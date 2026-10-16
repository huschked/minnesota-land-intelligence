"""S01-S07: explicit, portable and deterministic offline Isanti replay."""

import csv
import json
import shutil
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from mn_land import cli
from mn_land.config.input_limits import InputLimits
from mn_land.config.settings import Settings
from mn_land.counties.isanti.review import build_review
from mn_land.delinquency import pipeline
from mn_land.provenance import sha256_file
from mn_land.replay import input_dates
from mn_land.runs import JOIN_OUTPUTS, RunValidationError, read_json, validate_run, workspace_path

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture
def saved(tmp_path, make_raw, fake_adapter):
    parcel = make_raw(tmp_path / "raw")
    adapter = fake_adapter()
    stats = pipeline.import_and_join_delinquency(
        FIXTURES / "isanti_delinquency.csv",
        FIXTURES / "isanti_delinquency_mapping.json",
        Decimal(10),
        adapter=adapter,
        raw_root=tmp_path / "raw",
        processed_root=tmp_path / "processed",
    )
    return parcel, stats, adapter


def tree(path):
    return {str(p.relative_to(path)): sha256_file(p) for p in path.rglob("*") if p.is_file()}


def reseal_manifest(path, edit):
    manifest = read_json(path / "manifest.json")
    edit(manifest)
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    marker = read_json(path / "completion.json")
    for entry in marker["artifacts"]:
        if entry["path"] == "manifest.json":
            entry.update(
                bytes=(path / "manifest.json").stat().st_size,
                sha256=sha256_file(path / "manifest.json"),
            )
    (path / "completion.json").write_text(json.dumps(marker), encoding="utf-8")


def test_S01_explicit_import_ignores_newer_parcel_snapshot(tmp_path, saved, make_raw):
    parcel, initial, adapter = saved
    make_raw(tmp_path / "raw", [])
    raw_pointer = (parcel.parent / "latest.json").read_bytes()
    selected = pipeline.import_and_join_delinquency(
        FIXTURES / "isanti_delinquency.csv",
        FIXTURES / "isanti_delinquency_mapping.json",
        Decimal(10),
        adapter=adapter,
        raw_root=tmp_path / "raw",
        processed_root=tmp_path / "processed",
        parcel_snapshot=parcel,
    )
    assert selected.verified_candidates == initial.verified_candidates == 1
    manifest = read_json(selected.processed_snapshot_dir / "manifest.json")
    assert manifest["selection"]["mode"] == "explicit_pair"
    assert manifest["selection"]["parcel_run_id"] == parcel.name
    assert (parcel.parent / "latest.json").read_bytes() == raw_pointer


def test_S02_replay_exact_inputs_preserves_all_content_and_source_capture_dates(
    tmp_path,
    saved,
    monkeypatch,
):
    parcel, initial, adapter = saved
    before = tree(initial.raw_snapshot_dir), tree(parcel)
    original = read_json(initial.processed_snapshot_dir / "manifest.json")

    class FutureClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2031, 1, 1, tzinfo=UTC)

    monkeypatch.setattr(pipeline, "datetime", FutureClock)
    replayed = pipeline.replay_delinquency(
        snapshot=initial.processed_snapshot_dir,
        adapter=adapter,
        processed_root=tmp_path / "replayed",
    )
    actual = read_json(replayed.processed_snapshot_dir / "manifest.json")
    assert actual["created_at"].startswith("2031-")
    assert actual["reproducibility"] == original["reproducibility"]
    assert actual["selection"]["dates"] == original["selection"]["dates"]
    assert actual["selection"]["comparison"] == "identical_exports_and_recorded_normalization"
    assert actual["selection"]["replayed_from"]["run_id"] == initial.processed_snapshot_dir.name
    for name in JOIN_OUTPUTS:
        assert (replayed.processed_snapshot_dir / name).read_bytes() == (
            initial.processed_snapshot_dir / name
        ).read_bytes()
    assert (tree(initial.raw_snapshot_dir), tree(parcel)) == before


def test_S03_moved_join_is_self_contained_and_never_uses_latest_or_network(
    tmp_path,
    saved,
    monkeypatch,
):
    _, initial, adapter = saved
    moved = workspace_path(tmp_path / "portable" / initial.processed_snapshot_dir.name)
    shutil.copytree(initial.processed_snapshot_dir, moved)
    (tmp_path / "raw").rename(tmp_path / "unavailable-raw")
    (tmp_path / "processed").rename(tmp_path / "unavailable-processed")

    def prohibited(*args, **kwargs):
        pytest.fail("Replay attempted latest selection or acquisition")

    monkeypatch.setattr(pipeline, "select_latest", prohibited)
    monkeypatch.setattr(adapter, "fetch_parcels", prohibited)
    monkeypatch.setattr(adapter.client, "metadata", prohibited)
    before = tree(moved)
    replayed = pipeline.replay_delinquency(
        snapshot=moved,
        adapter=adapter,
        processed_root=tmp_path / "fresh-output",
    )
    assert replayed.verified_candidates == 1
    assert validate_run(replayed.processed_snapshot_dir, "delinquency_processed")
    assert tree(moved) == before


