"""Synthetic planar controls and actual offline FEMA geographic/grid controls."""
from copy import deepcopy
from datetime import date

import pytest

pytest.importorskip("shapely")
pytest.importorskip("pyproj")
import shapely
from pyproj.exceptions import ProjError
from shapely.geometry import MultiPolygon, Polygon, box

from mn_land.counties.isanti.flood_crs import FloodAlignment
from mn_land.floods import (
    PROCESSING_POLICY,
    date_observation,
    overlap,
    panel_context,
    project_features,
    query_groups,
)
from mn_land.geometry import GeometryError
from mn_land.sources.fema_nfhl import LAYERS, category, study_id
from mn_land.wetlands import esri_polygon

AS_OF = date(2026, 10, 19)
EFFECTIVE = 1067990400000


def parcel(shape=None, identity="synthetic"):
    shape = box(0, 0, 100, 100) if shape is None else shape
    return {"parcel_id": identity, "object_id": 1, "analysis_wkb_hex": shape.wkb_hex,
            "saved_deeded_acres": "3", "new_gis_deeded_acres": 3.0, "deeded_discrepancy": True}


def feature(layer, shape=None, *, oid=1, study="27059C", zone="X",
            subtype="AREA OF MINIMAL FLOOD HAZARD", sfha="F"):
    shape = box(-10, -10, 110, 110) if shape is None else shape
    raw = dict.fromkeys(LAYERS[layer].names)
    raw.update(OBJECTID=oid)
    if layer == "availability": raw.update(STUDY_ID=study)
    else: raw.update(DFIRM_ID=study)
    if layer == "zones": raw.update(FLD_ZONE=zone, ZONE_SUBTY=subtype, SFHA_TF=sfha)
    if layer == "panels": raw.update(FIRM_PAN=study+"0150D", EFF_DATE=EFFECTIVE,
        SCALE="24000", PANEL_TYP="Countywide, Panel Printed")
    if layer == "revisions": raw.update(CASE_NO="04-05-TESTP", EFF_DATE=1144800000000, STATUS="Effective")
    return {"layer": layer, "object_id": oid, "raw_attributes": raw, "analysis_wkb_hex": shape.wkb_hex}


def studies():
    return [{"OBJECTID": 1, "DFIRM_ID": "27059C", "INDX_EFFDT": 218330035200000,
             "DBREV_DT": None}]


def calculate(zones=None, *, others=None, parcels=None, metadata=None):
    records = [feature("zones")] if zones is None else zones
    records += [feature("availability"), feature("panels")] if others is None else others
    return overlap([parcel()] if parcels is None else parcels, records,
                   studies() if metadata is None else metadata, as_of=AS_OF)


@pytest.mark.parametrize("end,expected", [(0, 0), (50, 5000), (100, 10000)])
def test_zero_partial_full_sfha_with_independent_complete_coverage(end, expected):
    zones = []
    if end:
        zones.append(feature("zones", box(0, 0, end, 100), zone="AE", subtype=None, sfha="T"))
    if end < 100:
        zones.append(feature("zones", box(end, 0, 100, 100), oid=2))
    result = calculate(zones)[0]
    assert result["status"] == "complete"
    assert all(c["status"] == "complete" for c in result["coverage"].values())
    assert result["metrics"]["sfha"]["m2"] == expected
    assert result["metrics"]["sfha"]["percent"] == expected / 100
    assert result["metrics"]["minimal_hazard"]["m2"] == 10000 - expected


def test_boundary_contact_is_zero_not_positive_constraint():
    result = calculate([feature("zones"), feature("zones", box(100, 0, 200, 100),
        oid=2, zone="A", subtype=None, sfha="T")])[0]
    assert result["metrics"]["sfha"]["m2"] == 0
    assert any(c["boundary_only"] for c in result["source_contexts"])


def test_holes_multipart_duplicate_union_and_no_mutation():
    shape = MultiPolygon([Polygon([(0, 0), (100, 0), (100, 100), (0, 100)],
        [[(20, 20), (30, 20), (30, 30), (20, 30)]]), box(200, 0, 210, 10)])
    inputs = [parcel(shape)]
    original = deepcopy(inputs)
    zones = [feature("zones", box(-1, -1, 500, 500), oid=i, zone="AE", subtype=None, sfha="T")
             for i in (1, 2)]
    result = calculate(zones, parcels=inputs, others=[feature("availability", box(-2, -2, 501, 501)),
        feature("panels", box(-2, -2, 501, 501))])[0]
    assert result["metrics"]["sfha"]["m2"] == 10_000
    assert result["metrics"]["sfha"]["percent"] == 100
    assert inputs == original


