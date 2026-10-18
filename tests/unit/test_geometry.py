"""Synthetic geometry controls; optional GIS extra is installed by full CI."""

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("shapely")
pytest.importorskip("pyproj")
from pyproj import CRS

from mn_land.counties.isanti.geometry import ANALYSIS, native_crs
from mn_land.geometry import ACRE_M2, GeometryAnalysis, GeometryError, polygon

FIXTURE = json.loads((Path(__file__).parents[1] / "fixtures/geometry.json").read_text())


@pytest.fixture
def engine():
    return GeometryAnalysis(native_crs(FIXTURE["spatialReference"]), ANALYSIS)


def test_known_foot_square_and_roundtrip(engine):
    result, original = engine.project(FIXTURE["square"], 25.5)
    # Independent native plane control: 1 million US survey feet squared.
    # County conformal grid vs adjusted-ellipsoid area differs slightly.
    control = 1_000_000 * (1200 / 3937) ** 2
    assert result["measured_m2"] == pytest.approx(control, rel=0.0001)
    assert result["measured_acres"] == result["measured_m2"] / ACRE_M2
    assert result["roundtrip_error_metres"] < 0.001
    assert result["convergence_m2"] < 0.01
    assert result["ellipsoidal_control_m2"] == pytest.approx(result["measured_m2"], abs=0.01)
    assert original.area == 1_000_000
    assert result["deeded_discrepancy"] is True
    assert result["new_gis_deeded_acres"] == 25.5
    assert result["difference_acres"] < 0
    assert not result["repaired"]
    evidence = engine.evidence()
    assert evidence["grids"] == []
    assert evidence["transform_accuracy_metres"] == 0
    assert evidence["network_enabled"] is False
    assert "6378411.321" in evidence["native_wkt2"]
    assert "6378411.321" in evidence["analysis_wkt2"]
    assert "xy_in=us-ft" in evidence["pipeline"]
    assert evidence["native_unit_to_metres"] == pytest.approx(1200 / 3937)
    assert len(evidence["proj_database_sha256"]) == 64


def test_holes_multipart_no_mutation(engine):
    data = deepcopy(FIXTURE["square"])
    data["rings"] += [FIXTURE["hole"], FIXTURE["second_shell"]]
    before = deepcopy(data)
    result, shape = engine.project(data, None)
    assert data == before
    assert result["parts"] == 2 and result["holes"] == 1
    assert shape.area == 1_210_000
    assert result["measured_m2"] == pytest.approx(1_210_000 * (1200 / 3937) ** 2, rel=0.0001)
    assert result["difference_acres"] is None
    assert result["deeded_discrepancy"] is None


@pytest.mark.parametrize("geometry", [
    None, {}, {"rings": []}, {"rings": [[]]}, {"rings": [[[0, 0], [1, 0], [1, 1]]]},
    {"rings": [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]]},
    {"rings": [[[0, 0], [0, 0], [0, 0], [0, 0]]]},
    {"rings": [[[0, 0], [0, 1], [1, float("nan")], [0, 0]]]},
    {"rings": [[[0, 0], [0, 1], [float("inf"), 0], [0, 0]]]},
    {"rings": [[[0, 0], [0, True], [1, 0], [0, 0]]]},
    {"rings": [[[0, 0, 2], [0, 1, 2], [1, 0, 2], [0, 0, 2]]]},
    {"curveRings": [[[0, 0], {"c": [[1, 1], [0, 1]]}, [0, 0]]]},
    {"rings": [], "hasM": True}, {"paths": []},
    {"rings": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},  # orphan CCW hole
])
def test_bad_polygons_held_not_repaired(geometry):
    with pytest.raises(GeometryError):
        polygon(geometry, ANALYSIS)


def test_overlapping_shells_and_duplicate_rings_rejected():
    for second in [FIXTURE["square"]["rings"][0],
                   [[450500, 200000], [450500, 201000], [451500, 201000],
                    [451500, 200000], [450500, 200000]]]:
        with pytest.raises(GeometryError):
            polygon({"rings": [FIXTURE["square"]["rings"][0], second]}, ANALYSIS)