def test_S03_explicit_raw_pair_is_offline_and_creates_no_new_raw_capture(tmp_path, saved):
    parcel, initial, adapter = saved
    before = tree(tmp_path / "raw")
    replayed = pipeline.replay_delinquency(
        parcel_snapshot=parcel,
        import_snapshot=initial.raw_snapshot_dir,
        adapter=adapter,
        processed_root=tmp_path / "raw-pair-output",
    )
    assert replayed.verified_candidates == 1
    assert tree(tmp_path / "raw") == before
    assert (
        read_json(replayed.processed_snapshot_dir / "manifest.json")["selection"]["mode"]
        == "explicit_pair"
    )


@pytest.mark.parametrize("held", [False, True])
def test_S04_mixed_periods_unknown_balances_and_source_holds_survive_replay(
    tmp_path,
    make_raw,
    fake_adapter,
    held,
):
    parcel = make_raw(tmp_path / "raw")
    source, mapping = tmp_path / "input.csv", tmp_path / "mapping.json"
    source.write_text(
        "PARID,OWN1,ASMTYR,TAXYR,TOTAMT\n"
        "020010200,Synthetic,2024,2025,100\n"
        "020010200,Synthetic,2023,2025,100\n"
        "020010200,Synthetic,2025,2025,100\n",
        encoding="utf-8",
    )
    (tmp_path / "evidence.md").write_text("Synthetic county convention evidence", encoding="utf-8")
    payload = {
        "source_agency": "Isanti County",
        "dataset": "Synthetic mixed snapshot",
        "delinquency_assertion": "mixed_unpaid_prior_and_overdue_current_year_taxes",
        "tax_year_convention": "isanti_assessment_year_plus_one",
        "year_semantics_reference": "evidence.md",
        "supporting_documents": ["evidence.md"],
        "columns": {"parcel_id": "PARID", "owner_name": "OWN1"},
    }
    if held:
        payload["verification_hold_reason"] = "Synthetic unresolved source hold"
    mapping.write_text(json.dumps(payload), encoding="utf-8")
    initial = pipeline.import_and_join_delinquency(
        source,
        mapping,
        Decimal(10),
        adapter=fake_adapter(),
        raw_root=tmp_path / "raw",
        processed_root=tmp_path / "processed",
        parcel_snapshot=parcel,
    )
    replayed = pipeline.replay_delinquency(
        snapshot=initial.processed_snapshot_dir,
        adapter=fake_adapter(),
        processed_root=tmp_path / "replayed",
    )
    manifest = read_json(replayed.processed_snapshot_dir / "manifest.json")
    assert manifest["prior_year_source_rows"] == 2 and manifest["current_year_source_rows"] == 1
    assert replayed.verified_candidates == (0 if held else 1)
    candidates = read_json(
        replayed.processed_snapshot_dir / "isanti_verified_delinquent_candidates.json"
    )
    if not held:
        assert candidates[0]["total_taxes_and_penalties_due"] is None
        assert candidates[0]["balance_aggregation_status"] == "not_aggregated"
    review = build_review(replayed.processed_snapshot_dir)
    summary = read_json(review / "summary.json")
    assert summary["manual_verification_status"] == ("verification_hold" if held else "pending")
    assert summary["tax_status_screening_ready"] == (not held)


def test_S04_threshold_is_inherited_and_overrides_are_disclosed(tmp_path, saved):
    parcel, initial, adapter = saved
    first = pipeline.replay_delinquency(
        parcel_snapshot=parcel,
        import_snapshot=initial.raw_snapshot_dir,
        min_acres=Decimal(100),
        adapter=adapter,
        processed_root=tmp_path / "replayed",
    )
    second = pipeline.replay_delinquency(
        snapshot=first.processed_snapshot_dir,
        adapter=adapter,
        processed_root=tmp_path / "replayed",
    )
    assert second.verified_candidates == first.verified_candidates == 0
    changed = pipeline.replay_delinquency(
        snapshot=first.processed_snapshot_dir,
        min_acres=Decimal(0),
        adapter=adapter,
        processed_root=tmp_path / "replayed",
    )
    assert changed.verified_candidates == 1
    manifest = read_json(changed.processed_snapshot_dir / "manifest.json")
    assert manifest["selection"]["comparison"] == "threshold_changed_exports_not_compared"


