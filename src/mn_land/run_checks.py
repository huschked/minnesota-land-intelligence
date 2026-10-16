"""Content/row reconciliation for version 2 completion manifests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from mn_land.ingestion.source_checks import integer, inventory, metadata_contract, transfer_flag
from mn_land.runs import (
    JOIN_OUTPUTS,
    PARCEL_OUTPUTS,
    REVIEW_OUTPUTS,
    RunValidationError,
    artifact_row_count,
    read_json,
    safe_path,
)


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise RunValidationError(reason)


def parcel_ids(path: Path) -> set[int]:
    """Recheck complete acquisition against actual retained pages and inventories."""
    manifest = read_json(path / "manifest.json")
    from mn_land.provenance import sha256_file

    captured = manifest["provenance"]["outputs"]
    metadata_references = [
        entry["path"] for entry in captured if Path(entry["path"]).name == "layer_metadata.json"
    ]
    _require(len(metadata_references) == 1, "Missing/duplicate acquisition provenance anchor")
    origin = Path(metadata_references[0]).parent
    for entry in captured:
        relative = Path(entry["path"]).relative_to(origin).as_posix()
        _require(
            sha256_file(safe_path(path, relative)) == entry["sha256"],
            "Acquisition evidence changed after capture",
        )
    before, after = (
        read_json(path / "layer_metadata.json"),
        read_json(path / "layer_metadata_end.json"),
    )
    from mn_land.counties.isanti import IsantiAdapter

    IsantiAdapter.validate_metadata(before)
    IsantiAdapter.validate_metadata(after)
    start = metadata_contract(
        before, manifest["layer_id"], manifest["out_fields"], IsantiAdapter.layer_name
    )
    end = metadata_contract(
        after, manifest["layer_id"], manifest["out_fields"], IsantiAdapter.layer_name
    )
    _require(start == end, "Raw metadata changed during acquisition")
    expected = integer(manifest["record_count"], "record_count", minimum=0)
    oid = start["object_id"]
    initial_count = integer(read_json(path / "count_start.json")["count"], "start count", minimum=0)
    final_count = integer(read_json(path / "count_end.json")["count"], "end count", minimum=0)
    _require(initial_count == final_count == expected, "Raw counts do not reconcile")
    limit = manifest["retrieval_policy"]["max_inventory_ids"]
    first = inventory(read_json(path / "ids_start.json"), expected, oid, limit, "start")
    last = inventory(read_json(path / "ids_end.json"), expected, oid, limit, "end")
    _require(first == last, "Raw membership changed during acquisition")
    page_size = integer(manifest["page_size"], "page size", minimum=1)
    _require(page_size <= start["max_record_count"], "Page size exceeds advertised maximum")
    pages = sorted(path.glob("page_*.json"))
    _require(len(pages) == integer(manifest["pages"], "pages", minimum=0), "Missing raw pages")
    seen: set[int] = set()
    previous = None
    for number, page in enumerate(pages, 1):
        _require(page.name == f"page_{number:05d}.json", "Nonsequential raw pages")
        payload = read_json(page)
        features = payload["features"]
        _require(
            isinstance(features, list) and 0 < len(features) <= page_size, "Malformed raw page"
        )
        for feature in features:
            value = integer(feature["attributes"][oid], "retained OID")
            _require(
                value in first and value not in seen and (previous is None or previous < value),
                "Raw OID membership/order mismatch",
            )
            previous = value
            seen.add(value)
        flag = transfer_flag(payload, page.name)
        _require(
            not (flag is True and len(seen) >= expected)
            and not (flag is False and len(seen) < expected),
            "Retained transfer flag contradicts completeness",
        )
    _require(seen == first, "Raw pages/inventory mismatch")
    return seen


def _source(path: Path, completion: dict, label: str) -> Path:
    ref = next(ref for ref in completion["sources"] if ref["label"] == label)
    return safe_path(path, ref["path"], directory=True)


def _set(values: Any) -> set[int]:
    _require(
        isinstance(values, list) and all(type(value) is int for value in values),
        "Invalid source-row identities",
    )
    result = set(values)
    _require(len(result) == len(values), "Repeated source-row identity")
    return result


def validate_content(path: Path, completion: dict, manifest: dict) -> None:
    kind = completion["kind"]
    files = {entry["path"] for entry in completion["artifacts"]}
    if kind == "parcel_raw":
        _require(
            {
                "manifest.json",
                "layer_metadata.json",
                "layer_metadata_end.json",
                "count_start.json",
                "count_end.json",
                "ids_start.json",
                "ids_end.json",
            }
            <= files,
            "Missing raw acquisition artifacts",
        )
        parcel_ids(path)
        return
    if kind == "delinquency_raw":
        _require(
            "manifest.json" in files and "mapping.json" in files,
            "Missing raw import mapping/manifest",
        )
        source_name = manifest["source_file"]
        _require(
            source_name in {"source.csv", "source.xlsx"} and source_name in files,
            "Missing raw source",
        )
        from mn_land.config.input_limits import InputLimits
        from mn_land.delinquency.file_loader import DelinquencyMapping, FileDelinquencySource
        from mn_land.delinquency.tabular import read_table
        from mn_land.provenance import sha256_file

        limits = InputLimits(**manifest["input_limits"])
        mapping = DelinquencyMapping.from_json(
            path / "mapping.json",
            supporting_root=path / "supporting",
            limits=limits,
        )
        _, rows = read_table(path / source_name, limits)
        records = FileDelinquencySource(
            path / source_name,
            mapping,
            limits=limits,
            retrieved_at=datetime.fromisoformat(manifest["imported_at"]),
        ).load_records()
        _require(
            len(rows) == len(records) == integer(manifest["record_count"], "records", minimum=0),
            "Raw import row mismatch",
        )
        _require(
            manifest["source_sha256"] == sha256_file(path / source_name)
            and manifest["mapping_sha256"] == sha256_file(path / "mapping.json"),
            "Raw import hash mismatch",
        )
        _require(
            {f"supporting/{name}" for name in mapping.supporting_documents} <= files,
            "Missing retained supporting evidence",
        )
        supporting = manifest["supporting_documents"]
        _require(
            {entry["file"] for entry in supporting}
            == {f"supporting/{name}" for name in mapping.supporting_documents}
            and all(
                sha256_file(safe_path(path, entry["file"])) == entry["sha256"]
                for entry in supporting
            ),
            "Supporting bytes changed after capture",
        )
        return

    expected = set(
        PARCEL_OUTPUTS
        if kind == "parcel_processed"
        else JOIN_OUTPUTS
        if kind == "delinquency_processed"
        else REVIEW_OUTPUTS
    )
    required = (
        {"summary.json"}
        if kind == "review"
        else {"manifest.json", "accounting.json", "normalization_diagnostics.json"}
    )
    if kind == "parcel_processed":
        required.add("execution.json")
    _require(expected | required <= files, "Missing required processed exports")
    counter_fields = {
        "parcel_processed": ("retrieved", "normalized", "quarantined", "candidates"),
        "delinquency_processed": (
            "parcel_records_loaded",
            "parcel_normalization_errors",
            "delinquency_records_loaded",
            "unmatched_delinquency_records",
            "ambiguous_records",
            "verified_candidates",
            "current_year_view_count",
            "prior_year_source_rows",
            "current_year_source_rows",
        ),
        "review": (
            "large_listing_matches",
            "duplicate_parcel_groups",
            "unmatched_distinct_parcels",
            "worklist_records",
            "parcel_normalization_errors",
            "unmatched_source_rows",
        ),
    }
    for name in counter_fields[kind]:
        integer(manifest[name], name, minimum=0)
    counts = completion["row_counts"]
    _require(
        isinstance(counts, dict) and set(counts) == expected, "Output row-count inventory mismatch"
    )
    for name, count in counts.items():
        _require(
            type(count) is int and count >= 0 and artifact_row_count(path / name) == count,
            "Actual output rows do not reconcile",
        )
    if kind == "parcel_processed":
        accounting = read_json(path / "accounting.json")
        normalized, quarantined = (
            _set(accounting["normalized_source_ids"]),
            _set(accounting["quarantined_source_ids"]),
        )
        ids = parcel_ids(_source(path, completion, "parcel"))
        _require(
            not normalized & quarantined and normalized | quarantined == ids,
            "Retrieved != normalized + quarantined",
        )
        diagnostics = read_json(path / "normalization_diagnostics.json")
        errors = [entry for entry in diagnostics if entry.get("severity") == "error"]
        _require(
            {entry["source_record_id"] for entry in errors} == quarantined
            and len(errors) == len(quarantined),
            "Quarantine diagnostics do not reconcile",
        )
        _require(
            all("raw_page" in entry and "feature_number" in entry for entry in errors),
            "Quarantine source locations missing",
        )
        _require(
            manifest["retrieved"] == len(ids)
            and manifest["normalized"] == len(normalized)
            and manifest["quarantined"] == len(quarantined),
            "Parcel operation count mismatch",
        )
        _require(
            counts["isanti_candidates.csv"]
            == counts["isanti_candidates.json"]
            == manifest["candidates"],
            "Candidate export count mismatch",
        )
    elif kind == "delinquency_processed":
        from mn_land.delinquency.tabular import read_table

        raw = _source(path, completion, "delinquency")
        from mn_land.config.input_limits import InputLimits

        raw_manifest = read_json(raw / "manifest.json")
        _, rows = read_table(
            raw / raw_manifest["source_file"], InputLimits(**raw_manifest["input_limits"])
        )
        ids = parcel_ids(_source(path, completion, "parcel"))
        diagnostics = read_json(path / "normalization_diagnostics.json")
        errors = [entry for entry in diagnostics if entry.get("severity") == "error"]
        error_ids = {entry["source_record_id"] for entry in errors}
        _require(
            error_ids <= ids
            and len(error_ids) == len(errors)
            and len(errors) == manifest["parcel_normalization_errors"]
            and len(ids) - len(errors) == manifest["parcel_records_loaded"]
            and all("raw_page" in entry and "feature_number" in entry for entry in errors),
            "Joined GIS quarantine accounting mismatch",
        )
        expected_rows = {row.number for row in rows}
        accounting = read_json(path / "accounting.json")
        matched, unmatched, ambiguous = (
            _set(accounting[name]) for name in ("matched", "unmatched", "ambiguous")
        )
        _require(
            not (matched & unmatched or matched & ambiguous or unmatched & ambiguous)
            and matched | unmatched | ambiguous == expected_rows,
            "Join source-row partition does not reconcile",
        )
        periods = [
            _set(accounting[name]) for name in ("prior_year", "current_year", "unverified_period")
        ]
        _require(
            sum(map(len, periods)) == len(set.union(*periods))
            and set.union(*periods) == expected_rows,
            "Tax-period source rows overlap or are missing",
        )
        duplicate_rows = _set(accounting["duplicate_review"])
        _require(
            duplicate_rows <= expected_rows,
            "Duplicate review must overlap, not enlarge, the source partition",
        )
        _require(
            manifest["delinquency_records_loaded"] == len(expected_rows)
            and manifest["unmatched_delinquency_records"] == len(unmatched)
            and manifest["ambiguous_records"] == len(ambiguous),
            "Join operation counts disagree",
        )
        _require(
            counts["isanti_unmatched_delinquency_records.csv"] == len(unmatched)
            and counts["isanti_duplicate_delinquency_records.csv"] == len(duplicate_rows),
            "Issue-export row accounting mismatch",
        )
        for stem, field in (
            ("isanti_verified_delinquent_candidates", "verified_candidates"),
            ("isanti_overdue_current_year_parcels", "current_year_view_count"),
        ):
            _require(
                counts[f"{stem}.csv"] == counts[f"{stem}.json"] == manifest[field],
                "Period view export mismatch",
            )
        _require(
            manifest["prior_year_source_rows"] == len(periods[0])
            and manifest["current_year_source_rows"] == len(periods[1]),
            "Period totals disagree",
        )
    else:
        join = read_json(_source(path, completion, "join") / "manifest.json")
        _require(
            manifest["parcel_normalization_errors"] == join["parcel_normalization_errors"]
            and manifest["unmatched_source_rows"] == join["unmatched_delinquency_records"],
            "Review source accounting differs from pinned join",
        )
        _require(
            counts["isanti_candidate_review.csv"] == manifest["large_listing_matches"],
            "Review candidate counts disagree",
        )
        _require(
            counts["isanti_land_review.csv"] + counts["isanti_PILT_exempt_review.csv"]
            == manifest["large_listing_matches"],
            "Review buckets do not partition candidates",
        )
        _require(
            counts["isanti_duplicate_group_review.csv"] == manifest["duplicate_parcel_groups"]
            and counts["isanti_unmatched_parcel_review.csv"]
            == manifest["unmatched_distinct_parcels"]
            and counts["isanti_county_verification_worklist.csv"] == manifest["worklist_records"],
            "Review issue/worklist counts disagree",
        )
