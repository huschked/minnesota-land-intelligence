"""Pure planar controls and real, bundled offline alignment-grid controls."""
from copy import deepcopy
from datetime import date

import pytest

pytest.importorskip("pyproj")
pytest.importorskip("shapely")
import shapely
from pyproj.exceptions import ProjError
from shapely.geometry import MultiPolygon, Polygon, box

from mn_land.counties.isanti.wetland_crs import GRID_NAME, REFERENCE_ROOT, WetlandAlignment
from mn_land.geometry import GeometryError
from mn_land.sources.dnr_nwi import INCLUSION_POLICY, LEGACY_INCLUSION_POLICY, category
from mn_land.wetlands import esri_polygon, overlap, project_dates, project_features, query_groups

AS_OF = date(2026, 10, 19)


def parcel(shape=None, identity="synthetic"):
    shape = box(0, 0, 100, 100) if shape is None else shape
    return {"parcel_id": identity, "object_id": 1, "analysis_wkb_hex": shape.wkb_hex,
            "saved_deeded_acres": "3", "new_gis_deeded_acres": 3.0, "deeded_discrepancy": True}


def mapped(shape, kind="vegetated_or_other_wetland", oid=1):
    return {"object_id": oid, "category": kind, "analysis_wkb_hex": shape.wkb_hex,
            "raw_attributes": {"project_area": "synthetic", "project_area_name": "Fixture",
                               "project_partner": None, "delivery_date": 1369353600000,
                               "spring_imagery_year": "2010"}}


def calculate(wetlands, projects=None, parcels=None):
    return overlap([parcel()] if parcels is None else parcels, wetlands,
                   [mapped(box(-100, -100, 1000, 1000))] if projects is None else projects,
                   as_of=AS_OF)[0]


@pytest.mark.parametrize("wetlands,expected", [
    ([], 0), ([mapped(box(200, 200, 300, 300))], 0),
    ([mapped(box(100, 0, 200, 100))], 0), ([mapped(box(-1, -1, 101, 101))], 10_000),
    ([mapped(box(0, 0, 50, 100))], 5_000),
])
def test_zero_full_partial_and_boundary(wetlands, expected):
    result = calculate(wetlands)
    assert result["status"] == "complete"
    assert result["mapped_wetland_m2"] == expected
    assert result["mapped_wetland_percent"] == expected / 100
    if wetlands and expected == 0 and wetlands[0]["object_id"] == 1:
        assert all(r["boundary_only"] for r in result["source_contributors"])


def test_duplicate_overlapping_features_dissolve_without_double_counting():
    result = calculate([mapped(box(0, 0, 70, 100)), mapped(box(0, 0, 70, 100), oid=2),
                        mapped(box(50, 0, 90, 100), oid=3)])
    assert result["mapped_wetland_m2"] == 9_000
    assert result["mapped_wetland_percent"] == 90
    assert sum(r["intersected_m2_before_dissolve"] for r in result["source_contributors"]) == 18_000


def test_holes_multipart_and_input_preservation():
    shape = MultiPolygon([Polygon([(0, 0), (100, 0), (100, 100), (0, 100)],
                                  [[(20, 20), (30, 20), (30, 30), (20, 30)]]), box(200, 0, 210, 10)])
    parcels = [parcel(shape)]
    before = deepcopy(parcels)
    result = calculate([mapped(box(-1, -1, 500, 500))], parcels=parcels)
    assert result["mapped_wetland_m2"] == 10_000
    assert result["mapped_wetland_percent"] == 100
    assert parcels == before


@pytest.mark.parametrize("projects,status", [([], "missing"), ([mapped(box(0, 0, 50, 100))], "partial")])
def test_missing_or_partial_coverage_never_zero_or_complete_total(projects, status):
    result = calculate([], projects)
    assert result["coverage_status"] == status
    assert result["status"] == "held"
    assert result["mapped_wetland_m2"] is result["mapped_wetland_acres"] is None
    assert result["mapped_wetland_percent"] is None
    assert result["uncovered_m2"] > 0
    assert not shapely.from_wkb(result["uncovered_wkb_hex"]).is_empty