@pytest.mark.parametrize(
    "field,value", [("service_url", "https://other.test/FeatureServer"), ("where", "OBJECTID < 5")]
)
def test_S05_resealed_wrong_source_or_partial_query_is_not_accepted(tmp_path, saved, field, value):
    parcel, initial, adapter = saved
    reseal_manifest(parcel, lambda manifest: manifest.update({field: value}))
    assert validate_run(parcel, "parcel_raw")  # integrity alone is not county compatibility
    with pytest.raises(ValueError, match="incompatible"):
        pipeline.replay_delinquency(
            parcel_snapshot=parcel,
            import_snapshot=initial.raw_snapshot_dir,
            adapter=adapter,
            processed_root=tmp_path / "bad-output",
        )
    assert not (tmp_path / "bad-output").exists()


@pytest.mark.parametrize("failure", ["tampered", "failed", "legacy", "wrong_county"])
def test_S05_invalid_selected_import_never_falls_back_or_writes_outputs(tmp_path, saved, failure):
    parcel, initial, adapter = saved
    raw = initial.raw_snapshot_dir
    if failure == "tampered":
        (raw / "source.csv").write_text("tampered", encoding="utf-8")
    elif failure == "failed":
        (raw / "failure.json").write_text("{}", encoding="utf-8")
    elif failure == "legacy":
        raw = tmp_path / "legacy"
        raw.mkdir()
        (raw / "manifest.json").write_text("{}", encoding="utf-8")
    else:
        reseal_manifest(raw, lambda manifest: manifest.update(county="Other County"))
    before = tree(raw)
    with pytest.raises(ValueError):
        pipeline.replay_delinquency(
            parcel_snapshot=parcel,
            import_snapshot=raw,
            adapter=adapter,
            processed_root=tmp_path / "bad-output",
        )
    assert not (tmp_path / "bad-output").exists() and tree(raw) == before


@pytest.mark.parametrize("stage", ["normalization", "exports"])
def test_S06_failed_replay_does_not_replace_previous_success(tmp_path, saved, monkeypatch, stage):
    parcel, initial, adapter = saved
    before = tree(initial.processed_snapshot_dir), tree(parcel), tree(initial.raw_snapshot_dir)
    pointer = (initial.processed_snapshot_dir.parent / "latest.json").read_bytes()
    if stage == "normalization":
        monkeypatch.setattr(pipeline, "normalized_digest", lambda rows: "0" * 64)
    else:
        original = pipeline.export_join_result

        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            path = args[1] / "isanti_verified_delinquent_candidates.csv"
            body = path.read_text(encoding="utf-8")
            changed_body = body.replace("Example Owner", "Changed Owner")
            assert changed_body != body
            path.write_text(changed_body, encoding="utf-8")
            return result

        monkeypatch.setattr(pipeline, "export_join_result", changed)
    with pytest.raises(RunValidationError, match="differ"):
        pipeline.replay_delinquency(
            snapshot=initial.processed_snapshot_dir,
            adapter=adapter,
            processed_root=tmp_path / "processed",
        )
    assert (initial.processed_snapshot_dir.parent / "latest.json").read_bytes() == pointer
    assert (
        tree(initial.processed_snapshot_dir),
        tree(parcel),
        tree(initial.raw_snapshot_dir),
    ) == before
    failed = list(initial.processed_snapshot_dir.parent.glob("*/failure.json"))
    assert len(failed) == 1 and not (failed[0].parent / "completion.json").exists()


def test_S06_output_cannot_be_inside_any_selected_input(tmp_path, saved):
    parcel, initial, adapter = saved
    for source in (parcel, initial.raw_snapshot_dir, initial.processed_snapshot_dir):
        before = tree(source)
        with pytest.raises(RunValidationError, match="inside a selected snapshot"):
            pipeline.replay_delinquency(
                snapshot=initial.processed_snapshot_dir,
                adapter=adapter,
                processed_root=source,
            )
        assert tree(source) == before


def test_S06_older_complete_join_does_not_get_invented_historical_fingerprints(tmp_path, saved):
    _, initial, adapter = saved

    def historical(manifest):
        del manifest["reproducibility"], manifest["selection"]

    reseal_manifest(initial.processed_snapshot_dir, historical)
    before = tree(initial.processed_snapshot_dir)
    replayed = pipeline.replay_delinquency(
        snapshot=initial.processed_snapshot_dir,
        adapter=adapter,
        processed_root=tmp_path / "replayed",
    )
    comparison = read_json(replayed.processed_snapshot_dir / "manifest.json")["selection"][
        "comparison"
    ]
    assert comparison == "identical_exports_historical_normalization_unknown"
    assert tree(initial.processed_snapshot_dir) == before


