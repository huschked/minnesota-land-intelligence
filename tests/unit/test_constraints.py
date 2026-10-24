"""Offline planar controls for the explicitly versioned mapped remainder policy."""
import hashlib
from copy import deepcopy
from datetime import date

import pytest

pytest.importorskip("shapely")
pytest.importorskip("pyproj")
import shapely
from shapely.geometry import MultiPolygon, Polygon, box
from test_floods import feature as flood_feature
from test_floods import parcel, studies

from mn_land.constraints import POLICY, combine
from mn_land.floods import overlap as flood_overlap
from mn_land.geometry import ACRE_M2, GeometryError
from mn_land.wetlands import overlap as wetland_overlap


def inputs(water=None, hazard=None, *, geometry=None, category="vegetated_or_other_wetland"):
    p = parcel(geometry)
    p["analysis_wkb_sha256"] = hashlib.sha256(bytes.fromhex(p["analysis_wkb_hex"])).hexdigest()
    wet = [] if water is None else [{"object_id": 1, "category": category,
        "analysis_wkb_hex": water.wkb_hex, "raw_attributes": {}}]
    projects = [{"object_id": 1, "analysis_wkb_hex": box(-100, -100, 1000, 1000).wkb_hex,
                 "raw_attributes": {}}]
    features = [flood_feature("availability", box(-100, -100, 1000, 1000)),
                flood_feature("panels", box(-100, -100, 1000, 1000))]
    whole = shapely.from_wkb(p["analysis_wkb_hex"])
    if hazard is not None:
        features.append(flood_feature("zones", hazard, zone="AE", sfha="T", subtype=None))
    rest = whole if hazard is None else whole.difference(hazard)
    if not rest.is_empty:
        features.append(flood_feature("zones", rest, oid=2))
    when = date(2026, 10, 24)
    return [p], wetland_overlap([p], wet, projects, as_of=when), flood_overlap([p], features, studies(), as_of=when)


@pytest.mark.parametrize("wet_end,flood_start,expected,shared", [
    (0, 100, 10000, 0), (100, 100, 0, 0), (0, 0, 0, 0),
    (40, 100, 6000, 0), (60, 40, 0, 2000), (40, 60, 2000, 0),
    (60, 60, 0, 0), (100, 0, 0, 10000),
])
def test_zero_full_partial_overlap_union_bounds(wet_end, flood_start, expected, shared):
    args = inputs(None if not wet_end else box(0, 0, wet_end, 100),
                  None if flood_start == 100 else box(flood_start, 0, 100, 100))
    before = deepcopy(args)
    row = combine(*args)[0]
    assert row["status"] == "complete"
    assert row["estimated_usable"]["m2"] == expected
    assert row["estimated_usable"]["acres"] == expected / ACRE_M2
    assert row["shared_water_sfha"]["m2"] == shared
    assert row["combined_constraint"]["m2"] == 10000 - expected
    assert row["area_reconciliation"]["parcel_minus_constraint_minus_remaining_m2"] == 0
    assert row["saved_deeded_acres"] == "3"  # Not the calculation denominator.
    assert args == before


@pytest.mark.parametrize("category", POLICY["included_dnr_categories"])
def test_explicit_water_categories_remain_separate_constraints(category):
    row = combine(*inputs(box(0, 0, 50, 100), category=category))[0]
    assert row["status"] == "complete"
    assert row["components"][category]["m2"] == 5000
    assert row["estimated_usable"]["m2"] == 5000


def test_holes_multipart_and_subset_not_double_subtracted():
    geometry = MultiPolygon([Polygon([(0, 0), (100, 0), (100, 100), (0, 100)],
        [[(20, 20), (30, 20), (30, 30), (20, 30)]]), box(200, 0, 210, 10)])
    row = combine(*inputs(box(-1, -1, 101, 101), box(50, 0, 90, 90), geometry=geometry))[0]
    assert row["status"] == "complete"
    assert row["combined_constraint"]["m2"] == 9900
    assert row["shared_water_sfha"]["m2"] == 3600
    assert row["estimated_usable"]["m2"] == 100
    assert shapely.from_wkb(row["estimated_usable"]["wkb_hex"]).equals(box(200, 0, 210, 10))