def test_independent_project_union_and_all_dates_preserved():
    projects = [mapped(box(-1, -1, 50, 101)), mapped(box(50, -1, 101, 101), oid=2)]
    projects[1]["raw_attributes"]["spring_imagery_year"] = "2013, 2014"
    result = calculate([], projects)
    assert result["coverage_status"] == "complete"
    assert [c["imagery_years"] for c in result["project_contexts"]] == [[2010], [2013, 2014]]
    assert result["project_contexts"][0]["delivery_date"] == "2013-05-24"
    assert sum(c["intersected_m2"] for c in result["project_contexts"]) == 10_000


def test_unknown_or_conflicting_classification_holds_totals():
    for sources in ([mapped(box(0, 0, 10, 10), "unknown")],
                    [mapped(box(0, 0, 20, 20)), mapped(box(10, 10, 30, 30), "deepwater", oid=2)]):
        result = calculate(sources)
        assert result["status"] == "held" and result["mapped_wetland_acres"] is None
        assert result["coverage_status"] == "complete"
        assert result["holds"]


def test_deepwater_riverine_and_open_water_separate():
    result = calculate([mapped(box(0, 0, 10, 10), "deepwater"),
                        mapped(box(10, 0, 20, 10), "riverine_mixed", oid=2),
                        mapped(box(20, 0, 30, 10), "open_water_wetland", oid=3)])
    assert result["mapped_wetland_m2"] == 100
    assert result["mapped_water_and_wetland_m2"] == 300
    assert result["observed_categories"]["deepwater"]["m2"] == 100


@pytest.mark.parametrize("label,code,expected", [
    ("Freshwater Forested/Shrub Wetland", "PFO1/SS1Cd", "vegetated_or_other_wetland"),
    ("Freshwater Forested Wetland", "PFO2Dq", "vegetated_or_other_wetland"),
    ("Freshwater Shrub Wetland", "PSS3Dq", "vegetated_or_other_wetland"),
    ("Freshwater Shrub/Emergent Wetland", "PSS1/EM1C", "vegetated_or_other_wetland"),
    ("Freshwater Forested Wetland", "PSS1C", "unknown"),
    ("Freshwater Shrub/Emergent Wetland", "PSS1C", "unknown"),
    ("Freshwater Emergent Wetland", "PEM1C", "vegetated_or_other_wetland"),
    ("Freshwater Pond", "PUBHx", "open_water_wetland"),
    ("Lake", "L1UBH", "deepwater"), ("Lake", "L2UBH", "open_water_wetland"),
    ("Lake", "L2EM1H", "vegetated_or_other_wetland"),
    ("Riverine", "R2UBH", "riverine_mixed"),
    ("Lake", "PFO1C", "unknown"), (None, "PFO1C", "unknown"),
    ("Other", "PUSC", "unknown"), ("Freshwater Pond", None, "unknown"),
    ("Freshwater Forested/Shrub Wetland", "PFORANDOM", "unknown"),
])
def test_versioned_explicit_inclusion_no_label_guess(label, code, expected):
    assert category({"wetland_type": label, "attribute": code}) == expected


def test_legacy_detailed_labels_remain_held_and_unreviewed_policy_refused():
    raw = {"wetland_type": "Freshwater Forested Wetland", "attribute": "PFO1A"}
    assert category(raw, LEGACY_INCLUSION_POLICY) == "unknown"
    assert category(raw, INCLUSION_POLICY) == "vegetated_or_other_wetland"
    with pytest.raises(ValueError, match="Unrecognized"):
        category(raw, {**INCLUSION_POLICY, "version": "future"})


@pytest.mark.parametrize("raw", [None, True, -99999999999999, 218330035200000, "2013"])
def test_invalid_unknown_project_dates_never_capture_date(raw):
    result = project_dates({"delivery_date": raw, "spring_imagery_year": "9999"}, AS_OF)
    assert result["raw_delivery_date"] == raw and result["delivery_date"] is None
    assert result["imagery_years"] is None


