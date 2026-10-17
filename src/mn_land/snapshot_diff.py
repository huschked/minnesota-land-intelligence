"""Explicit offline observations across completed joins, never a payment inference."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from mn_land.config.input_limits import InputLimits
from mn_land.config.settings import SETTINGS
from mn_land.counties.isanti import IsantiAdapter
from mn_land.counties.isanti.delinquency import normalize_parcel_id
from mn_land.delinquency.file_loader import DelinquencyMapping, FileDelinquencySource
from mn_land.delinquency.join import join_delinquency_records
from mn_land.delinquency.pipeline import load_parcel_snapshot
from mn_land.provenance import build_provenance
from mn_land.replay import check_destination, input_dates, normalized_digest
from mn_land.runs import (
    RunValidationError,
    RunWorkspace,
    ValidatedRun,
    read_artifact_json,
    read_json,
    safe_path,
    validate_run,
    write_json,
)
from mn_land.utils.validation import minimum_acres

LIMITATIONS = [
    "Missing means not observed in that listing, never paid, cleared or currently tax-current.",
    "Added/missing GIS IDs do not establish splits, mergers or retirement relationships.",
    "All current payment statuses remain unknown. Source tax statuses are dated observations.",
    "Raw monetary rows are unaggregated evidence; no debt, motivation or purchase score is calculated.",
    "Freshness is an operator calendar-day policy, not a county payment or validity determination.",
]


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value == 0:
            return "0"
        text = format(value, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _ordered(values: list[dict]) -> list[dict]:
    return sorted(values, key=lambda value: json.dumps(value, sort_keys=True, allow_nan=False))


def _policy(as_of: date, stale_after_days: int) -> None:
    if type(as_of) is not date or type(stale_after_days) is not int or not 0 <= stale_after_days <= 36500:
        raise RunValidationError("Use a date and a stale-after-days integer from 0 through 36500")


def _age(value: str | None, as_of: date, days: int, *, timestamp: bool = False) -> dict:
    if value is None:
        return {"source_date": None, "age_days": None, "state": "unknown"}
    parsed = datetime.fromisoformat(value) if timestamp else date.fromisoformat(value)
    if timestamp:
        if parsed.tzinfo is None:
            raise RunValidationError("Capture timestamps require a timezone")
        observed_date = parsed.astimezone(UTC).date()
    else:
        observed_date = parsed
    age = (as_of - observed_date).days
    return {
        "source_date": value, "age_days": age,
        "state": "future_dated" if age < 0 else "stale" if age > days else "within_policy",
    }


def _child(parent: ValidatedRun, label: str, kind: str) -> ValidatedRun:
    child = validate_run(parent.source(label), kind)
    reference = next(ref for ref in parent.completion["sources"] if ref["label"] == label)
    if reference["completion_sha256"] != child.completion_sha256:
        raise RunValidationError("Pinned source changed during comparison")
    return child


@dataclass
class _Observation:
    context: dict
    profile: dict
    gis_ids: set[str]
    parcels: dict[str, dict]
    gis_records: dict[str, list[dict]]


def _load(path: Path, as_of: date, days: int) -> _Observation:
    selected = validate_run(path, "delinquency_processed")
    raw_gis = _child(selected, "parcel", "parcel_raw")
    raw_file = _child(selected, "delinquency", "delinquency_raw")
    gis = read_artifact_json(raw_gis, "manifest.json")
    imported = read_artifact_json(raw_file, "manifest.json")
    mapping_body = read_artifact_json(raw_file, "mapping.json")
    manifest = read_artifact_json(selected, "manifest.json")
    limits = InputLimits(**imported["input_limits"])
    mapping = DelinquencyMapping.from_json(
        raw_file.path / "mapping.json", supporting_root=raw_file.path / "supporting", limits=limits,
    )
    records = FileDelinquencySource(
        raw_file.path / imported["source_file"], mapping, limits=limits,
        retrieved_at=datetime.fromisoformat(imported["imported_at"]),
    ).load_records()
    parcels, errors, _ = load_parcel_snapshot(IsantiAdapter(), raw_gis.path)
    fingerprints = manifest.get("reproducibility")
    if not fingerprints or (
        fingerprints["normalized_parcels_sha256"] != normalized_digest(parcels)
        or fingerprints["normalized_delinquency_sha256"] != normalized_digest(records)
    ):
        raise RunValidationError("Comparison requires recorded, reproducible normalized inputs")
    if gis.get("where") != "1=1":
        raise RunValidationError("Comparison requires full-county GIS observations")
    # Reuse the canonical join's holds, duplicate handling and tax-period rules.
    joined = join_delinquency_records(parcels, records)
    gis_index: dict[str, list[dict]] = defaultdict(list)
    for parcel in parcels:
        values = asdict(parcel)
        for name in ("source_metadata", "geometry"):
            values.pop(name)
        gis_index[normalize_parcel_id(parcel.parcel_id)].append(_json_value(values))
    record_index: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        values = asdict(record)
        metadata = values.pop("source_metadata")
        row_number = values.pop("source_row_number")
        record_index[record.normalized_parcel_id].append({
            "values": _json_value(values), "source_row_number": row_number,
            "source_sheet": metadata["source_sheet"],
        })
    statuses: dict[str, set[str]] = defaultdict(set)
    for match in joined.matches:
        statuses[normalize_parcel_id(match.parcel.parcel_id)].add(match.status.value)
    for status, group in (("unmatched", joined.unmatched_records), ("ambiguous", joined.ambiguous_records)):
        for record in group:
            statuses[record.normalized_parcel_id].add(status)
    views = {
        "prior_year_large": {row["parcel_id"] for row in read_artifact_json(
            selected, "isanti_verified_delinquent_candidates.json"
        )},
        "current_year_overdue_large": {row["parcel_id"] for row in read_artifact_json(
            selected, "isanti_overdue_current_year_parcels.json"
        )},
    }
    views = {label: {normalize_parcel_id(key) for key in ids} for label, ids in views.items()}
    projected = {
        key: {
            "listing_observed": True,
            "listing_rows": _ordered(rows), "gis_records": _ordered(gis_index.get(key, [])),
            "dated_join_statuses": sorted(statuses[key]),
            "views": {label: key in ids for label, ids in views.items()},
        } for key, rows in record_index.items()
    }
    context = {
        "join_run_id": selected.path.name, "join_completion_sha256": selected.completion_sha256,
        "parcel_run_id": raw_gis.path.name, "import_run_id": raw_file.path.name,
        "parcel_completion_sha256": raw_gis.completion_sha256,
        "import_completion_sha256": raw_file.completion_sha256,
        "source_dates": input_dates(gis, imported, mapping.publication_date),
        "source_agency": mapping.source_agency, "dataset": mapping.dataset,
        "listing_sha256": imported["source_sha256"], "mapping_sha256": imported["mapping_sha256"],
        "year_convention": mapping.tax_year_convention,
        "report_payable_years": sorted({r.report_taxes_payable_year for r in records if r.report_taxes_payable_year is not None}),
        "source_hold": mapping.verification_hold_reason,
        "minimum_acres": str(minimum_acres(manifest["minimum_acres"])),
        "listing_rows": len(records), "listing_distinct_ids": len(record_index),
        "normalized_gis_records": len(parcels), "gis_quarantined_records": errors,
        "view_counts": {name: len(ids) for name, ids in views.items()},
        "freshness": {
            "listing_publication": _age(mapping.publication_date, as_of, days),
            "listing_capture": _age(imported["imported_at"], as_of, days, timestamp=True),
            "gis_capture": _age(gis["retrieved_at"], as_of, days, timestamp=True),
        },
        "synthetic": (
            selected.completion["provenance"]["code"].get("git", {}).get("status") == "synthetic_test_fixture"
            or any(word in mapping.dataset.lower() for word in ("synthetic", "test fixture"))
        ),
    }
    # The profile permits annual dataset names, publication dates, evidence bytes
    # and hold changes, but not silently different meaning/mappings/thresholds.
    profile = {
        "gis_source": [gis["service_url"], gis["layer_id"], gis["where"], sorted(gis["out_fields"])],
        "mapping": {name: mapping_body.get(name) for name in (
            "source_agency", "source_url", "columns", "delinquency_assertion", "tax_year_convention",
        )},
        "minimum_acres": str(minimum_acres(manifest["minimum_acres"]).normalize()),
    }
    validate_run(selected.path, "delinquency_processed")  # recheck all reads before accepting observation
    return _Observation(context, profile, set(gis_index), projected, dict(gis_index))


def _semantics(observation: dict) -> dict:
    return {
        **observation,
        "listing_rows": _ordered([row["values"] for row in observation["listing_rows"]]),
    }


def build_difference(before: Path, after: Path, *, as_of: date, stale_after_days: int) -> tuple[dict, list]:
    """Deterministic payload for explicitly ordered compatible completed joins."""
    _policy(as_of, stale_after_days)
    old, new = _load(before, as_of, stale_after_days), _load(after, as_of, stale_after_days)
    if old.profile != new.profile:
        raise RunValidationError("Comparison source, mapping semantics or candidate thresholds are incompatible")
    changes = []
    for key in sorted(old.parcels.keys() | new.parcels.keys()):
        states = []
        for observed in (old, new):
            states.append(observed.parcels.get(key, {
                "listing_observed": False, "listing_rows": [],
                "gis_records": _ordered(observed.gis_records.get(key, [])),
                "dated_join_statuses": ["not_observed_in_listing"],
                "views": {"prior_year_large": False, "current_year_overdue_large": False},
            }))
        left, right = states
        left_values, right_values = _semantics(left), _semantics(right)
        fields = [name for name, value in left_values.items() if value != right_values[name]]
        change = (
            "added" if key not in old.parcels else "missing" if key not in new.parcels
            else "changed" if fields else "unchanged"
        )
        changes.append({
            "parcel_id": key, "change": change, "changed_fields": fields,
            "before": left, "after": right,
            "current_payment_status": "unknown", "identity_relationship": "not_inferred",
        })
    warnings = []
    for side, observed in (("before", old), ("after", new)):
        for name, age in observed.context["freshness"].items():
            if age["state"] != "within_policy":
                warnings.append(f"{side}: {name} is {age['state']}")
        if observed.context["source_hold"]:
            warnings.append(f"{side}: source hold retained")
    if old.context["listing_sha256"] == new.context["listing_sha256"]:
        warnings.append("Same retained listing bytes; a new capture does not establish refreshed tax status")
    if old.context["mapping_sha256"] != new.context["mapping_sha256"]:
        warnings.append("Mapping/evidence bytes differ; the explicit semantic profiles matched")
    if old.context["report_payable_years"] != new.context["report_payable_years"]:
        warnings.append("Report payable-year populations differ; rollover is not payment evidence")
    for name in ("delinquency_publication_date", "parcel_retrieved_at"):
        left, right = (entry.context["source_dates"][name] for entry in (old, new))
        if left is not None and right is not None and (
            date.fromisoformat(right) < date.fromisoformat(left) if name.endswith("date")
            else datetime.fromisoformat(right) < datetime.fromisoformat(left)
        ):
            warnings.append(f"After source date moved backward: {name}; input order was not changed")
    counts = Counter(row["change"] for row in changes)
    manifest = {
        "schema_version": 1, "algorithm": "listing_observation_diff_v1", "county": "Isanti",
        "as_of": as_of.isoformat(), "as_of_date_basis": "UTC calendar dates",
        "stale_after_days": stale_after_days,
        "freshness_boundary": "age_days > stale_after_days; unknown/future dates are separate states",
        "scope": "Union of normalized listing parcel IDs; below-threshold, held and unmatched rows included",
        "before": old.context, "after": new.context,
        "summary": {name: counts[name] for name in ("added", "changed", "missing", "unchanged")},
        "normalized_gis_id_changes": {
            "added": sorted(new.gis_ids - old.gis_ids), "missing": sorted(old.gis_ids - new.gis_ids),
            "identity_relationships": "unknown; no split, merger or retirement inferred",
        },
        "warnings": warnings, "limitations": LIMITATIONS,
    }
    return manifest, changes


def compare_snapshots(
    before: Path, after: Path, *, as_of: date, stale_after_days: int = 30,
    processed_root: Path | None = None,
) -> Path:
    """Pin both complete joins and publish a new comparison, never refresh sources."""
    _policy(as_of, stale_after_days)
    before = validate_run(before, "delinquency_processed").path
    after = validate_run(after, "delinquency_processed").path
    root = (processed_root or SETTINGS.processed_dir) / "isanti" / "comparisons"
    check_destination(root, before, after)
    with RunWorkspace(root, "comparison") as run:
        run.stage = "pin_comparison_inputs"
        old, new = run.pin(before, "before"), run.pin(after, "after")
        run.stage = "compare_observations"
        manifest, rows = build_difference(old, new, as_of=as_of, stale_after_days=stale_after_days)
        write_json(run.path / "changes.json", rows)
        manifest["provenance"] = build_provenance(
            {"command": "compare-snapshots", "as_of": as_of.isoformat(), "stale_after_days": stale_after_days},
            inputs=[old / "completion.json", new / "completion.json"], outputs=[run.path / "changes.json"],
        )
        write_json(run.path / "manifest.json", manifest)
        run.counts.update(manifest["summary"])
        run.publish(row_counts={"changes.json": len(rows)})
    return run.path


def validate_comparison_content(path: Path, completion: dict, manifest: dict) -> None:
    """Resealed reports cannot claim payment, drop warnings or fabricate diffs."""
    if not {"changes.json", "manifest.json"} <= {item["path"] for item in completion["artifacts"]}:
        raise RunValidationError("Missing comparison outputs")
    refs = {ref["label"]: ref for ref in completion["sources"]}
    expected, rows = build_difference(
        safe_path(path, refs["before"]["path"], directory=True),
        safe_path(path, refs["after"]["path"], directory=True),
        as_of=date.fromisoformat(manifest["as_of"]), stale_after_days=manifest["stale_after_days"],
    )
    if (
        {key: value for key, value in manifest.items() if key != "provenance"} != expected
        or read_json(safe_path(path, "changes.json")) != rows
        or completion["row_counts"] != {"changes.json": len(rows)}
    ):
        raise RunValidationError("Comparison content differs from its pinned evidence and policy")
