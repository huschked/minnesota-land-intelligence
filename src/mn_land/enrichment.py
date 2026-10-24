"""Versioned canonical suitability exports from unchanged, completed observations.

No GIS import at module load; optional GIS is needed only for graph validation.
No network, tax refresh, source repair or legal conclusion.
"""
from __future__ import annotations

import csv
import io
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from mn_land.provenance import sha256_file
from mn_land.runs import (
    RunValidationError,
    RunWorkspace,
    ValidatedRun,
    read_artifact_json,
    read_json,
    safe_path,
    validate_run,
    workspace_path,
    write_json,
)
from mn_land.worklists import canonical

ALGORITHM = "saved-suitability-enrichment-v1"
MAX_EXPORT_BYTES = 8 * 1024 * 1024
CSV_NULL = "\\N"
CSV_FIELDS = (
    "parcel_id", "status", "measured_acres", "saved_deeded_acres", "new_gis_deeded_acres",
    "mapped_wetland_acres", "mapped_water_acres", "sfha_acres", "floodway_acres",
    "annual_chance_0_2pct_acres", "minimal_hazard_acres", "combined_constraint_acres",
    "shared_water_sfha_acres", "estimated_remaining_acres", "evidence_gap_m2", "holds",
    "wetland_project_contexts", "flood_panel_contexts", "flood_study_contexts",
    "context",
)
WARNINGS = (
    "Preliminary mapped-policy remainder, not verified usable/upland or legally buildable acres",
    "Held is unknown, not zero. Not assessed means outside the selected suitability observation",
    "Source capture, imagery/project, panel/study, parcel and tax dates remain independent",
    "No source/tax refresh, current payment verification, access/zoning/septic or investment conclusion",
    "FEMA 0.2%/minimal-hazard zones are not subtracted by the selected policy; no-risk is not inferred",
    "DNR/FEMA attribution and source notices remain in pinned evidence; no public hosting clearance",
)


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RunValidationError(reason)


def child(run: ValidatedRun, prefix: str, label: str) -> tuple[str, dict]:
    """Read only exact inventoried bytes of the already validated contained graph."""
    completion = run.completion if not prefix else read_artifact_json(run, prefix + "/completion.json")
    ref = next(r for r in completion["sources"] if r["label"] == label)
    return "/".join(part for part in (prefix, ref["path"]) if part), ref