def test_vertex_ring_and_densification_budgets(engine):
    with pytest.raises(GeometryError, match="vertex budget"):
        polygon(FIXTURE["square"], replace(ANALYSIS, max_vertices=4))
    with pytest.raises(GeometryError, match="oversized rings"):
        polygon(FIXTURE["square"], replace(ANALYSIS, max_rings=0))
    engine.policy = replace(ANALYSIS, max_vertices=100)
    with pytest.raises(GeometryError, match="Densified vertex"):
        engine.project(FIXTURE["square"], None)


@pytest.mark.parametrize("sr", [None, {}, {"wkid": 3857}, {"wkid": True},
    {"wkid": 103736, "latestWkid": 26915}, {"wkid": 103736, "vcsWkid": 5703},
    {"wkid": 103736, "wkt": CRS(26915).to_wkt()},
])
def test_unknown_conflicting_or_vertical_crs_held(sr):
    with pytest.raises(GeometryError):
        native_crs(sr)


def test_full_wkt_must_match_code():
    expected = native_crs(FIXTURE["spatialReference"])
    assert native_crs({"wkid": 103736, "wkt": expected.to_wkt()}).equals(expected)


@pytest.mark.parametrize("crs", [CRS(4326), CRS(4979)])
def test_geographic_area_rejected(crs):
    with pytest.raises(GeometryError):
        GeometryAnalysis(crs, ANALYSIS)


def test_wrong_axes_and_nonlocal_coordinates_held(engine):
    bad = deepcopy(FIXTURE["square"])
    bad["rings"] = [[[y, x] for x, y in ring] for ring in bad["rings"]]
    with pytest.raises(GeometryError):
        engine.project(bad, None)
    with pytest.raises(GeometryError):
        engine.project({"rings": [[[0, 0], [0, 1000], [1000, 1000], [1000, 0], [0, 0]]]}, None)


@pytest.mark.parametrize("deeded", [-1, True, float("inf"), "25"])
def test_invalid_deeded_area_not_substituted(engine, deeded):
    with pytest.raises(GeometryError, match="deeded"):
        engine.project(FIXTURE["square"], deeded)


def test_precision_and_deeded_tolerance(engine):
    first, _ = engine.project(FIXTURE["square"], None)
    measured = first["measured_acres"]
    assert engine.project(FIXTURE["square"], measured)[0]["deeded_discrepancy"] is False
    assert engine.project(FIXTURE["square"], measured * 1.01)[0]["deeded_discrepancy"] is False
    assert engine.project(FIXTURE["square"], measured * 1.1)[0]["deeded_discrepancy"] is True
    assert engine.project(FIXTURE["square"], 0)[0]["deeded_discrepancy"] is True


def test_missing_best_grid_or_ballpark_fails_closed(monkeypatch):
    class Group:
        best_available = False
        transformers = ()
    monkeypatch.setattr("mn_land.geometry.TransformerGroup", lambda *a, **k: Group())
    with pytest.raises(GeometryError, match="Exact unique"):
        GeometryAnalysis(native_crs(FIXTURE["spatialReference"]), ANALYSIS)


def test_transform_failure_does_not_become_zero_area(engine):
    class Bad:
        def transform(self, *args, **kwargs):
            return float("inf"), float("inf")
    engine.geographic = Bad()
    with pytest.raises(GeometryError):
        engine.project(FIXTURE["square"], None)


def test_approximate_operation_is_not_accepted(monkeypatch):
    from types import SimpleNamespace
    group = SimpleNamespace(best_available=True,
                            transformers=[SimpleNamespace(accuracy=1, description="ballpark")])
    monkeypatch.setattr("mn_land.geometry.TransformerGroup", lambda *a, **k: group)
    with pytest.raises(GeometryError, match="approximate"):
        GeometryAnalysis(native_crs(FIXTURE["spatialReference"]), ANALYSIS)
