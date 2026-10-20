"""Explicit saved polygons -> separate effective FEMA evidence and flood metrics."""
from __future__ import annotations

import shutil
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

from mn_land.counties.isanti.flood_crs import FloodAlignment
from mn_land.counties.isanti.wetland_crs import GRID_NAME, REFERENCE_ROOT
from mn_land.floods import PROCESSING_POLICY, overlap, project_features, query_groups
from mn_land.geometry import GeometryError, digest
from mn_land.ingestion.spatial_capture import (
    MAX_CAPTURE_BYTES,
    MAX_REQUESTS,
    POLICY,
    SpatialCapture,
    SpatialReplay,
)
from mn_land.ingestion.spatial_layers import fetch_polygons
from mn_land.runs import (
    RunWorkspace,
    read_artifact_json,
    read_json,
    safe_path,
    validate_run,
    workspace_path,
    write_json,
)
from mn_land.sources.fema_nfhl import (
    CATEGORY_POLICY,
    LAYERS,
    SERVICE,
    STUDIES,
    fetch_studies,
    map_schema,
    service_contract,
    study_id,
)

SOURCE_URLS = {**{name: spec.url for name, spec in LAYERS.items()}, "studies": STUDIES.url}
BUDGETS = {"logical_requests": MAX_REQUESTS, "capture_bytes": MAX_CAPTURE_BYTES,
           "study_identifiers": 20, "study_rows": 100}


def process(request: Callable, parcels: list[dict], alignment: FloodAlignment,
            as_of: date) -> tuple[list[dict], list[dict], list[dict], dict, list[dict]]:
    groups = query_groups(parcels, alignment)
    initial = service_contract(request(SERVICE, {"f": "json"}))
    projected, checks = [], {}
    for name, spec in LAYERS.items():
        raw, checks[name] = fetch_polygons(request, spec, groups, schema=map_schema, confirm_null_empty=True)
        projected.extend(project_features(raw, name, groups, alignment))
    ids = sorted({identity for r in projected for identity in [study_id(r["raw_attributes"].get(
        "STUDY_ID" if r["layer"] == "availability" else "DFIRM_ID"))] if identity})
    studies, checks["studies"] = fetch_studies(request, ids)
    final = service_contract(request(SERVICE, {"f": "json"}))
    if initial != final:
        raise GeometryError("FEMA service contract drift during acquisition")
    checks["service"] = initial
    return overlap(parcels, projected, studies, as_of=as_of), projected, studies, checks, groups


def summary(rows: list[dict]) -> dict:
    numeric = [r for r in rows if r["status"] == "complete"]
    return {"parcels": len(rows), "numeric_results": len(numeric),
            "held_results": len(rows) - len(numeric),
            "positive_mapped_sfha": sum(r["metrics"]["sfha"]["m2"] > 0 for r in numeric),
            "verified_zero_mapped_sfha": sum(r["metrics"]["sfha"]["m2"] == 0 for r in numeric)}


def selection(parcels: list[dict]) -> list[dict]:
    return [{"parcel_id": r["parcel_id"], "object_id": r["object_id"],
             "analysis_wkb_sha256": r["analysis_wkb_sha256"]} for r in parcels]


