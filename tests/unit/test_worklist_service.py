"""Pinned evidence revalidation, issue-only holds and no disk writes/acquisition."""

import json
from dataclasses import replace

import pytest

from mn_land.parcel_table import TableFilters, query, select_parcel
from mn_land.provenance import sha256_file
from mn_land.review_service import ReviewService, SnapshotKey
from mn_land.runs import RunValidationError


def test_preview_download_context_issues_no_mutation_or_acquisition(viewer_data, monkeypatch):
    root, _, review = viewer_data(
        rows=[
            "020010200,Owner,2024,2025,100",
            "020010200,Owner,2025,2025,100",
            "999999999,Unmatched,2024,2025,0",
        ]
    )
    before = {str(p): sha256_file(p) for p in root.rglob("*") if p.is_file()}

    def prohibited(*args, **kwargs):
        pytest.fail("Export attempted acquisition/replay/latest")

    monkeypatch.setattr("mn_land.counties.isanti.IsantiAdapter.fetch_parcels", prohibited)
    monkeypatch.setattr("mn_land.delinquency.pipeline.replay_delinquency", prohibited)
    monkeypatch.setattr("mn_land.delinquency.pipeline.import_and_join_delinquency", prohibited)
    monkeypatch.setattr("mn_land.runs.select_latest", prohibited)
    service = ReviewService(root)
    dataset = service.load_parcels(SnapshotKey("review", review.name))
    filters = TableFilters(view="either")
    preview = service.prepare_export(dataset, filters)
    result = json.loads(service.download_export(preview, "json"))
    assert len(result["candidates"]) == 1
    assert any(row["kind"] == "unmatched" for row in result["issues"])
    assert any(row["kind"] == "fiscal_group_review" for row in result["issues"])
    assert result["context"]["report_verification_date"] is None
    assert result["context"]["synthetic"] is True
    assert result["context"]["mapping_sha256"]
    assert str(root) not in json.dumps(result)
    assert before == {str(p): sha256_file(p) for p in root.rglob("*") if p.is_file()}
    identity = select_parcel(dataset, query(dataset, filters), dataset.rows[0].parcel_id)
    assert (
        service.prepare_export(dataset, filters, scope="selected", identity=identity).payload()[
            "context"
        ]["candidate_count"]
        == 1
    )
    with pytest.raises(RunValidationError):
        service.download_export(replace(preview, document=preview.document + " "), "json")
    with pytest.raises(RunValidationError):
        service.prepare_export(
            dataset,
            filters,
            scope="selected",
            identity=replace(identity, completion_sha256="0" * 64),
        )
    (review / "summary.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RunValidationError, match="Download refused"):
        service.download_export(preview, "csv")


@pytest.mark.parametrize("held,empty", [(True, False), (False, True)])
def test_held_and_empty_results_offer_only_honest_issue_context(viewer_data, held, empty):
    root, _, review = viewer_data(held=held, empty=empty)
    service = ReviewService(root)
    dataset = service.load_parcels(SnapshotKey("review", review.name))
    preview = service.prepare_export(dataset, TableFilters(view="either"))
    data = json.loads(service.download_export(preview, "json"))
    assert not data["candidates"]
    assert data["context"]["holds"] == list(dataset.overview.holds)
    assert data["issues"]  # explicit accounting/quarantine counts, even if all zero


def test_changes_during_issue_read_are_rejected(viewer_data, monkeypatch):
    from mn_land import review_service

    root, _, review = viewer_data()
    service = ReviewService(root)
    dataset = service.load_parcels(SnapshotKey("review", review.name))
    original = review_service.read_artifact_bytes

    def changed(run, name, **kwargs):
        body = original(run, name, **kwargs)
        if name == "isanti_unmatched_delinquency_records.csv":
            (run.path / name).write_bytes(body + b"changed")
        return body

    monkeypatch.setattr(review_service, "read_artifact_bytes", changed)
    with pytest.raises(RunValidationError):
        service.prepare_export(dataset, TableFilters(view="either"))
