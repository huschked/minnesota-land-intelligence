"""Explicit polygon snapshot -> separately dated, pinned DNR wetland observations."""

from __future__ import annotations

import shutil
from datetime import UTC, date, datetime
from pathlib import Path

from mn_land.counties.isanti.wetland_crs import GRID_NAME, REFERENCE_ROOT, WetlandAlignment
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
from mn_land.sources.dnr_nwi import INCLUSION_POLICIES, INCLUSION_POLICY, NWI, PROJECTS
from mn_land.wetlands import overlap, project_features, query_groups


def process(request, parcels: list[dict], alignment: WetlandAlignment, as_of: date,
            inclusion_policy: dict = INCLUSION_POLICY):
    groups = query_groups(parcels, alignment)
    nwi, nwi_checks = fetch_polygons(request, NWI, groups)
    projects, project_checks = fetch_polygons(request, PROJECTS, groups)
    mapped = project_features(nwi, groups, alignment, inclusion_policy=inclusion_policy)
    context = project_features(projects, groups, alignment, projects=True)
    observations = overlap(parcels, mapped, context, as_of=as_of)
    features = [{"layer": "nwi", **r} for r in mapped] + [
        {"layer": "projects", **r} for r in context]
    return observations, features, {"nwi": nwi_checks, "projects": project_checks}, groups


def summary(rows: list[dict]) -> dict:
    return {"parcels": len(rows), "numeric_results": sum(r["status"] == "complete" for r in rows),
            "held_results": sum(r["status"] == "held" for r in rows),
            "verified_zero_mapped_overlap": sum(r["mapped_wetland_m2"] == 0 for r in rows)}


def acquire_wetlands(geometry_snapshot: Path, *, output_root: Path, transport=None) -> Path:
    validated = validate_run(geometry_snapshot, "parcel_geometry")
    # Resolve before any reservation/network, and forbid writing inside old runs.
    parcels = read_artifact_json(validated, "polygons.json")
    alignment = WetlandAlignment()
    query_groups(parcels, alignment)
    target = workspace_path(output_root).resolve()
    if validated.path.resolve().is_relative_to(target) or any(
        (parent / marker).exists()
        for parent in (target, *target.parents)
        for marker in ("completion.json", "reservation.json", "failure.json")
    ):
        raise GeometryError("Choose a dedicated wetland output root outside saved source/run evidence")
    with RunWorkspace(output_root, "wetland_analysis") as run:
        run.stage = "pin_wetland_parcels"
        pinned = validate_run(run.pin(geometry_snapshot, "parcels"), "parcel_geometry")
        parcels = read_artifact_json(pinned, "polygons.json")
        reference = run.path / "reference"
        reference.mkdir()
        for name in (GRID_NAME, "isanti_alignment_controls.json"):
            shutil.copyfile(REFERENCE_ROOT / name, reference / name)
        alignment = WetlandAlignment(reference)
        write_json(run.path / "selection.json", [
            {"parcel_id": row["parcel_id"], "object_id": row["object_id"],
             "analysis_wkb_sha256": row["analysis_wkb_sha256"]} for row in parcels])
        run.stage = "capture_dnr_sources"
        started = datetime.now(UTC)
        with SpatialCapture(run.path / "capture", transport) as capture:
            rows, features, checks, groups = process(
                capture.request, parcels, alignment, started.date(),
            )
        finished = datetime.now(UTC)
        write_json(run.path / "wetlands.json", rows)
        write_json(run.path / "source_features.json", features)
        run.stage = "validate_wetland_publication"
        write_json(run.path / "manifest.json", {
            "schema_version": 1, "algorithm": "dnr-wetland-dissolve-clip-v1",
            "source_agency": "Minnesota Department of Natural Resources",
            "source_layers": {"nwi": NWI.url, "projects": PROJECTS.url},
            "capture_started_at": started.isoformat(), "capture_finished_at": finished.isoformat(),
            "as_of": started.date().isoformat(),
            "saved_geometry_capture_started": pinned.manifest["geometry_capture_started"],
            "saved_geometry_capture_finished": pinned.manifest["geometry_capture_finished"],
            "requests": capture.records, "wire_bytes_retained": capture.wire,
            "wire_limitation": None if capture.wire else "Injected offline transport; no original wire bytes",
            "query_aoi_groups": groups, "query_aoi_sha256": digest(groups),
            "query_policy": "groups of <=4 native-SR parcel envelopes +2 m query-only margin",
            "checks": checks, "alignment": alignment.evidence(),
            "inclusion_policy": INCLUSION_POLICY, "retrieval_policy": POLICY.to_dict(),
            "budgets": {"logical_requests": MAX_REQUESTS, "capture_bytes": MAX_CAPTURE_BYTES,
                        "selected_parcels": 50, "analysis_vertices_per_layer": 1_000_000},
            "summary": summary(rows),
            "metric_semantics": "Complete observation run; each parcel status gates numeric results",
            "attribution": "Minnesota DNR, National Wetland Inventory for Minnesota",
            "warnings": [
                "Preliminary remotely mapped inventory, not regulatory delineation or buildability",
                "Coverage verified using independent project footprints, not wetland count",
                "Unknown/partial coverage and classification holds have null overall metrics",
                "Project imagery/delivery dates differ from new capture and old parcel/tax dates",
                "Public requests are non-atomic; unavailable source edit consistency remains unknown",
                "DNR source notices apply; no raw dataset redistribution/resale/hosting clearance",
                "No federal/state union, flood overlay, remaining-acre estimate, score or tax refresh",
            ],
        })
        run.publish(row_counts={"wetlands.json": len(rows), "source_features.json": len(features)})
    return run.path