def test_floodway_subset_and_x_subtypes_never_double_add():
    zones = [feature("zones", box(0, 0, 20, 100), zone="AE", subtype="FLOODWAY", sfha="T"),
        feature("zones", box(20, 0, 50, 100), oid=2, zone="AE", subtype=None, sfha="T"),
        feature("zones", box(50, 0, 80, 100), oid=3, subtype="0.2 PCT ANNUAL CHANCE FLOOD HAZARD"),
        feature("zones", box(80, 0, 100, 100), oid=4)]
    result = calculate(zones)[0]
    assert result["metrics"]["sfha"]["m2"] == 5000
    assert result["metrics"]["floodway"]["m2"] == 2000
    assert result["metrics"]["annual_chance_0_2pct"]["m2"] == 3000
    assert result["metrics"]["minimal_hazard"]["m2"] == 2000
    assert len(result["observed_categories"]) == 4


@pytest.mark.parametrize("missing", ["availability", "panels", "zones"])
def test_missing_evidence_never_zero(missing):
    zones = [] if missing == "zones" else [feature("zones")]
    others = [feature(k) for k in ("availability", "panels") if k != missing]
    result = calculate(zones, others=others)[0]
    assert result["status"] == "held"
    assert all(m is None for m in result["metrics"].values())
    assert result["coverage"]["study_matched"]["uncovered"]["m2"] == 10000


def test_partial_or_mismatched_study_coverage_not_filled():
    others = [feature("availability", box(0, 0, 50, 100)), feature("panels")]
    result = calculate(others=others)[0]
    assert result["coverage"]["study_matched"]["status"] == "partial"
    assert result["metrics"]["sfha"] is None
    others[0] = feature("availability", study="27095C")
    result = calculate(others=others, metadata=studies()+[{"DFIRM_ID": "27095C"}])[0]
    assert result["coverage"]["availability"]["status"] == "complete"
    assert result["coverage"]["study_matched"]["status"] == "missing"
    assert result["status"] == "held"


def test_unknown_and_conflicting_categories_hold_not_pick_a_winner():
    for zones in ([feature("zones", subtype=None)],
                  [feature("zones"), feature("zones", oid=2, zone="AE", subtype=None, sfha="T")]):
        result = calculate(zones)[0]
        assert result["status"] == "held"
        assert result["metrics"]["sfha"] is None
        assert result["holds"]


def test_revision_footprints_context_only_and_cases_distinct():
    others = [feature("availability"), feature("panels"),
              feature("revisions", box(0, 0, 30, 100)),
              feature("revisions", box(50, 0, 80, 100), oid=2)]
    result = calculate(others=others)[0]
    assert result["status"] == "complete" and result["metrics"]["sfha"]["m2"] == 0
    assert result["distinct_revision_cases"] == ["04-05-TESTP"]
    contexts = [c for c in result["source_contexts"] if c["layer"] == "revisions"]
    assert len(contexts) == 2 and all(c["used_as_hazard_geometry"] is False for c in contexts)


@pytest.mark.parametrize("bad", [None, "Preliminary", "Pending"])
def test_unverified_revision_status_holds_affected_parcel_only(bad):
    revision = feature("revisions", box(0, 0, 50, 100))
    revision["raw_attributes"]["STATUS"] = bad
    others = [feature("availability", box(-1, -1, 401, 401)),
              feature("panels", box(-1, -1, 401, 401)), revision]
    rows = calculate([feature("zones", box(-1, -1, 401, 401))], others=others,
        parcels=[parcel(), parcel(box(200, 200, 300, 300), "other")])
    assert rows[0]["status"] == "held" and rows[1]["status"] == "complete"


@pytest.mark.parametrize("field,value", [("EFF_DATE", None), ("EFF_DATE", 218330035200000),
    ("EFF_DATE", True), ("PANEL_TYP", "Countywide, Panel Not Printed"),
    ("FIRM_PAN", "27095C0150D"), ("DFIRM_ID", None)])
def test_unverified_panel_date_type_or_identity_holds(field, value):
    panel = feature("panels")
    panel["raw_attributes"][field] = value
    result = calculate(others=[feature("availability"), panel])[0]
    assert result["status"] == "held" and result["metrics"]["sfha"] is None


def test_raw_study_8888_null_dates_never_become_panel_or_capture_date():
    result = calculate()[0]
    study = result["study_contexts"][0]
    assert study["index_effective_date"]["raw"] == 218330035200000
    assert study["index_effective_date"]["decoded_date"] == "8888-08-08"
    assert study["index_effective_date"]["date"] is None
    assert study["database_revision_date"]["date"] is None
    assert result["status"] == "complete"  # independently valid panel dates remain separate
    panel = next(c for c in result["source_contexts"] if c["layer"] == "panels")
    assert panel["effective_date"]["date"] == "2003-11-05"
    assert result["warnings"]


@pytest.mark.parametrize("value", [None, True, "2003", -99999999999999, 218330035200000, 1e100])
def test_unknown_invalid_future_date(value):
    observed = date_observation(value, AS_OF)
    assert observed["raw"] == value and observed["date"] is None


