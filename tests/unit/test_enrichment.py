"""Canonical serialization, source-bound map review and genuine portable publication."""
import csv
import io
import json
from copy import deepcopy
from datetime import UTC, datetime

import pytest

from mn_land.cli import build_parser, main
from mn_land.enrichment import CSV_FIELDS, CSV_NULL, publish_enrichment, serialize, validate_review
from mn_land.provenance import sha256_file
from mn_land.runs import RunValidationError, read_artifact_json, read_json, validate_run, write_json
from mn_land.suitability_service import SuitabilityObservation, SuitabilityService
from mn_land.worklists import canonical


def payload(*, held=False):
    record = {name: None for name in CSV_FIELDS if name != "context"}
    record.update(parcel_id="020010200", status="held" if held else "complete", measured_acres=25.5,
                  mapped_wetland_acres=0, estimated_remaining_acres=None if held else 25.5,
                  holds=["floods:unverified_panel_type_identity_or_effective_date"] if held else [],
                  wetland_project_contexts=[], flood_panel_contexts=[], flood_study_contexts=[])
    return {"schema_version": 1, "context": {"csv_import_note": "Import parcel IDs as text",
        "map_review": {"method": "synthetic_fixture", "findings": "Synthetic map review"},
        "constraint_run_id": "synthetic", "constraint_completion_sha256": "a"*64,
        "source_dates": {}, "constraint_policy": {}, "warnings": ["Synthetic, not buildability"]},
        "records": [record]}


@pytest.mark.parametrize("held", [False, True])
def test_csv_json_roundtrip_ids_dates_zero_null_context_and_order(held):
    original = payload(held=held)
    original["context"]["source_dates"] = {"imagery": 2010, "retrieved": "2026-10-20", "index": None}
    before = deepcopy(original)
    json_body = serialize(original, "json")
    assert json.loads(json_body) == original
    csv_body = serialize(original, "csv")
    rows = list(csv.DictReader(io.StringIO(csv_body.decode())))
    assert tuple(rows[0]) == CSV_FIELDS
    assert rows[0]["parcel_id"] == "020010200"
    assert rows[0]["mapped_wetland_acres"] == "0"
    assert rows[0]["sfha_acres"] == CSV_NULL
    assert rows[0]["estimated_remaining_acres"] == (CSV_NULL if held else "25.5")
    assert json.loads(rows[0]["context"]) == original["context"]
    assert json.loads(rows[0]["holds"]) == original["records"][0]["holds"]
    assert original == before


@pytest.mark.parametrize("value", ["=1+1", "+1", "-1", "@SUM(A1)", " \t=1", "bad\rtext", CSV_NULL])
def test_scalar_csv_formula_control_and_null_marker_ambiguity_refused(value):
    doc = payload()
    doc["records"][0]["saved_deeded_acres"] = value
    with pytest.raises(RunValidationError): serialize(doc, "csv")


def test_export_budget_empty_context_and_unknown_format(monkeypatch):
    import mn_land.enrichment as module
    doc = payload()
    doc["records"] = []
    assert json.loads(serialize(doc, "json"))["context"]
    assert len(list(csv.reader(io.StringIO(serialize(doc, "csv").decode())))) == 1
    with pytest.raises(RunValidationError): serialize(doc, "xlsx")
    monkeypatch.setattr(module, "MAX_EXPORT_BYTES", 1)
    with pytest.raises(RunValidationError): serialize(payload(), "json")


def report(source, path):
    write_json(path / "map-evidence.json", {"synthetic": True, "not_an_actual_map": True})
    return {"schema_version": 1, "constraint_completion_sha256": source.completion_sha256,
            "reviewed_at": datetime.now(UTC).isoformat(), "method": "synthetic_fixture",
            "findings": "Synthetic review fixture, not independent map verification",
            "samples": [{"parcel_id": "020010200", "finding": "Synthetic sample",
                         "urls": ["https://wetland-finder.dnr.state.mn.us/"]}],
            "evidence": [{"file": "map-evidence.json", "sha256": sha256_file(path / "map-evidence.json")}]}