def test_S07_cli_raw_pair_and_missing_pair_have_clear_outcomes(
    tmp_path, saved, monkeypatch, capsys
):
    parcel, initial, adapter = saved
    monkeypatch.setattr(pipeline, "IsantiAdapter", lambda: adapter)
    monkeypatch.setattr(
        pipeline,
        "SETTINGS",
        Settings(
            raw_dir=tmp_path / "no-raw",
            processed_dir=tmp_path / "cli-output",
        ),
    )
    assert (
        cli.main(
            [
                "replay-delinquency",
                "--county",
                "isanti",
                "--parcel-snapshot",
                str(parcel),
                "--import-snapshot",
                str(initial.raw_snapshot_dir),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "explicit_pair" in output and "current payment status unknown" in output
    assert (
        cli.main(
            [
                "replay-delinquency",
                "--county",
                "isanti",
                "--snapshot",
                str(initial.processed_snapshot_dir),
                "--output-root",
                str(tmp_path / "cli-selected-join"),
            ]
        )
        == 0
    )
    assert "recorded_join" in capsys.readouterr().out
    assert (
        cli.main(
            [
                "replay-delinquency",
                "--county",
                "isanti",
                "--import-snapshot",
                str(initial.raw_snapshot_dir),
            ]
        )
        == 2
    )


@pytest.mark.parametrize("publication", [None, "2026-01-01", "2030-01-01"])
def test_S07_date_offsets_are_exact_and_uncertainty_is_visible(publication):
    dates = input_dates(
        {"retrieved_at": "2026-01-01T06:00:00.000001+00:00"},
        {"imported_at": "2026-01-01T00:00:00-06:00"},
        publication,
    )
    assert dates["parcel_minus_import_seconds"] == "0.000001"
    assert "current payment status unknown" in dates["limitation"]
    if publication is None:
        assert any("unknown" in warning for warning in dates["warnings"])
    if publication == "2030-01-01":
        assert any("postdates" in warning for warning in dates["warnings"])


def test_S02_xlsx_replays_retained_bytes_and_captured_limits(tmp_path, make_raw, fake_adapter):
    from openpyxl import Workbook

    make_raw(tmp_path / "raw")
    with (FIXTURES / "isanti_delinquency.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    workbook = Workbook()
    for row in rows:
        workbook.active.append(row)
    source = tmp_path / "listing.xlsx"
    workbook.save(source)
    workbook.close()
    limits = InputLimits(max_records=42)
    initial = pipeline.import_and_join_delinquency(
        source,
        FIXTURES / "isanti_delinquency_mapping.json",
        Decimal(10),
        adapter=fake_adapter(),
        raw_root=tmp_path / "raw",
        processed_root=tmp_path / "processed",
        limits=limits,
    )
    replayed = pipeline.replay_delinquency(
        snapshot=initial.processed_snapshot_dir,
        adapter=fake_adapter(),
        processed_root=tmp_path / "replayed",
    )
    manifest = read_json(replayed.processed_snapshot_dir / "manifest.json")
    assert manifest["input_limits"]["max_records"] == 42
    assert (
        manifest["reproducibility"]
        == read_json(initial.processed_snapshot_dir / "manifest.json")["reproducibility"]
    )
    assert (initial.raw_snapshot_dir / "source.xlsx").read_bytes() == source.read_bytes()


@pytest.mark.parametrize(
    "field,value",
    [
        ("parcel_run_id", "wrong"),
        ("dates", {}),
        ("comparison", "made_up"),
    ],
)
def test_S05_resealed_replay_metadata_must_reconcile_with_pinned_evidence(saved, field, value):
    _, initial, _ = saved
    reseal_manifest(
        initial.processed_snapshot_dir,
        lambda manifest: manifest["selection"].update({field: value}),
    )
    with pytest.raises(RunValidationError):
        validate_run(initial.processed_snapshot_dir, "delinquency_processed")


@pytest.mark.parametrize("minimum", [True, Decimal("NaN"), Decimal("Infinity"), Decimal(-1)])
def test_S07_invalid_threshold_rejected_without_outputs(tmp_path, minimum):
    with pytest.raises(ValueError):
        pipeline.replay_delinquency(
            parcel_snapshot=tmp_path / "missing-parcel",
            import_snapshot=tmp_path / "missing-import",
            min_acres=minimum,
            processed_root=tmp_path / "output",
        )
    assert not (tmp_path / "output").exists()
