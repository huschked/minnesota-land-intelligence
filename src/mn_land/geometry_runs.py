"""Explicit completed-review -> new immutable polygon evidence. Never latest.

One completion covers acquisition AND all analysis polygons. A missing/ambiguous
identity, unsupported shape, CRS failure or budget excess retains staging evidence
and a failure marker, never a partially usable geometry run.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from pyproj.exceptions import ProjError
from shapely.errors import GEOSException

from mn_land.counties.isanti.geometry import (
    ANALYSIS,
    LAYER,
    MAX_CAPTURE_BYTES,
    MAX_REQUESTS,
    POLICY,
    acquire,
    capture,
    identity,
    native_crs,
)
from mn_land.geometry import GeometryAnalysis, GeometryError, digest
from mn_land.parcel_table import VIEWS, in_view, project_rows
from mn_land.runs import (
    RunValidationError,
    RunWorkspace,
    read_artifact_json,
    read_json,
    safe_path,
    validate_run,
    workspace_path,
    write_json,
)
from mn_land.utils.http import ArcGISError
from mn_land.utils.validation import minimum_acres

MAX_ANALYSIS_VERTICES = 1_000_000


def selection(review: Path, view: str) -> list[dict]:
    if view not in VIEWS:
        raise GeometryError("Explicit supported candidate view required")
    selected = validate_run(review, "review")
    joined = validate_run(selected.source("join"), "delinquency_processed")
    imported = validate_run(joined.source("delinquency"), "delinquency_raw")
    mapping = read_artifact_json(imported, "mapping.json")
    if mapping.get("verification_hold_reason") or joined.manifest.get("unverified_matches"):
        raise GeometryError("Candidate source has an active verification hold")
    comparison_name = "inputs/official_report_comparison.json"
    if any(e["path"] == comparison_name for e in selected.completion["artifacts"]):
        comparison = read_artifact_json(selected, comparison_name)
        if comparison.get("operational_status") == "HOLD_COUNTY_RECONCILIATION_REQUIRED":
            raise GeometryError("Candidate review has a county reconciliation hold")
    floor = max(
        minimum_acres(selected.manifest["minimum_acres"]),
        minimum_acres(joined.manifest["minimum_acres"]),
    )
    rows = project_rows(
        read_artifact_json(joined, "isanti_verified_delinquent_candidates.json"),
        read_artifact_json(joined, "isanti_overdue_current_year_parcels.json"), floor,
    )
    from mn_land.counties.isanti.delinquency import normalize_parcel_id

    result = sorted([
        {"parcel_id": normalize_parcel_id(row.parcel_id),
         "candidate_parcel_id": row.parcel_id,
         "saved_deeded_acres": str(row.deeded_acres) if row.deeded_acres is not None else None}
        for row in rows if in_view(row, view)
    ], key=lambda row: row["parcel_id"])
    if not result or len(result) > 500 or len({r["parcel_id"] for r in result}) != len(result):
        raise GeometryError("Candidate selection is empty, ambiguous or exceeds 500 parcels")
    return result


def analyze(features: list[dict], selected: list[dict], schema: dict) -> tuple[list[dict], dict]:
    engine = GeometryAnalysis(native_crs(schema["spatial_reference"]), ANALYSIS)
    originals = []
    rows = []
    saved = {r["parcel_id"]: r for r in selected}
    vertices = 0
    for feature in features:
        oid, pin = identity(feature)
        try:
            observation, shape = engine.project(
                feature["geometry"], feature["attributes"].get("DEEDEDACRES"),
            )
        except (ProjError, GEOSException) as exc:
            raise GeometryError("Polygon transformation/topology failed; no repair") from exc
        if any(shape.equals(previous) for previous in originals):
            raise GeometryError("Duplicate topological geometry across parcel identities")
        originals.append(shape)
        vertices += observation["analysis_vertices"]
        if vertices > MAX_ANALYSIS_VERTICES:
            raise GeometryError("Aggregate analysis vertex budget exceeded")
        rows.append({
            "parcel_id": pin, "object_id": oid,
            "saved_deeded_acres": saved[pin]["saved_deeded_acres"],
            "source_fields": {"identity": ["PARCELID", "UNFORMATTEDPIN", "OBJECTID"],
                              "deeded_acres": "DEEDEDACRES", "geometry": "geometry"},
            **observation,
        })
    return rows, engine.evidence()


def acquire_geometry(
    review: Path, *, view: str, output_root: Path, transport=None, batch_size: int = 50,
) -> Path:
    # Validate before reserving/network. Pin/reselect again so the exact copied
    # graph, not an earlier mutable input, defines the capture.
    selection(review, view)
    target = workspace_path(output_root).resolve()
    source = workspace_path(review).resolve(strict=True)
    if source.is_relative_to(target) or any(
        (parent / marker).exists()
        for parent in (target, *target.parents)
        for marker in ("completion.json", "reservation.json", "failure.json")
    ):
        raise GeometryError("Choose a dedicated geometry root outside existing source/run evidence")
    with RunWorkspace(output_root, "parcel_geometry") as run:
        run.stage = "pin_geometry_candidates"
        pinned = run.pin(review, "candidates")
        selected = selection(pinned, view)
        write_json(run.path / "selection.json", selected)
        started = datetime.now(UTC).isoformat()
        run.stage = "capture_native_geometry"
        features, checks, requests, wire = capture(
            run.path / "capture", [r["parcel_id"] for r in selected], transport,
            batch_size=batch_size,
        )
        finished = datetime.now(UTC).isoformat()
        run.stage = "validate_polygon_analysis"
        try:
            rows, analysis = analyze(features, selected, checks["schema"])
        except GeometryError as exc:
            write_json(run.path / "geometry_hold.json", {
                "status": "held", "reason": str(exc), "analysis_complete": False,
                "area": None, "repair": "not supported; raw originals retained",
            })
            raise
        write_json(run.path / "polygons.json", rows)
        write_json(run.path / "manifest.json", {
            "schema_version": 1, "source_agency": "Isanti County GIS",
            "source_layer": LAYER, "view": view,
            "selection_sha256": digest(selected), "geometry_capture_started": started,
            "geometry_capture_finished": finished, "requests": requests,
            "checks": checks, "analysis": analysis, "retrieval_policy": POLICY.to_dict(),
            "wire_bytes_retained": wire,
            "aggregate_budgets": {"capture_bytes": MAX_CAPTURE_BYTES,
                                  "analysis_vertices": MAX_ANALYSIS_VERTICES},
            "wire_limitation": None if wire else "injected offline transport; not wire capture",
            "warnings": [
                "New geometry capture, NOT the saved candidate GIS/tax capture date",
                "Non-atomic public service; same-ID edits cannot be ruled out absolutely",
                "Adjusted native-datum equal-area screening, not legal/survey acreage",
                "Deeded and measured areas remain independent; no usable-acre calculation",
                "No cross-datum thematic alignment is approved by this operation",
            ],
        })
        run.publish(row_counts={"polygons.json": len(rows)})
    return run.path


def validate_geometry_content(path: Path, completion: dict, manifest: dict) -> None:
    """Reconcile retained requests offline, then reproduce analysis (no HTTP).

    Changed spatial libraries/databases require explicit new processing, not
    silent validation with an approximate substitute operation.
    """
    def require(condition, reason):
        if not condition:
            raise RunValidationError(reason)

    ref = next(r for r in completion["sources"] if r["label"] == "candidates")
    pinned = safe_path(path, ref["path"], directory=True)
    selected = selection(pinned, manifest["view"])
    require(read_json(path / "selection.json") == selected, "Geometry selection/source mismatch")
    require(manifest["selection_sha256"] == digest(selected), "Geometry selection hash mismatch")
    require(manifest["source_layer"] == LAYER and manifest["schema_version"] == 1,
            "Unsupported geometry source/schema")
    start = datetime.fromisoformat(manifest["geometry_capture_started"])
    finish = datetime.fromisoformat(manifest["geometry_capture_finished"])
    require(start.tzinfo is not None and finish.tzinfo is not None and start <= finish,
            "Invalid new geometry capture dates")
    records = manifest["requests"]
    require(isinstance(records, list) and 0 < len(records) <= MAX_REQUESTS,
            "Geometry request inventory exceeds budget")
    require(manifest["retrieval_policy"] == POLICY.to_dict(), "Changed geometry retrieval policy")
    require(manifest["aggregate_budgets"] == {"capture_bytes": MAX_CAPTURE_BYTES,
                                             "analysis_vertices": MAX_ANALYSIS_VERTICES},
            "Changed aggregate geometry budgets")
    require(sum(p.stat().st_size for p in (path / "capture").rglob("*") if p.is_file())
            <= MAX_CAPTURE_BYTES, "Aggregate geometry capture byte budget exceeded")
    wire = manifest["wire_bytes_retained"]
    require(type(wire) is bool, "Invalid wire evidence declaration")
    counter, previous_time, previous_attempt = 0, start, 0

    def replay(params, *, query=True):
        nonlocal counter, previous_time, previous_attempt
        counter += 1
        require(counter <= len(records), "Missing retained geometry request")
        record = records[counter - 1]
        receipt = read_json(safe_path(path, f"capture/receipt_{counter:03d}.json"))
        require(record == receipt, "Geometry receipt differs from capture manifest")
        require(record["number"] == counter and record["url"] == LAYER + (
            "/query" if query else "") and record["params"] == params,
            "Retained geometry query/URL/order differs from reviewed contract")
        intended = read_json(safe_path(path, f"capture/request_{counter:03d}.json"))
        require(all(record[k] == v for k, v in intended.items()), "Changed intended request")
        before = datetime.fromisoformat(record["started_at"])
        after = datetime.fromisoformat(record["finished_at"])
        require(before.tzinfo is not None and after.tzinfo is not None
                and previous_time <= before <= after <= finish,
                "Invalid request chronology")
        previous_time = after
        if record.get("failure"):
            require(record["failure"] == "body_budget", "Failed geometry request cannot complete")
            if wire:
                previous_attempt = _wire(path, record, previous_attempt, None)
            raise ArcGISError("Response exceeds configured body byte budget")
        expected_name = f"response_{counter:03d}.json"
        require(record["response"] == expected_name, "Unsafe geometry response reference")
        payload = read_json(safe_path(path, "capture/" + expected_name))
        if wire:
            previous_attempt = _wire(path, record, previous_attempt, payload)
        return payload

    features, checks = acquire(replay, [r["parcel_id"] for r in selected],
                               batch_size=manifest["checks"]["configured_batch_size"])
    require(counter == len(records) and checks == manifest["checks"],
            "Unreconciled geometry requests/source checks")
    rows, analysis = analyze(features, selected, checks["schema"])
    require(analysis == manifest["analysis"], "Changed geometry algorithm/library/CRS evidence")
    require(rows == read_json(path / "polygons.json"), "Geometry analysis does not reproduce")
    require(completion["row_counts"] == {"polygons.json": len(rows)}, "Polygon row count mismatch")
    if wire:
        actual = list((path / "capture/http").glob("*.evidence.json"))
        require(len(actual) == previous_attempt, "Unreconciled wire attempt inventory")


def _wire(path: Path, record: dict, previous: int, payload: dict | None) -> int:
    """Tie normalized response to exact retained successful HTTP body/attempts."""
    first, last = record["first_http_attempt"], record["last_http_attempt"]

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise RunValidationError("Duplicate JSON member in native geometry wire evidence")
            result[key] = value
        return result
    if type(first) is not int or type(last) is not int or first != previous + 1 or not (
        first <= last < first + POLICY.max_attempts
    ):
        raise RunValidationError("Invalid geometry HTTP attempt range")
    for attempt in range(first, last + 1):
        stem = f"attempt_{attempt:05d}"
        evidence = read_json(safe_path(path, f"capture/http/{stem}.evidence.json"))
        # Transport filenames use the capture-global counter, while the record's
        # attempt is the retry ordinal within this individual request.
        if evidence.get("attempt") != attempt - first + 1:
            raise RunValidationError("Invalid wire attempt identity")
        body_info = evidence.get("body")
        if body_info:
            if body_info["file"] != stem + ".body" or not re.fullmatch(
                "[0-9a-f]{64}", body_info["sha256"],
            ):
                raise RunValidationError("Unsafe wire body reference")
            body = safe_path(path, f"capture/http/{stem}.body").read_bytes()
            if len(body) != body_info["bytes"] or len(body) > POLICY.max_body_bytes or (
                hashlib.sha256(body).hexdigest() != body_info["sha256"]
            ):
                raise RunValidationError("Wire body hash/byte budget mismatch")
        if attempt == last and payload is not None and (
            not body_info or evidence.get("outcome") != "success"
            or evidence.get("body_truncated") is not False
            or evidence.get("body_incomplete") is not False
            or json.loads(body, object_pairs_hook=unique) != payload
        ):
            raise RunValidationError("Normalized geometry response differs from wire evidence")
        if attempt == last and payload is None and evidence.get("body_truncated") is not True:
            raise RunValidationError("Split batch lacks body-budget evidence")
    return last
