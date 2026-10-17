"""Detail reads revalidate evidence, use pinned graphs and never fetch replacements."""

import json
from dataclasses import replace

import pytest

from mn_land.parcel_table import TableFilters, query, select_parcel
from mn_land.provenance import sha256_file
from mn_land.review_service import ReviewService, SnapshotKey
from mn_land.runs import RunValidationError, read_artifact_bytes, validate_run


@pytest.fixture
def chosen(viewer_data):
    root, joined, review = viewer_data()
    service = ReviewService(root)
    dataset = service.load_parcels(SnapshotKey("review", review.name))
    result = query(dataset, TableFilters(view="either"))
    identity = select_parcel(dataset, result, result.rows[0].parcel_id)
    return root, joined, review, service, dataset, identity


def test_detail_allowlist_lineage_and_preserved_graph(chosen, monkeypatch):
    root, _, _, service, dataset, identity = chosen

    def tree():
        return {str(p.relative_to(root)): sha256_file(p) for p in root.rglob("*") if p.is_file()}

    before = tree()

    def prohibited(*args, **kwargs):
        pytest.fail("Details attempted acquisition, replay, reimport or latest selection")

    monkeypatch.setattr("mn_land.counties.isanti.IsantiAdapter.fetch_parcels", prohibited)
    monkeypatch.setattr("mn_land.delinquency.pipeline.replay_delinquency", prohibited)
    monkeypatch.setattr("mn_land.delinquency.pipeline.import_and_join_delinquency", prohibited)
    monkeypatch.setattr("mn_land.runs.select_latest", prohibited)
    detail = service.load_details(dataset, identity)
    assert detail.identity == identity and detail.checked_at.tzinfo is not None
    assert len(detail.rows) == 2
    assert detail.parcel.owner_name == "Example Owner"
    assert all(row.owner_text == "Synthetic owner" for row in detail.rows)
    assert detail.year_evidence_name == "viewer-years.md" and len(detail.year_evidence_sha256) == 64
    assert not detail.links and not detail.sample_findings
    assert str(root) not in repr(detail)
    assert tree() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("county", "Other"),
        ("snapshot_token", "review/other"),
        ("completion_sha256", "0" * 64),
        ("parcel_id", "../outside"),
    ],
)
def test_forged_detail_identity_is_not_a_file_selector(chosen, field, value):
    _, _, _, service, dataset, identity = chosen
    with pytest.raises(RunValidationError):
        service.load_details(dataset, replace(identity, **{field: value}))


def test_source_changes_between_validated_reads_fail_closed(chosen, monkeypatch):
    from mn_land import review_service

    _, _, _, service, dataset, identity = chosen
    original = review_service.read_artifact_bytes

    def changed(run, name, **kwargs):
        body = original(run, name, **kwargs)
        if name == "source.csv":
            (run.path / name).write_bytes(body + b"changed")
        return body

    monkeypatch.setattr(review_service, "read_artifact_bytes", changed)
    with pytest.raises(RunValidationError, match="nothing was fetched"):
        service.load_details(dataset, identity)


def test_raw_artifact_reader_detects_tamper_and_honors_budget(chosen):
    _, _, review, _, _, _ = chosen
    run = validate_run(review, "review")
    assert read_artifact_bytes(run, "summary.json").startswith(b"{")
    with pytest.raises(RunValidationError):
        read_artifact_bytes(run, "summary.json", max_bytes=1)
    with pytest.raises(RunValidationError):
        read_artifact_bytes(run, "../secret")
    (review / "summary.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RunValidationError):
        read_artifact_bytes(run, "summary.json")


def test_only_explicitly_pinned_parcel_sample_is_shown(chosen, tmp_path):
    from mn_land.counties.isanti.review import build_review

    _root, joined, _, service, dataset, identity = chosen
    evidence = tmp_path / "comparison.json"
    evidence.write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "parcel_id": identity.parcel_id,
                        "verification_result": "positive_outstanding_for_listed_prior_year",
                        "listed_taxes_payable_years": "2025",
                        "county_report_pdf": "C:/secret/report.pdf",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    review = build_review(joined.processed_snapshot_dir, comparison_path=evidence)
    assert not service.load_details(
        dataset, identity
    ).sample_findings  # no latest/historical discovery
    new = service.load_parcels(SnapshotKey("review", review.name))
    new_identity = select_parcel(new, query(new, TableFilters(view="either")), identity.parcel_id)
    detail = service.load_details(new, new_identity)
    assert len(detail.sample_findings) == 1
    assert detail.sample_findings[0].aligns_with_selected_prior_years is True
    assert "C:/secret" not in repr(detail)
