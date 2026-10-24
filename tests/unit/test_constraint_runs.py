"""Genuine pinned completion, offline reproduction and no implicit latest input."""
import json
from copy import deepcopy
from dataclasses import replace

import pytest

pytest.importorskip("shapely")
pytest.importorskip("pyproj")

from test_flood_ingestion import Transport as FloodTransport
from test_flood_ingestion import feature as flood_feature
from test_geometry_acquisition import Transport as ParcelTransport
from test_wetland_ingestion import Transport as WetlandTransport
from test_wetland_ingestion import feature as wetland_feature

from mn_land.cli import build_parser, main
from mn_land.constraint_runs import analyze_constraints, compatible
from mn_land.counties.isanti.flood_crs import FloodAlignment
from mn_land.counties.isanti.wetland_crs import WetlandAlignment
from mn_land.flood_runs import acquire_floods
from mn_land.floods import query_groups as flood_groups
from mn_land.geometry import GeometryError, polygon
from mn_land.geometry_runs import acquire_geometry
from mn_land.provenance import sha256_file
from mn_land.runs import RunValidationError, read_artifact_json, read_json, validate_run
from mn_land.sources.dnr_nwi import NWI, PROJECTS
from mn_land.sources.fema_nfhl import LAYERS
from mn_land.wetland_runs import acquire_wetlands
from mn_land.wetlands import query_groups as wetland_groups


def rehash(path, name):
    completion = read_json(path / "completion.json")
    entry = next(e for e in completion["artifacts"] if e["path"] == name)
    entry.update(bytes=(path / name).stat().st_size, sha256=sha256_file(path / name))
    (path / "completion.json").write_text(json.dumps(completion), encoding="utf-8")


def test_genuine_combination_replay_portable_holds_and_semantic_tamper(viewer_data, tmp_path):
    _, _, review = viewer_data()
    geometry = acquire_geometry(review, view="prior", output_root=tmp_path / "g", transport=ParcelTransport())
    parcels = read_artifact_json(validate_run(geometry, "parcel_geometry"), "polygons.json")
    alignment = WetlandAlignment()
    window = polygon(wetland_groups(parcels, alignment)[0], alignment.engine.policy)
    wet = acquire_wetlands(geometry, output_root=tmp_path / "w", transport=WetlandTransport({
        NWI.url: [wetland_feature(NWI, shape=window)], PROJECTS.url: [wetland_feature(PROJECTS, shape=window)]}))
    alignment = FloodAlignment()
    window = polygon(flood_groups(parcels, alignment)[0], alignment.engine.policy)
    flood = acquire_floods(geometry, output_root=tmp_path / "f", transport=FloodTransport({
        s.url: [] if name == "revisions" else [flood_feature(s, window)] for name, s in LAYERS.items()}))
    baseline = {p: sha256_file(p) for root in (geometry, wet, flood) for p in root.rglob("*") if p.is_file()}
    result = analyze_constraints(wet, flood, output_root=tmp_path / "c")
    valid = validate_run(result, "constraint_analysis")
    row = read_artifact_json(valid, "constraints.json")[0]
    assert row["status"] == "complete"
    assert row["estimated_usable"]["m2"] == pytest.approx(0, abs=.01)
    assert row["shared_water_sfha"]["m2"] == pytest.approx(row["measured_parcel"]["m2"], abs=.01)
    assert valid.manifest["network_requests"] == 0
    assert valid.manifest["lineage"]["inputs"]["wetlands"]["source_policy"]["version"].endswith("v2")
    assert main(["validate-constraints", "--snapshot", str(result)]) == 0
    assert all(sha256_file(p) == digest for p, digest in baseline.items())

    wvalid, fvalid = validate_run(wet, "wetland_analysis"), validate_run(flood, "flood_analysis")
    for field in ("analysis", "grid_sha256", "controls_canonical_sha256"):
        manifest = deepcopy(fvalid.manifest)
        manifest["alignment"][field] = "incompatible"
        with pytest.raises(GeometryError): compatible(wvalid, replace(fvalid, manifest=manifest))
    completion = deepcopy(fvalid.completion)
    completion["sources"][0]["completion_sha256"] = "0" * 64
    with pytest.raises(GeometryError): compatible(wvalid, replace(fvalid, completion=completion))
    with pytest.raises(GeometryError): analyze_constraints(wet, flood, output_root=wet / "bad-root")

    held = acquire_floods(geometry, output_root=tmp_path / "h", transport=FloodTransport({s.url: [] for s in LAYERS.values()}))
    held_result = analyze_constraints(wet, held, output_root=tmp_path / "c")
    held_valid = validate_run(held_result, "constraint_analysis")
    assert held_valid.manifest["summary"]["held_results"] == 1
    assert read_artifact_json(held_valid, "constraints.json")[0]["estimated_usable"] is None
    # Pinned evidence works even after all three original inputs move away.
    for path in (geometry, wet, flood): path.rename(path.with_name(path.name + "-moved"))
    validate_run(result, "constraint_analysis")
    original_completion = (result / "completion.json").read_bytes()
    for name, field, value in (("constraints.json", "estimated_usable", {"acres": 999}),
                              ("manifest.json", "policy", {"version": "silent-new-policy"}),
                              ("manifest.json", "lineage_sha256", "0" * 64),
                              ("manifest.json", "summary", {})):
        original = (result / name).read_bytes()
        payload = read_json(result / name)
        (payload[0] if isinstance(payload, list) else payload)[field] = value
        (result / name).write_text(json.dumps(payload), encoding="utf-8")
        rehash(result, name)
        with pytest.raises(RunValidationError): validate_run(result, "constraint_analysis")
        (result / name).write_bytes(original)
        (result / "completion.json").write_bytes(original_completion)


@pytest.mark.parametrize("args", [[], ["--wetland-snapshot", "explicit"], ["--flood-snapshot", "explicit"]])
def test_both_source_snapshots_required_no_latest(args):
    with pytest.raises(SystemExit):
        build_parser().parse_args(["analyze-constraints", "--county", "isanti", *args])


def test_old_failed_incomplete_or_wrong_kind_not_accepted(tmp_path):
    assert main(["validate-constraints", "--snapshot", str(tmp_path)]) == 2
    assert main(["analyze-constraints", "--county", "isanti", "--wetland-snapshot", str(tmp_path),
                 "--flood-snapshot", str(tmp_path)]) == 2
    assert not (tmp_path / "latest.json").exists()


def test_historical_graph_depth_guard_unchanged(tmp_path):
    with pytest.raises(RunValidationError): validate_run(tmp_path, "flood_analysis", depth=5)
    with pytest.raises(RunValidationError): validate_run(tmp_path, "constraint_analysis", depth=6)