@pytest.mark.parametrize("change", ["hash", "date", "method", "sample", "duplicates", "url", "evidence", "filename"])
def test_review_source_date_identity_url_and_evidence_guards(tmp_path, monkeypatch, change):
    from types import SimpleNamespace

    import mn_land.enrichment as module
    source = SimpleNamespace(completion_sha256="a"*64)
    monkeypatch.setattr(module, "read_artifact_json", lambda *args: [{"parcel_id": "020010200"}])
    doc = report(source, tmp_path)
    if change == "hash": doc["constraint_completion_sha256"] = "b"*64
    if change == "date": doc["reviewed_at"] = "2999-01-01T00:00:00+00:00"
    if change == "method": doc["method"] = "guessed"
    if change == "sample": doc["samples"][0]["parcel_id"] = "other"
    if change == "duplicates": doc["samples"] *= 2
    if change == "url": doc["samples"][0]["urls"] = ["https://hazards.fema.gov.evil.test/"]
    if change == "evidence": doc["evidence"][0]["sha256"] = "b"*64
    if change == "filename": doc["evidence"][0]["file"] = "../map-evidence.json"
    with pytest.raises(RunValidationError): validate_review(doc, source, tmp_path)


def test_explicit_publication_inputs_and_no_latest_fallback(tmp_path):
    with pytest.raises(SystemExit): build_parser().parse_args(["publish-suitability", "--county", "isanti"])
    assert main(["validate-suitability", "--snapshot", str(tmp_path)]) == 2
    assert not (tmp_path / "latest.json").exists()


def test_genuine_publication_source_binding_tamper_replay_and_download(viewer_data, tmp_path):
    pytest.importorskip("shapely")
    pytest.importorskip("pyproj")
    from test_flood_ingestion import Transport as FloodTransport
    from test_flood_ingestion import feature as flood_feature
    from test_geometry_acquisition import Transport as ParcelTransport
    from test_wetland_ingestion import Transport as WetlandTransport
    from test_wetland_ingestion import feature as wetland_feature

    from mn_land.constraint_runs import analyze_constraints
    from mn_land.counties.isanti.flood_crs import FloodAlignment
    from mn_land.counties.isanti.wetland_crs import WetlandAlignment
    from mn_land.flood_runs import acquire_floods
    from mn_land.floods import query_groups as flood_groups
    from mn_land.geometry import polygon
    from mn_land.geometry_runs import acquire_geometry
    from mn_land.parcel_table import TableFilters
    from mn_land.review_service import ReviewService, SnapshotKey
    from mn_land.sources.dnr_nwi import NWI, PROJECTS
    from mn_land.sources.fema_nfhl import LAYERS
    from mn_land.wetland_runs import acquire_wetlands
    from mn_land.wetlands import query_groups as wetland_groups

    root, _, review = viewer_data()
    geometry = acquire_geometry(review, view="prior", output_root=tmp_path/"g", transport=ParcelTransport())
    parcels = read_artifact_json(validate_run(geometry, "parcel_geometry"), "polygons.json")
    a = WetlandAlignment()
    window = polygon(wetland_groups(parcels, a)[0], a.engine.policy)
    wet = acquire_wetlands(geometry, output_root=tmp_path/"w", transport=WetlandTransport({
        NWI.url: [], PROJECTS.url: [wetland_feature(PROJECTS, shape=window)]}))
    a = FloodAlignment()
    window = polygon(flood_groups(parcels, a)[0], a.engine.policy)
    flood = acquire_floods(geometry, output_root=tmp_path/"f", transport=FloodTransport({s.url:
        [] if name == "revisions" else [flood_feature(s, window)] for name, s in LAYERS.items()}))
    constraint = analyze_constraints(wet, flood, output_root=tmp_path/"c")
    source = validate_run(constraint, "constraint_analysis")
    write_json(tmp_path/"review.json", report(source, tmp_path))
    output = publish_enrichment(constraint, tmp_path/"review.json", output_root=root/"isanti/enrichment")
    valid = validate_run(output, "suitability_enrichment")
    assert valid.manifest["summary"] == {"parcels": 1, "complete": 1, "held": 0}
    dataset = ReviewService(root).load_parcels(SnapshotKey("review", review.name))
    service = SuitabilityService(root)
    assert output.name in service.catalog()
    observation = service.load(output.name, dataset)
    assert isinstance(observation, SuitabilityObservation)
    assert observation.record("02.001.0200")["mapped_wetland_acres"] == 0
    preview = service.prepare(observation, dataset, TableFilters(view="prior"), scope="filtered")
    assert len(json.loads(service.download(preview, "json"))["records"]) == 1
    assert main(["validate-suitability", "--snapshot", str(output)]) == 0
    original = (output/"enrichment.json").read_bytes()
    completion_bytes = (output/"completion.json").read_bytes()
    doc = read_json(output/"enrichment.json")
    doc["records"][0]["estimated_remaining_acres"] = 999
    write_json(output/"enrichment.json", doc)
    completion = read_json(output/"completion.json")
    entry = next(e for e in completion["artifacts"] if e["path"] == "enrichment.json")
    entry.update(bytes=(output/"enrichment.json").stat().st_size, sha256=sha256_file(output/"enrichment.json"))
    write_json(output/"completion.json", completion)
    with pytest.raises(RunValidationError): validate_run(output, "suitability_enrichment")
    with pytest.raises(RunValidationError): service.download(preview, "json")
    (output/"enrichment.json").write_bytes(original)
    (output/"completion.json").write_bytes(completion_bytes)
    constraint.rename(constraint.with_name("moved-original"))
    validate_run(output, "suitability_enrichment")
    with pytest.raises(RunValidationError): service.load("../escape", dataset)
    with pytest.raises(RunValidationError): service.load(output.name, dataset, expected="b"*64)


