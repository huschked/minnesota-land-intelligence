"""Saved table loads retain validation and threshold/hold boundaries."""

from dataclasses import replace

import pytest

from mn_land.parcel_table import TableFilters, query
from mn_land.provenance import sha256_file
from mn_land.review_service import ReviewService, SnapshotKey
from mn_land.runs import RunValidationError


def test_load_table_distinct_allowlist_and_originals_unchanged(viewer_data, monkeypatch):
    root, _, review = viewer_data()

    def tree():
        return {str(p.relative_to(root)): sha256_file(p) for p in root.rglob("*") if p.is_file()}

    baseline = tree()

    def prohibited(*args, **kwargs):
        pytest.fail("Viewer acquired, replayed or reimported data")

    monkeypatch.setattr("mn_land.counties.isanti.IsantiAdapter.fetch_parcels", prohibited)
    monkeypatch.setattr("mn_land.delinquency.pipeline.replay_delinquency", prohibited)
    monkeypatch.setattr("mn_land.delinquency.pipeline.import_and_join_delinquency", prohibited)
    monkeypatch.setattr("mn_land.runs.select_latest", prohibited)
    loaded = ReviewService(root).load_parcels(SnapshotKey("review", review.name))
    assert len(loaded.rows) == 1
    assert loaded.rows[0].prior and loaded.rows[0].current
    assert "original_row" not in repr(loaded.rows)
    assert str(root) not in repr(loaded.rows)
    assert tree() == baseline
    assert dict(query(loaded, TableFilters(view="either")).counts)["either"] == 1


@pytest.mark.parametrize("held,empty", [(True, False), (False, True)])
def test_held_or_empty_never_browsable_as_candidates(viewer_data, held, empty):
    root, _, review = viewer_data(held=held, empty=empty)
    data = ReviewService(root).load_parcels(SnapshotKey("review", review.name))
    assert not data.rows
    assert bool(data.overview.holds) == held


def test_review_floor_can_be_stricter_than_join_without_inventing_missing_records(viewer_data):
    root, _, review = viewer_data(review_min_acres=30)
    data = ReviewService(root).load_parcels(SnapshotKey("review", review.name))
    assert data.overview.minimum_acres == 10
    assert data.minimum_acres == 30
    assert not data.rows  # original GIS fixture is 25.5 acres
    with pytest.raises(ValueError, match="floor"):
        query(data, TableFilters(minimum_acres=20))


def test_new_table_read_revalidates_exact_completion_identity(viewer_data):
    root, _, review = viewer_data()
    service = ReviewService(root)
    data = service.load_parcels(SnapshotKey("review", review.name))
    with pytest.raises(RunValidationError):
        service.load_parcels(data.overview.key, expected_completion="0" * 64)
    (review / "isanti_land_review.csv").write_text("changed", encoding="utf-8")
    with pytest.raises(RunValidationError):
        service.load_parcels(data.overview.key, expected_completion=data.overview.completion_sha256)


def test_changed_pinned_child_between_reads_cannot_be_promoted(viewer_data, monkeypatch):
    from mn_land import review_service

    root, _, review = viewer_data()
    original = review_service.validate_run

    def changed(path, kind):
        result = original(path, kind)
        if kind == "delinquency_processed":
            return replace(result, completion_sha256="0" * 64)
        return result

    monkeypatch.setattr(review_service, "validate_run", changed)
    with pytest.raises(RunValidationError):
        ReviewService(root).load_parcels(SnapshotKey("review", review.name))


def test_review_comparison_hold_cannot_reexpose_join_candidates(viewer_data, tmp_path):
    from mn_land.counties.isanti.review import build_review

    root, joined, _ = viewer_data()
    comparison = tmp_path / "comparison.json"
    comparison.write_text(
        '{"operational_status":"HOLD_COUNTY_RECONCILIATION_REQUIRED","findings":[]}',
        encoding="utf-8",
    )
    review = build_review(joined.processed_snapshot_dir, comparison_path=comparison)
    loaded = ReviewService(root).load_parcels(SnapshotKey("review", review.name))
    assert loaded.overview.holds
    assert dict(loaded.overview.counts)["Prior-year large parcels"] == 1
    assert not loaded.rows