def test_boundary_contact_is_not_area_and_zero_is_not_null():
    row = combine(*inputs(box(100, 0, 200, 100)))[0]
    assert row["status"] == "complete"
    assert row["combined_constraint"]["m2"] == 0
    assert row["estimated_usable"]["m2"] == 10000


@pytest.mark.parametrize("which", ["wetlands", "floods", "both"])
def test_held_upstream_propagates_even_with_zero_coverage_gap(which):
    p, w, f = inputs(box(0, 0, 50, 100))
    for label, rows in (("wetlands", w), ("floods", f)):
        if which in {label, "both"}:
            rows[0]["status"] = "held"
            rows[0]["holds"] = ["synthetic_panel_or_classification_hold"]
    row = combine(p, w, f)[0]
    assert row["status"] == "held"
    assert row["estimated_usable"] is row["combined_constraint"] is row["components"] is None
    assert row["combined_evidence_gap"]["m2"] == 0
    assert any("synthetic_panel_or_classification_hold" in hold for hold in row["holds"])


@pytest.mark.parametrize("gap_end", [50, 100])
def test_missing_partial_coverage_quantified_without_double_count_or_estimate(gap_end):
    p, w, f = inputs()
    gap = box(0, 0, gap_end, 100)
    w[0].update(uncovered_wkb_hex=gap.wkb_hex, coverage_status="partial")
    f[0]["coverage"]["availability"].update(status="partial", uncovered={"wkb_hex": gap.wkb_hex})
    row = combine(p, w, f)[0]
    assert row["status"] == "held"
    assert row["estimated_usable"] is None
    assert row["combined_evidence_gap"]["m2"] == gap_end * 100
    assert row["independently_covered"]["m2"] == 10000 - gap_end * 100


def test_tiny_coverage_gap_is_not_filled_by_area_tolerance():
    p, w, f = inputs()
    gap = box(0, 0, 1e-8, 1)
    w[0]["uncovered_wkb_hex"] = gap.wkb_hex
    row = combine(p, w, f)[0]
    assert row["status"] == "held" and row["estimated_usable"] is None
    assert row["combined_evidence_gap"]["m2"] == 1e-8


def test_floodway_subset_not_added_and_x_subtypes_not_subtracted():
    p, w, f = inputs(hazard=box(0, 0, 50, 100))
    f[0]["metrics"]["floodway"] = deepcopy(f[0]["metrics"]["sfha"])
    f[0]["metrics"]["annual_chance_0_2pct"] = deepcopy(f[0]["metrics"]["minimal_hazard"])
    row = combine(p, w, f)[0]
    assert row["combined_constraint"]["m2"] == 5000
    assert row["estimated_usable"]["m2"] == 5000


@pytest.mark.parametrize("change", ["empty", "duplicate", "missing", "unexpected", "oid", "area", "hash",
                                    "invalid", "outside", "status", "null", "coverage"])
def test_malformed_incompatible_rows_refused(change):
    p, w, f = inputs(box(0, 0, 50, 100))
    if change == "empty": p = []
    if change == "duplicate": w += deepcopy(w)
    if change == "missing": f = []
    if change == "unexpected": f[0]["parcel_id"] = "other"
    if change == "oid": w[0]["parcel_object_id"] = 999
    if change == "area": w[0]["parcel_measured_m2"] = 99
    if change == "hash": p[0]["analysis_wkb_sha256"] = "0" * 64
    if change == "invalid": w[0]["observed_categories"]["vegetated_or_other_wetland"]["wkb_hex"] = Polygon([(0, 0), (100, 100), (0, 100), (100, 0), (0, 0)]).wkb_hex
    if change == "outside": w[0]["observed_categories"]["deepwater"]["wkb_hex"] = box(200, 0, 300, 100).wkb_hex
    if change == "status": f[0]["status"] = "unknown"
    if change == "null": f[0]["metrics"]["sfha"] = None
    if change == "coverage": del f[0]["coverage"]["study_matched"]
    with pytest.raises(GeometryError): combine(p, w, f)


def test_selection_bound_and_stable_order():
    p, w, f = inputs()
    with pytest.raises(GeometryError): combine(p * 16, w, f)
    assert [r["parcel_id"] for r in combine(p, w, f)] == [r["parcel_id"] for r in p]