def test_filtered_selected_not_assessed_scope_and_stable_order(viewer_data, monkeypatch):
    from mn_land.parcel_table import TableFilters
    from mn_land.review_service import ReviewService, SnapshotKey
    root, _, review = viewer_data()
    dataset = ReviewService(root).load_parcels(SnapshotKey("review", review.name))
    service = SuitabilityService(root)
    doc = payload()
    doc["records"] = []
    observation = SuitabilityObservation("synthetic", "a"*64, canonical(doc))
    monkeypatch.setattr(service, "load", lambda *args, **kwargs: observation)
    preview = service.prepare(observation, dataset, TableFilters(view="prior"), scope="filtered")
    rows = json.loads(preview.document)["records"]
    assert rows[0]["parcel_id"] == "020010200" and rows[0]["status"] == "not_assessed"
    assert rows[0]["estimated_remaining_acres"] is None
    with pytest.raises(RunValidationError): service.prepare(observation, dataset, TableFilters(), scope="selected", selected="other")
    with pytest.raises(RunValidationError): service.prepare(observation, dataset, TableFilters(), scope="filtered", selected="02.001.0200")


def test_long_retained_grid_native_path_preserves_operation_and_evidence(tmp_path):
    pytest.importorskip("shapely")
    pytest.importorskip("pyproj")
    import shutil

    from mn_land.counties.isanti.wetland_crs import GRID_NAME, REFERENCE_ROOT, WetlandAlignment
    from mn_land.runs import workspace_path

    reference = workspace_path(tmp_path/("a"*80)/("b"*80)/("c"*80))
    reference.mkdir(parents=True)
    for name in (GRID_NAME, "isanti_alignment_controls.json"):
        shutil.copyfile(REFERENCE_ROOT/name, reference/name)
    assert len(str(reference/GRID_NAME)) > 260
    original, nested = WetlandAlignment(), WetlandAlignment(reference)
    assert nested.grid.transform(-93.5, 45.7, errcheck=True) == original.grid.transform(-93.5, 45.7, errcheck=True)
    assert nested.evidence() == original.evidence()