@pytest.mark.parametrize("raw,label", [
    ({"FLD_ZONE": "AE", "ZONE_SUBTY": "FLOODWAY", "SFHA_TF": "T"}, "sfha_floodway"),
    ({"FLD_ZONE": "A", "ZONE_SUBTY": None, "SFHA_TF": "T"}, "sfha_other"),
    ({"FLD_ZONE": "AE", "ZONE_SUBTY": None, "SFHA_TF": "F"}, "unknown"),
    ({"FLD_ZONE": "D", "ZONE_SUBTY": None, "SFHA_TF": "F"}, "unknown"),
    ({"FLD_ZONE": "X", "ZONE_SUBTY": None, "SFHA_TF": "F"}, "unknown"),
    ({"FLD_ZONE": None, "ZONE_SUBTY": "FLOODWAY", "SFHA_TF": "T"}, "unknown"),
])
def test_category_requires_consistent_explicit_fields(raw, label):
    assert category(raw) == label


@pytest.mark.parametrize("identity", [None, "27059C' OR 1=1", "27059", True, "abcdef", "27059c"])
def test_study_identity_not_guessed_or_sql_injected(identity):
    assert study_id(identity) is None


def test_missing_ambiguous_study_metadata_held():
    for metadata in ([], studies()*2):
        assert calculate(metadata=metadata)[0]["status"] == "held"


def test_scale_raw_null_invalid_not_inferred():
    raw = feature("panels")["raw_attributes"]
    for value in (None, "", "24000 feet", "0", 24000):
        raw["SCALE"] = value
        assert panel_context(raw, AS_OF)["scale_denominator"] is None


def test_fema_geographic_alignment_real_grid_controls_and_native_roundtrip():
    alignment = FloodAlignment()
    geog = box(-93.31, 45.54, -93.30, 45.55)
    projected = alignment.project(geog)
    assert projected.area > 800000
    evidence = alignment.evidence()
    assert evidence["network_enabled"] is False and evidence["source_units"].startswith("degree")
    assert "utm_projection_pipeline" not in evidence
    assert max(r["grid_control_error_metres"] for r in evidence["control_results"]) < .25
    assert max(r["grid_control_error_metres"] for r in evidence["control_results"]) > .05
    with pytest.raises(ProjError): alignment.forward(0, 0)


def test_query_groups_and_degree_densification_metre_area():
    alignment = FloodAlignment()
    p = parcel(box(-100, -100, 100, 100))
    groups = query_groups([p], alignment)
    assert all(-94 < point[0] < -92 for ring in groups[0]["rings"] for point in ring)
    raw = feature("zones")["raw_attributes"]
    raw["OBJECTID"] = 1
    native = {"attributes": raw, "geometry": deepcopy(groups[0])}
    before = deepcopy(native)
    result = project_features([native], "zones", groups, alignment)[0]
    assert result["analysis_vertices"] > 4
    assert result["area_convergence_m2"] < .01
    assert shapely.from_wkb(result["analysis_wkb_hex"]).area > 40000
    assert native == before


@pytest.mark.parametrize("bad", [[], [parcel()]*2, [parcel(identity=str(i)) for i in range(16)]])
def test_selection_budget_or_duplicates_refused(bad):
    with pytest.raises(GeometryError): query_groups(bad, FloodAlignment())


@pytest.mark.parametrize("geometry", [None, {"rings": []}, {"curveRings": []},
    {"rings": [[[-93, 45, 1], [-93, 46, 1], [-92, 45, 1], [-93, 45, 1]]]},
    {"rings": [[[-93, 45], [-92, 46], [-93, 46], [-92, 45], [-93, 45]]]},
    {"rings": [[[-93, 45], [-93, 46], [float("inf"), 46], [-93, 45]]]},
    {"rings": [[]] * 10_001},
])
def test_invalid_oversized_curved_extra_dimensions_never_repaired(geometry):
    alignment = FloodAlignment()
    group = esri_polygon(box(-93.4, 45.5, -93.2, 45.6))
    with pytest.raises(GeometryError):
        project_features([{"attributes": feature("zones")["raw_attributes"], "geometry": geometry}],
                         "zones", [group], alignment)


def test_projected_vertex_budgets_and_missing_grid(monkeypatch, tmp_path):
    with pytest.raises(GeometryError, match="grid"):
        FloodAlignment(tmp_path)
    alignment = FloodAlignment()
    group = esri_polygon(box(-93.31, 45.54, -93.30, 45.55))
    monkeypatch.setitem(PROCESSING_POLICY, "analysis_vertices_per_layer", 5)
    with pytest.raises(GeometryError, match="aggregate"):
        project_features([{"attributes": feature("zones")["raw_attributes"], "geometry": group}],
                         "zones", [group], alignment)