def test_real_bundled_grid_published_controls_and_roundtrip():
    alignment = WetlandAlignment()
    evidence = alignment.evidence()
    assert evidence["grid_sha256"] == "e6b5da45fea4fa0f050a5656e34379e81c5175e90bf535b8a8498dbdb1e4554c"
    assert evidence["network_enabled"] is False
    assert max(r["projection_error_metres"] for r in evidence["control_results"]) < 0.001
    assert max(r["grid_control_error_metres"] for r in evidence["control_results"]) < 0.25
    assert max(r["grid_control_error_metres"] for r in evidence["control_results"]) > 0.05
    projected = alignment.project(box(480000, 5040000, 480100, 5040100))
    assert projected.area == pytest.approx(10_000, rel=0.001)


def test_missing_changed_grid_controls_fail_closed(tmp_path):
    import shutil
    with pytest.raises(GeometryError, match="grid"):
        WetlandAlignment(tmp_path)
    shutil.copyfile(REFERENCE_ROOT / GRID_NAME, tmp_path / GRID_NAME)
    (tmp_path / "isanti_alignment_controls.json").write_text('{"controls":[]}', encoding="utf-8")
    with pytest.raises(GeometryError, match="control definitions"):
        WetlandAlignment(tmp_path)
    (tmp_path / GRID_NAME).write_bytes(b"changed")
    with pytest.raises(GeometryError, match="grid"):
        WetlandAlignment(tmp_path)


def test_query_groups_and_project_feature_provenance():
    alignment = WetlandAlignment()
    selected = [parcel(box(-100, -100, 100, 100), str(i)) for i in range(5)]
    groups = query_groups(selected, alignment)
    assert len(groups) == 2
    native = shapely.from_wkb(selected[0]["analysis_wkb_hex"])
    from shapely.ops import transform
    utm = transform(alignment.inverse, native)
    record = {"attributes": {"objectid": 1, "attribute": "PEM1C", "wetland_type": "Freshwater Emergent Wetland"},
              "geometry": esri_polygon(utm)}
    result = project_features([record], groups, alignment)[0]
    assert result["category"] == "vegetated_or_other_wetland"
    assert result["native_geometry_canonical_sha256"]
    assert result["analysis_vertices"] > 4
    assert result["area_convergence_m2"] < 0.01


def test_alignment_cannot_extrapolate_outside_grid():
    alignment = WetlandAlignment()
    with pytest.raises(ProjError):
        alignment.forward(0, 0)


@pytest.mark.parametrize("geometry", [None, {"rings": []}, {"curveRings": []},
    {"rings": [[[0, 0, 2], [0, 1, 2], [1, 0, 2], [0, 0, 2]]]},
    {"rings": [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]]},
    {"rings": [[[0, 0], [0, 1], [float("inf"), 1], [0, 0]]]},
])
def test_invalid_thematic_geometry_never_repaired(geometry):
    alignment = WetlandAlignment()
    with pytest.raises(GeometryError):
        project_features([{"attributes": {"objectid": 1}, "geometry": geometry}],
                         [esri_polygon(box(470000, 5030000, 490000, 5050000))], alignment)


def test_aggregate_projected_vertex_budget(monkeypatch):
    alignment = WetlandAlignment()
    group = esri_polygon(box(480000, 5040000, 480100, 5040100))
    monkeypatch.setattr("mn_land.wetlands.MAX_VERTICES", 10)
    with pytest.raises(GeometryError, match="Aggregate thematic"):
        project_features([{"attributes": {"objectid": 1}, "geometry": group}], [group], alignment)


def test_oversized_original_thematic_rings_hold_before_clipping():
    alignment = WetlandAlignment()
    group = esri_polygon(box(480000, 5040000, 480100, 5040100))
    with pytest.raises(GeometryError, match="oversized rings"):
        project_features([{"attributes": {"objectid": 1},
                           "geometry": {"rings": [[]] * 10_001}}], [group], alignment)