def project(run: ValidatedRun, review: dict) -> dict:
    require(run.completion["kind"] == "constraint_analysis", "Completed constraint input required")
    wp, wr = child(run, "", "wetlands")
    fp, fr = child(run, "", "floods")
    gp, _ = child(run, wp, "parcels")
    rp, rr = child(run, gp, "candidates")
    jp, jr = child(run, rp, "join")
    ip, ir = child(run, jp, "delinquency")
    listing = read_artifact_json(run, ip + "/mapping.json")
    wm = read_artifact_json(run, wp + "/manifest.json")
    fm = read_artifact_json(run, fp + "/manifest.json")
    wet = {r["parcel_id"]: r for r in read_artifact_json(run, wp + "/wetlands.json")}
    flood = {r["parcel_id"]: r for r in read_artifact_json(run, fp + "/floods.json")}
    records = []
    for row in read_artifact_json(run, "constraints.json"):
        identity = row["parcel_id"]
        require(isinstance(identity, str) and re.fullmatch(r"[0-9]{9}", identity) is not None,
                "Noncanonical Isanti parcel identity")
        w, f = wet[identity], flood[identity]
        def metric(name: str, source: dict = f):
            return None if source["metrics"][name] is None else source["metrics"][name]["acres"]
        def combined(name: str, source: dict = row):
            return None if source[name] is None else source[name]["acres"]
        record = {
            "parcel_id": identity, "parcel_object_id": row["parcel_object_id"],
            "analysis_wkb_sha256": row["analysis_wkb_sha256"], "status": row["status"],
            "measured_acres": row["measured_parcel"]["acres"],
            "saved_deeded_acres": row["saved_deeded_acres"],
            "new_gis_deeded_acres": row["new_parcel_gis_deeded_acres"],
            "deeded_discrepancy": row["deeded_discrepancy"],
            "mapped_wetland_acres": w["mapped_wetland_acres"],
            "mapped_water_acres": None if w["mapped_water_and_wetland_m2"] is None else (
                w["mapped_water_and_wetland_m2"] / run.manifest["policy"]["international_acre_m2"]),
            "sfha_acres": metric("sfha"), "floodway_acres": metric("floodway"),
            "annual_chance_0_2pct_acres": metric("annual_chance_0_2pct"),
            "minimal_hazard_acres": metric("minimal_hazard"),
            "combined_constraint_acres": combined("combined_constraint"),
            "shared_water_sfha_acres": combined("shared_water_sfha"),
            "estimated_remaining_acres": combined("estimated_usable"),
            "evidence_gap_m2": row["combined_evidence_gap"]["m2"], "holds": row["holds"],
            "wetland_project_contexts": [
                {k: v for k, v in c.items() if k != "intersection_wkb_hex"}
                for c in w["project_contexts"]],
            "flood_panel_contexts": [
                {"object_id": c["object_id"], "raw_attributes": c["raw_attributes"],
                 "effective_date": c.get("effective_date"),
                 "eligible_effective_coverage": c.get("eligible_effective_coverage")}
                for c in f["source_contexts"] if c["layer"] == "panels"],
            "flood_study_contexts": f["study_contexts"],
            "source_observation_sha256": row["source_observation_sha256"],
        }
        if row["status"] == "held":
            require(record["estimated_remaining_acres"] is None
                    and record["combined_constraint_acres"] is None, "Held totals must remain null")
        records.append(record)
    records.sort(key=lambda row: row["parcel_id"])
    require(len(records) == len({r["parcel_id"] for r in records}), "Duplicate enrichment identity")
    return {"schema_version": 1, "context": {
        "county": "Isanti", "algorithm": ALGORITHM,
        "constraint_run_id": run.path.name, "constraint_completion_sha256": run.completion_sha256,
        "candidate_review": {"run_id": rr["run_id"], "completion_sha256": rr["completion_sha256"]},
        "candidate_join": {"run_id": jr["run_id"], "completion_sha256": jr["completion_sha256"]},
        "listing_import": {"run_id": ir["run_id"], "completion_sha256": ir["completion_sha256"],
                           "publication_date": listing.get("publication_date")},
        "constraint_policy": run.manifest["policy"], "lineage": run.manifest["lineage"],
        "source_agencies": ["Minnesota Department of Natural Resources", "Federal Emergency Management Agency"],
        "source_snapshots": {"wetlands": wr, "floods": fr},
        "source_dates": {label: {key: m[key] for key in (
            "capture_started_at", "capture_finished_at", "saved_geometry_capture_started",
            "saved_geometry_capture_finished")} for label, m in (("wetlands", wm), ("floods", fm))},
        "map_review": {key: review.get(key) for key in (
            "reviewed_at", "method", "findings", "samples", "guidance_sources", "tolerances_and_limits")},
        "csv_null_marker": CSV_NULL,
        "csv_import_note": "Parcel IDs are text. Use a text-column CSV import or JSON; spreadsheet auto-open can strip leading zeros",
        "warnings": list(WARNINGS),
    }, "records": records}


def serialize(payload: dict, format: str) -> bytes:
    require(format in {"csv", "json"}, "Choose CSV or JSON")
    if format == "json":
        body = (canonical(payload) + "\n").encode("utf-8")
    else:
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in payload["records"]:
            cells = {}
            for name in CSV_FIELDS:
                value = payload["context"] if name == "context" else row.get(name)
                if value is None:
                    cells[name] = CSV_NULL
                elif isinstance(value, (dict, list)):
                    cells[name] = canonical(value)
                else:
                    cells[name] = str(value)
                    require(not isinstance(value, str) or (
                        value != CSV_NULL and not value.lstrip().startswith(("=", "+", "-", "@"))
                        and not any(ord(c) < 32 for c in value)),
                        "Unsafe/ambiguous scalar CSV text; canonical export refused")
            writer.writerow(cells)
        body = output.getvalue().encode("utf-8")
    require(len(body) <= MAX_EXPORT_BYTES, "Enrichment exceeds export byte budget; no partial output")
    return body


