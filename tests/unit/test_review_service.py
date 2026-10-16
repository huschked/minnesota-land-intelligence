"""U01-U03/U08/U11: core viewer boundary, independent of Streamlit installation."""
import dataclasses
import subprocess
import sys

import pytest

from mn_land.provenance import sha256_file
from mn_land.review_service import ReviewService, SnapshotKey
from mn_land.runs import RunValidationError, read_artifact_json, validate_run


def tree(path):
    return {str(p.relative_to(path)): sha256_file(p) for p in path.rglob("*") if p.is_file()}


def test_missing_folder_is_not_empty_success(tmp_path):
    catalog = ReviewService(tmp_path / "missing").catalog()
    assert not catalog.entries
    assert len(catalog.notices) == 2


def test_catalog_classifies_legacy_failed_partial_unsupported_and_corrupt(tmp_path):
    root = tmp_path / "isanti/delinquency"
    for name, payload in (
        ("legacy", {"manifest.json": "{}"}),
        ("failed", {"failure.json": "{}"}),
        ("incomplete", {}),
        ("unsupported", {"completion.json": '{"schema_version":3}'}),
        ("invalid", {"completion.json": "{"}),
    ):
        path = root / name
        path.mkdir(parents=True)
        for filename, content in payload.items():
            (path / filename).write_text(content, encoding="utf-8")
    before = tree(tmp_path)
    service = ReviewService(tmp_path)
    catalog = service.catalog()
    assert {entry.key.run_id: entry.state for entry in catalog.entries} == {
        state: state for state in ("legacy", "failed", "incomplete", "unsupported", "invalid")
    }
    assert not any(entry.eligible for entry in catalog.entries)
    for entry in catalog.entries:
        with pytest.raises(RunValidationError):
            service.load(entry.key)
    assert tree(tmp_path) == before


@pytest.mark.parametrize("run_id", ["../outside", "C:/secret", "a\\b", ".", "x:y", "<script>", ""])
def test_widget_ids_never_become_arbitrary_paths(run_id):
    with pytest.raises(RunValidationError):
        SnapshotKey("review", run_id)


def test_wrong_kind_is_rejected():
    with pytest.raises(RunValidationError):
        SnapshotKey("parcel_raw", "valid")


@pytest.mark.parametrize("kind", ["review", "delinquency_processed"])
def test_load_projects_allowlisted_immutable_metadata(viewer_data, kind):
    root, joined, review = viewer_data()
    path = review if kind == "review" else joined.processed_snapshot_dir
    before = tree(root)
    loaded = ReviewService(root).load(SnapshotKey(kind, path.name))
    assert loaded.key.run_id == path.name
    assert loaded.join_id == joined.processed_snapshot_dir.name
    assert loaded.import_id == joined.raw_snapshot_dir.name
    assert loaded.synthetic
    assert loaded.listing_publication_date.isoformat() == "2026-01-01"
    assert loaded.gis_captured_at.tzinfo is not None
    assert loaded.report_verification_date is None
    assert not loaded.holds
    assert dict(loaded.counts)["Prior-year large parcels"] == 1
    assert dict(loaded.counts)["Current-year overdue large parcels"] == 1  # not a unique total of 2
    assert dict(loaded.unknown_counts)["Combined tax/penalty balance"] == 1
    assert "original_row" not in repr(loaded)
    assert "Synthetic owner" not in repr(loaded)
    assert str(root) not in repr(loaded)
    with pytest.raises(dataclasses.FrozenInstanceError):
        loaded.join_id = "replaced"
    assert tree(root) == before


def test_completed_empty_is_eligible_and_distinct_from_missing(viewer_data):
    root, _, review = viewer_data(empty=True)
    service = ReviewService(root)
    assert all(entry.eligible for entry in service.catalog().entries)
    loaded = service.load(SnapshotKey("review", review.name))
    assert dict(loaded.counts)["Prior-year large parcels"] == 0
    assert dict(loaded.counts)["Unmatched listing rows"] == 2


def test_active_holds_stay_visible_without_interpreting_amounts(viewer_data):
    root, _, review = viewer_data(held=True)
    loaded = ReviewService(root).load(SnapshotKey("review", review.name))
    assert "Synthetic hold" in loaded.holds[0]
    assert dict(loaded.counts)["Prior-year large parcels"] == 0
    assert loaded.holds


def test_reload_changed_graph_fails_without_falling_back(viewer_data):
    root, _, review = viewer_data()
    service = ReviewService(root)
    loaded = service.load(SnapshotKey("review", review.name))
    viewer_data()  # newer valid result cannot replace the selected identity
    target = review / "isanti_land_review.csv"
    target.write_bytes(target.read_bytes() + b"changed")
    with pytest.raises(RunValidationError, match="nothing was refreshed"):
        service.revalidate(loaded)
    assert loaded.key.run_id == review.name  # immutable old observation, not fresh validation


