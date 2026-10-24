"""Offline combination of explicitly selected, completed wetland and flood runs."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from mn_land.constraints import POLICY, combine, require
from mn_land.geometry import digest
from mn_land.runs import (
    RunWorkspace,
    ValidatedRun,
    read_artifact_json,
    read_json,
    validate_run,
    workspace_path,
    write_json,
)


def compatible(wetlands: ValidatedRun, floods: ValidatedRun) -> tuple[list[dict], dict]:
    """Do not match merely by parcel ID, area, a latest pointer or approximate CRS."""
    wref, fref = (r.completion["sources"][0] for r in (wetlands, floods))
    require(wref["label"] == fref["label"] == "parcels"
            and wref["completion_sha256"] == fref["completion_sha256"]
            and wref["run_id"] == fref["run_id"],
            "Wetland/flood observations must pin the identical completed parcel geometry")
    wselection = read_artifact_json(wetlands, "selection.json")
    require(wselection == read_artifact_json(floods, "selection.json"),
            "Wetland/flood selections or parcel geometry hashes differ")
    wa, fa = (r.manifest["alignment"] for r in (wetlands, floods))
    require(wa["analysis"] == fa["analysis"]
            and wa["grid_sha256"] == fa["grid_sha256"]
            and wa["controls_canonical_sha256"] == fa["controls_canonical_sha256"],
            "Incompatible analysis CRS, runtime or alignment references")
    geometry = validate_run(wetlands.source("parcels"), "parcel_geometry")
    parcels = read_artifact_json(geometry, "polygons.json")
    require(wselection == [{"parcel_id": p["parcel_id"], "object_id": p["object_id"],
                            "analysis_wkb_sha256": p["analysis_wkb_sha256"]} for p in parcels],
            "Selected analysis hashes differ from the pinned parcel polygons")
    lineage = {
        "geometry_run_id": wref["run_id"],
        "geometry_completion_sha256": wref["completion_sha256"],
        "selection": wselection,
        "analysis": wa["analysis"],
        "inputs": {},
    }
    for label, run in (("wetlands", wetlands), ("floods", floods)):
        manifest = run.manifest
        lineage["inputs"][label] = {
            "run_id": run.path.name, "completion_sha256": run.completion_sha256,
            "algorithm": manifest["algorithm"],
            "capture_started_at": manifest["capture_started_at"],
            "capture_finished_at": manifest["capture_finished_at"],
            "as_of": manifest["as_of"],
            "saved_geometry_capture_started": manifest["saved_geometry_capture_started"],
            "saved_geometry_capture_finished": manifest["saved_geometry_capture_finished"],
            "source_policy": manifest["inclusion_policy" if label == "wetlands" else "category_policy"],
            "source_layers": manifest["source_layers"],
            "spatial_date_context": "Per-parcel imagery/project or panel/revision/study dates remain in pinned observations",
        }
    return parcels, lineage


def summary(rows: list[dict]) -> dict:
    complete = [r for r in rows if r["status"] == "complete"]
    return {"parcels": len(rows), "numeric_results": len(complete),
            "held_results": len(rows) - len(complete),
            "positive_shared_water_sfha": sum(r["shared_water_sfha"]["m2"] > 0 for r in complete),
            "zero_remaining": sum(r["estimated_usable"]["m2"] == 0 for r in complete)}


def calculate(wetlands: ValidatedRun, floods: ValidatedRun) -> tuple[list[dict], dict]:
    parcels, lineage = compatible(wetlands, floods)
    return combine(parcels, read_artifact_json(wetlands, "wetlands.json"),
                   read_artifact_json(floods, "floods.json")), lineage


def analyze_constraints(wetland_snapshot: Path, flood_snapshot: Path, *, output_root: Path) -> Path:
    wet = validate_run(wetland_snapshot, "wetland_analysis")
    flood = validate_run(flood_snapshot, "flood_analysis")
    calculate(wet, flood)  # Refuse incompatible inputs before reserving/copying anything.
    target = workspace_path(output_root).resolve()
    require(not any(r.path.resolve().is_relative_to(target) for r in (wet, flood))
            and not any((parent / marker).exists() for parent in (target, *target.parents)
                        for marker in ("completion.json", "reservation.json", "failure.json")),
            "Choose a dedicated constraint output root outside saved source/run evidence")
    with RunWorkspace(output_root, "constraint_analysis") as run:
        run.stage = "pin_constraint_sources"
        pinned_wet = validate_run(run.pin(wet.path, "wetlands"), "wetland_analysis")
        pinned_flood = validate_run(run.pin(flood.path, "floods"), "flood_analysis")
        run.stage = "combine_mapped_constraints"
        started = datetime.now(UTC).isoformat()
        rows, lineage = calculate(pinned_wet, pinned_flood)
        write_json(run.path / "constraints.json", rows)
        write_json(run.path / "manifest.json", {
            "schema_version": 1, "algorithm": POLICY["version"], "policy": POLICY,
            "processing_started_at": started, "processing_finished_at": datetime.now(UTC).isoformat(),
            "network_requests": 0, "lineage": lineage, "lineage_sha256": digest(lineage),
            "summary": summary(rows),
            "warnings": [POLICY["interpretation"],
                "Offline derivation, not a source/tax refresh or current property-condition observation",
                "Held inputs never become numeric; inspect source contexts even when evidence gap is zero",
                "DNR/FEMA attribution and source notices retained; no redistribution/hosting clearance",
                "No UI, score, access, zoning, septic, legal, insurance or investment determination"],
        })
        run.stage = "validate_constraint_publication"
        run.publish(row_counts={"constraints.json": len(rows)})
    return run.path


def validate_constraint_content(path: Path, completion: dict, manifest: dict) -> None:
    require(manifest["schema_version"] == 1 and manifest["algorithm"] == POLICY["version"]
            and manifest["policy"] == POLICY and manifest["network_requests"] == 0,
            "Unsupported/changed constraint schema or inclusion policy")
    started, finished = (datetime.fromisoformat(manifest[name]) for name in
                         ("processing_started_at", "processing_finished_at"))
    require(started.tzinfo is not None and finished.tzinfo is not None and finished >= started,
            "Invalid constraint processing dates")
    sources = {ref["label"]: ref for ref in completion["sources"]}
    from mn_land.runs import safe_path

    wet = validate_run(safe_path(path, sources["wetlands"]["path"], directory=True), "wetland_analysis")
    flood = validate_run(safe_path(path, sources["floods"]["path"], directory=True), "flood_analysis")
    rows, lineage = calculate(wet, flood)
    require(lineage == manifest["lineage"] and digest(lineage) == manifest["lineage_sha256"],
            "Constraint source identity, policies, CRS or independent dates do not reproduce")
    require(rows == read_json(path / "constraints.json"), "Constraint union/remainder does not reproduce")
    require(manifest["summary"] == summary(rows)
            and completion["row_counts"] == {"constraints.json": len(rows)},
            "Constraint summary/row accounting does not reproduce")