def acquire_floods(geometry_snapshot: Path, *, output_root: Path, transport=None) -> Path:
    validated = validate_run(geometry_snapshot, "parcel_geometry")
    parcels = read_artifact_json(validated, "polygons.json")
    query_groups(parcels, FloodAlignment())  # Before reservation/network.
    target = workspace_path(output_root).resolve()
    if validated.path.resolve().is_relative_to(target) or any(
        (parent / marker).exists() for parent in (target, *target.parents)
        for marker in ("completion.json", "reservation.json", "failure.json")
    ):
        raise GeometryError("Choose a dedicated flood output root outside source/run evidence")
    with RunWorkspace(output_root, "flood_analysis") as run:
        run.stage = "pin_flood_parcels"
        pinned = validate_run(run.pin(geometry_snapshot, "parcels"), "parcel_geometry")
        parcels = read_artifact_json(pinned, "polygons.json")
        reference = run.path / "reference"
        reference.mkdir()
        for name in (GRID_NAME, "isanti_alignment_controls.json"):
            shutil.copyfile(REFERENCE_ROOT / name, reference / name)
        alignment = FloodAlignment(reference)
        write_json(run.path / "selection.json", selection(parcels))
        run.stage = "capture_effective_fema"
        started = datetime.now(UTC)
        with SpatialCapture(run.path / "capture", transport) as capture:
            rows, features, studies, checks, groups = process(capture.request, parcels, alignment, started.date())
        finished = datetime.now(UTC)
        write_json(run.path / "floods.json", rows)
        write_json(run.path / "source_features.json", features)
        write_json(run.path / "study_records.json", studies)
        write_json(run.path / "manifest.json", {
            "schema_version": 1, "algorithm": PROCESSING_POLICY["version"],
            "source_agency": "Federal Emergency Management Agency",
            "source_service": SERVICE, "source_layers": SOURCE_URLS,
            "capture_started_at": started.isoformat(), "capture_finished_at": finished.isoformat(),
            "as_of": started.date().isoformat(),
            "saved_geometry_capture_started": pinned.manifest["geometry_capture_started"],
            "saved_geometry_capture_finished": pinned.manifest["geometry_capture_finished"],
            "requests": capture.records, "wire_bytes_retained": capture.wire,
            "wire_limitation": None if capture.wire else "Injected offline transport; no original wire bytes",
            "query_aoi_groups": groups, "query_aoi_sha256": digest(groups),
            "checks": checks, "alignment": alignment.evidence(),
            "processing_policy": PROCESSING_POLICY, "category_policy": CATEGORY_POLICY,
            "retrieval_policy": POLICY.to_dict(), "budgets": BUDGETS,
            "summary": summary(rows),
            "attribution": "FEMA, effective National Flood Hazard Layer (NFHL)",
            "warnings": [
                "Complete observation run; each parcel status gates numeric metrics",
                "Availability, valid dated panels and zone geometry are independently reconciled by study",
                "Unavailable/partial/unknown evidence yields held/null, never zero or no flood risk",
                "Panel, revision, study/database, parcel and retrieval dates remain separate",
                "Invalid/future raw dates retained; no substitution or automatic LOMA conclusions",
                "Public requests non-atomic; unavailable same-ID edit consistency remains unknown",
                "Source notices retained; public access is not redistribution/hosting clearance",
                "No wetland combination, remaining acres, score, tax refresh, UI or legal/insurance determination",
            ],
        })
        run.stage = "validate_flood_publication"
        run.publish(row_counts={"floods.json": len(rows), "source_features.json": len(features),
                                "study_records.json": len(studies)})
    return run.path


def validate_flood_content(path: Path, completion: dict, manifest: dict) -> None:
    def require(condition: bool, reason: str) -> None:
        if not condition:
            raise GeometryError(reason)

    require(manifest["schema_version"] == 1 and manifest["algorithm"] == PROCESSING_POLICY["version"],
            "Unsupported FEMA observation schema/algorithm")
    require(manifest["source_service"] == SERVICE and manifest["source_layers"] == SOURCE_URLS,
            "FEMA effective source substitution refused")
    require(manifest["processing_policy"] == PROCESSING_POLICY and manifest["category_policy"] == CATEGORY_POLICY,
            "Changed FEMA calculation/category policy")
    require(manifest["retrieval_policy"] == POLICY.to_dict() and manifest["budgets"] == BUDGETS,
            "Changed FEMA retrieval budgets")
    ref = next(r for r in completion["sources"] if r["label"] == "parcels")
    pinned = validate_run(safe_path(path, ref["path"], directory=True), "parcel_geometry")
    parcels = read_artifact_json(pinned, "polygons.json")
    require(read_json(path / "selection.json") == selection(parcels), "FEMA parcel identity/hash selection differs")
    require(manifest["saved_geometry_capture_started"] == pinned.manifest["geometry_capture_started"]
        and manifest["saved_geometry_capture_finished"] == pinned.manifest["geometry_capture_finished"],
        "Saved parcel and new FEMA capture dates were conflated")
    alignment = FloodAlignment(path / "reference")
    require(alignment.evidence() == manifest["alignment"], "Changed FEMA alignment/reference/library evidence")
    as_of = date.fromisoformat(manifest["as_of"])
    require(as_of == datetime.fromisoformat(manifest["capture_started_at"]).date(),
            "FEMA processing date differs from capture")
    replay = SpatialReplay(path / "capture", manifest)
    rows, features, studies, checks, groups = process(replay.request, parcels, alignment, as_of)
    replay.complete()
    require(groups == manifest["query_aoi_groups"] and digest(groups) == manifest["query_aoi_sha256"],
            "FEMA query AOIs differ from pinned parcels")
    require(checks == manifest["checks"], "FEMA source checks do not reproduce")
    require(rows == read_json(path / "floods.json") and features == read_json(path / "source_features.json")
        and studies == read_json(path / "study_records.json"), "FEMA calculation/context does not reproduce")
    require(summary(rows) == manifest["summary"], "FEMA summary does not reproduce")
    require(completion["row_counts"] == {"floods.json": len(rows), "source_features.json": len(features),
        "study_records.json": len(studies)}, "FEMA row accounting differs")