def validate_wetland_content(path: Path, completion: dict, manifest: dict) -> None:
    def require(condition, reason):
        if not condition:
            raise GeometryError(reason)

    require(manifest["schema_version"] == 1 and manifest["algorithm"] == "dnr-wetland-dissolve-clip-v1",
            "Unsupported wetland observation schema/algorithm")
    require(manifest["source_layers"] == {"nwi": NWI.url, "projects": PROJECTS.url},
            "Wetland source substitution refused")
    require(INCLUSION_POLICIES.get(manifest["inclusion_policy"].get("version"))
            == manifest["inclusion_policy"], "Changed wetland inclusion policy")
    require(manifest["retrieval_policy"] == POLICY.to_dict(), "Changed wetland retrieval policy")
    require(manifest["budgets"] == {"logical_requests": MAX_REQUESTS, "capture_bytes": MAX_CAPTURE_BYTES,
                                   "selected_parcels": 50, "analysis_vertices_per_layer": 1_000_000},
            "Changed wetland acquisition budgets")
    ref = next(r for r in completion["sources"] if r["label"] == "parcels")
    pinned = validate_run(safe_path(path, ref["path"], directory=True), "parcel_geometry")
    parcels = read_artifact_json(pinned, "polygons.json")
    require(read_json(path / "selection.json") == [
        {"parcel_id": row["parcel_id"], "object_id": row["object_id"],
         "analysis_wkb_sha256": row["analysis_wkb_sha256"]} for row in parcels],
        "Wetland selected parcel/hash identity differs from pinned geometry")
    require(manifest["saved_geometry_capture_started"] == pinned.manifest["geometry_capture_started"]
            and manifest["saved_geometry_capture_finished"] == pinned.manifest["geometry_capture_finished"],
            "Geometry and wetland capture dates were conflated")
    alignment = WetlandAlignment(path / "reference")
    require(alignment.evidence() == manifest["alignment"], "Changed wetland CRS/grid/control/library evidence")
    replay = SpatialReplay(path / "capture", manifest)
    as_of = date.fromisoformat(manifest["as_of"])
    require(as_of == datetime.fromisoformat(manifest["capture_started_at"]).date(),
            "Wetland processing date differs from actual capture")
    rows, features, checks, groups = process(replay.request, parcels, alignment, as_of,
                                            manifest["inclusion_policy"])
    replay.complete()
    require(checks == manifest["checks"], "Wetland source checks do not reconcile")
    require(groups == manifest["query_aoi_groups"] and digest(groups) == manifest["query_aoi_sha256"],
            "Wetland query AOI differs from pinned parcels")
    require(rows == read_json(path / "wetlands.json") and features == read_json(path / "source_features.json"),
            "Wetland clipping/coverage/classification does not reproduce")
    require(manifest["summary"] == summary(rows), "Wetland result summary differs")
    require(completion["row_counts"] == {"wetlands.json": len(rows), "source_features.json": len(features)},
            "Wetland row accounting differs")