def validate_review(review: dict, run: ValidatedRun, evidence_root: Path) -> None:
    require(review["schema_version"] == 1 and review["constraint_completion_sha256"] == run.completion_sha256,
            "Map review must bind the exact completed constraint run")
    checked = datetime.fromisoformat(review["reviewed_at"])
    require(checked.tzinfo is not None and checked <= datetime.now(UTC), "Invalid/future map review date")
    require(review["method"] in {"official_map_visual_comparison", "synthetic_fixture"}, "Unknown map review method")
    require(isinstance(review["findings"], str) and 0 < len(review["findings"]) <= 8000,
            "Explicit map review findings required")
    ids = {r["parcel_id"] for r in read_artifact_json(run, "constraints.json")}
    samples = review["samples"]
    require(isinstance(samples, list) and 1 <= len(samples) <= 15, "Select bounded representative map samples")
    require(len({r["parcel_id"] for r in samples}) == len(samples), "Duplicate map-review parcel")
    for sample in samples:
        require(sample["parcel_id"] in ids and isinstance(sample["finding"], str)
                and 0 < len(sample["finding"]) <= 4000, "Invalid map-review parcel/finding")
        require(isinstance(sample["urls"], list) and sample["urls"], "Official map URLs required")
        for value in sample["urls"]:
            url = urlsplit(value)
            require(url.scheme == "https" and url.username is None and url.password is None
                    and url.hostname in {"gis.co.isanti.mn.us", "wetland-finder.dnr.state.mn.us",
                        "enterprise.gisdata.mn.gov", "hazards.fema.gov", "msc.fema.gov",
                        "hazards-fema.maps.arcgis.com"}, "Unreviewed map URL destination")
    require(isinstance(review["evidence"], list) and 1 <= len(review["evidence"]) <= 30,
            "Retained map review evidence required")
    names = set()
    for item in review["evidence"]:
        name = item["file"]
        require(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,90}\.(png|jpg|json|md)", name)
                is not None and name != "review.json" and name not in names, "Unsafe/duplicate review evidence name")
        names.add(name)
        file = safe_path(evidence_root, name)
        require(file.stat().st_size <= MAX_EXPORT_BYTES and sha256_file(file) == item["sha256"],
                "Missing/changed map review evidence")


def publish_enrichment(constraint_snapshot: Path, report: Path, *, output_root: Path) -> Path:
    selected = validate_run(constraint_snapshot, "constraint_analysis")
    review = read_json(report)
    validate_review(review, selected, report.parent)
    target = workspace_path(output_root).resolve()
    require(not selected.path.resolve().is_relative_to(target)
            and not report.resolve().is_relative_to(target)
            and not any((p / marker).exists() for p in (target, *target.parents)
                        for marker in ("completion.json", "reservation.json", "failure.json")),
            "Choose a dedicated enrichment output root outside source/review evidence")
    with RunWorkspace(output_root, "suitability_enrichment") as run:
        run.stage = "pin_suitability_sources"
        pinned = validate_run(run.pin(selected.path, "constraints"), "constraint_analysis")
        destination = run.path / "validation"
        destination.mkdir()
        for item in review["evidence"]:
            shutil.copyfile(safe_path(report.parent, item["file"]), destination / item["file"])
        write_json(destination / "review.json", review)
        validate_review(review, pinned, destination)
        run.stage = "project_canonical_suitability"
        payload = project(pinned, review)
        write_json(run.path / "enrichment.json", payload)
        with (run.path / "enrichment.csv").open("xb") as handle:
            handle.write(serialize(payload, "csv"))
        write_json(run.path / "manifest.json", {
            "schema_version": 1, "algorithm": ALGORITHM, "network_requests": 0,
            "published_at": datetime.now(UTC).isoformat(), "csv_fields": list(CSV_FIELDS),
            "summary": {"parcels": len(payload["records"]), **{
                name: sum(r["status"] == name for r in payload["records"]) for name in ("complete", "held")}},
            "warnings": list(WARNINGS),
        })
        run.stage = "validate_enrichment_publication"
        run.publish(row_counts={"enrichment.json": len(payload["records"]),
                                "enrichment.csv": len(payload["records"])})
    return run.path


def validate_enrichment_content(path: Path, completion: dict, manifest: dict, source: ValidatedRun) -> None:
    require(manifest["schema_version"] == 1 and manifest["algorithm"] == ALGORITHM
            and manifest["network_requests"] == 0 and manifest["csv_fields"] == list(CSV_FIELDS)
            and manifest["warnings"] == list(WARNINGS), "Changed suitability export schema/policy")
    review = read_json(safe_path(path, "validation/review.json"))
    validate_review(review, source, path / "validation")
    published = datetime.fromisoformat(manifest["published_at"])
    require(published.tzinfo is not None
            and datetime.fromisoformat(review["reviewed_at"]) <= published
            <= datetime.fromisoformat(completion["created_at"]), "Invalid enrichment publication chronology")
    expected = project(source, review)
    require(read_json(path / "enrichment.json") == expected, "Suitability JSON does not reproduce")
    require(safe_path(path, "enrichment.csv").read_bytes() == serialize(expected, "csv"),
            "Suitability CSV does not reproduce")
    count = len(expected["records"])
    require(completion["row_counts"] == {"enrichment.json": count, "enrichment.csv": count}
            and manifest["summary"] == {"parcels": count, **{
                name: sum(r["status"] == name for r in expected["records"]) for name in ("complete", "held")}},
            "Suitability row/summary accounting differs")