def test_review_graph_is_self_contained_and_has_no_acquisition_calls(viewer_data, monkeypatch):
    root, joined, review = viewer_data()

    def prohibited(*args, **kwargs):
        pytest.fail("Viewer attempted acquisition, replay, latest lookup or normalization")

    monkeypatch.setattr("mn_land.delinquency.pipeline.replay_delinquency", prohibited)
    monkeypatch.setattr("mn_land.delinquency.pipeline.import_and_join_delinquency", prohibited)
    monkeypatch.setattr("mn_land.runs.select_latest", prohibited)
    monkeypatch.setattr("mn_land.counties.isanti.IsantiAdapter.fetch_parcels", prohibited)
    joined.processed_snapshot_dir.rename(joined.processed_snapshot_dir.with_name("moved-original"))
    loaded = ReviewService(root).load(SnapshotKey("review", review.name))
    assert dict(loaded.counts)["Prior-year large parcels"] == 1


@pytest.mark.parametrize("change", ["artifact", "completion", "unlisted", "overflow"])
def test_inventory_reader_detects_changes_after_validation(viewer_data, change, monkeypatch):
    _, joined, _ = viewer_data()
    run = validate_run(joined.processed_snapshot_dir, "delinquency_processed")
    name = "manifest.json"
    if change == "artifact":
        (run.path / name).write_text("{}", encoding="utf-8")
    elif change == "completion":
        (run.path / "completion.json").write_text("{}", encoding="utf-8")
    elif change == "unlisted":
        name = "../secret.json"
    else:
        monkeypatch.setattr("mn_land.runs.MAX_JSON_BYTES", 2)
    with pytest.raises(RunValidationError):
        read_artifact_json(run, name)


def test_catalog_budget_fails_visibly_without_partial_trust(tmp_path, monkeypatch):
    root = tmp_path / "isanti/review"
    root.mkdir(parents=True)
    for name in ("a", "b", "c"):
        (root / name).mkdir()
    monkeypatch.setattr("mn_land.review_service.MAX_SNAPSHOTS_PER_KIND", 2)
    catalog = ReviewService(tmp_path).catalog()
    assert not catalog.entries
    assert any("Too many" in notice for notice in catalog.notices)


def test_cli_service_and_launcher_help_work_with_streamlit_imports_blocked(viewer_data):
    root, _, review = viewer_data()
    program = '''
import importlib.abc, sys
class BlockUI(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "streamlit" or fullname.startswith("streamlit."):
            raise ModuleNotFoundError("UI intentionally absent", name="streamlit")
sys.meta_path.insert(0, BlockUI())
import mn_land.review_service
from pathlib import Path
from mn_land.review_service import ReviewService, SnapshotKey
loaded = ReviewService(Path(sys.argv[1])).load(SnapshotKey("review", sys.argv[2]))
assert dict(loaded.counts)["Prior-year large parcels"] == 1
from mn_land.ui.launcher import main
assert main([]) == 2
from mn_land.cli import main as cli_main
cli_main(["--help"])
'''
    result = subprocess.run(
        [sys.executable, "-c", program, str(root), review.name],
        check=False, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "Optional UI missing" in result.stderr
    assert "find-candidates" in result.stdout


def test_parent_source_completion_is_checked_again_between_reads(viewer_data, monkeypatch):
    root, _, review = viewer_data()
    from mn_land import review_service
    original = review_service.validate_run

    def changed_child(path, kind):
        result = original(path, kind)
        if kind == "delinquency_processed":
            return dataclasses.replace(result, completion_sha256="0" * 64)
        return result

    monkeypatch.setattr(review_service, "validate_run", changed_child)
    with pytest.raises(RunValidationError, match="nothing was refreshed"):
        ReviewService(root).load(SnapshotKey("review", review.name))


def test_revalidate_rejects_different_completion_identity(viewer_data):
    root, _, review = viewer_data()
    service = ReviewService(root)
    loaded = service.load(SnapshotKey("review", review.name))
    with pytest.raises(RunValidationError):
        service.revalidate(dataclasses.replace(loaded, completion_sha256="0" * 64))


def test_unreadable_root_fails_helpfully_without_paths(tmp_path, monkeypatch):
    service = ReviewService(tmp_path)
    def denied(kind):
        raise PermissionError("secret local path")
    monkeypatch.setattr(service, "_root", denied)
    catalog = service.catalog()
    assert len(catalog.notices) == 2
    assert "secret" not in repr(catalog)
