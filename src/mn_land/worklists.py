"""Immutable contextual worklists and spreadsheet-safe presentation serialization.

No disk writes, Streamlit, acquisition, source editing or monetary aggregation.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import asdict, dataclass
from datetime import datetime

from mn_land.parcel_details import MONEY
from mn_land.parcel_table import (
    ParcelDataset,
    ParcelIdentity,
    TableFilters,
    number,
    query,
    selected_row,
)

MAX_ROWS = 20_000
MAX_OUTPUT_BYTES = 32 * 1024 * 1024
CSV_POLICY = (
    "All CSV data text cells are prefixed with an apostrophe and all fields are quoted. "
    "UNKNOWN is a null marker, not zero. Decimal values are exact text. "
    "Protection changes presentation only; JSON preserves canonical values/nulls. "
    "No universal spreadsheet/re-save guarantee: do not strip protection or treat CSV as authoritative raw data."
)
WARNINGS = (
    "Research worklist only, not an offer list, purchase recommendation or owner-contact instruction.",
    "Dated prior/current views can overlap. Records here are distinct parcels; do not add period counts.",
    "Current payment status is unknown; monetary observations are not summed or inferred.",
    "GIS owner text is independent of listing owner observations; no preferred owner is inferred.",
    "Snapshot-wide issue rows are NOT filtered candidates, can overlap each other, and are not unique-parcel totals.",
    "Access, usable/buildable acreage, zoning, resale value and profit are not assessed.",
)


def canonical(value: object) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


@dataclass(frozen=True, slots=True)
class Worklist:
    dataset: ParcelDataset
    filters: TableFilters
    scope: str
    identity: ParcelIdentity | None
    checked_at: datetime
    document: str

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.document.encode("utf-8")).hexdigest()

    def payload(self) -> dict:
        return json.loads(self.document)


def issue_rows(body: bytes, fields: tuple[str, ...], expected: int) -> list[dict]:
    """Parse generated saved CSV only; reject missing rows/columns and over-budget files."""
    if len(body) > MAX_OUTPUT_BYTES or expected > MAX_ROWS or expected < 0:
        raise ValueError("Issue table exceeds export budget")
    if not body.strip() and expected == 0:
        return []
    reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig"), newline=""), strict=True)
    headers = reader.fieldnames
    if not headers or len(headers) != len(set(headers)) or not set(fields) <= set(headers):
        raise ValueError("Incompatible issue table columns")
    rows = []
    for row in reader:
        if len(rows) >= MAX_ROWS or None in row or any(value is None for value in row.values()):
            raise ValueError("Invalid issue table row")
        rows.append({field: row[field] or None for field in fields})
    if len(rows) != expected:
        raise ValueError("Issue table count differs from inventory")
    return rows


def _period(record: dict | None) -> dict | None:
    if record is None:
        return None
    years = {}
    for field in ("assessment_years", "taxes_payable_years"):
        values = record[field]
        if values is not None and (
            not isinstance(values, list)
            or any(type(year) is not int or not 1000 <= year <= 9999 for year in values)
            or len(values) != len(set(values))
        ):
            raise ValueError("Invalid canonical period years")
        years[field] = values
    return {
        **years,
        "status": record["delinquency_status"],
        "source_rows": [
            {"row": row["source_row_number"], "sheet": row["source_metadata"].get("source_sheet")}
            for row in record["delinquency_source_records"]
        ],
        "balance_aggregation_status": record["balance_aggregation_status"],
        **{
            field: str(number(record[field])) if record[field] is not None else None
            for field in MONEY
        },
    }


def project_worklist(
    dataset: ParcelDataset,
    filters: TableFilters,
    prior: list[dict],
    current: list[dict],
    issues: list[dict],
    context: dict,
    *,
    checked_at: datetime,
    scope: str = "filtered",
    identity: ParcelIdentity | None = None,
) -> Worklist:
    if scope not in {"filtered", "selected"} or (scope == "filtered" and identity is not None):
        raise ValueError("Invalid export scope")
    result = query(dataset, filters)
    rows = result.filtered
    if scope == "selected":
        row = selected_row(dataset, result, identity) if identity is not None else None
        if row is None:
            raise ValueError("Selected parcel is not in this filtered observation")
        rows = (row,)
    if dataset.overview.holds and rows:
        raise ValueError("Held candidates cannot be exported")
    if len(rows) + len(issues) > MAX_ROWS:
        raise ValueError("Worklist exceeds row budget; no partial export")
    indexes = []
    for records in (prior, current):
        index = {record["parcel_id"]: record for record in records}
        if len(index) != len(records):
            raise ValueError("Duplicate saved candidate identity")
        indexes.append(index)
    candidates = []
    for row in rows:
        periods = [_period(index.get(row.parcel_id)) for index in indexes]
        if (periods[0] is not None, periods[1] is not None) != (row.prior, row.current):
            raise ValueError("Candidate period membership changed")
        candidates.append(
            {
                "parcel_id": row.parcel_id,
                "deeded_acres": str(row.deeded_acres) if row.deeded_acres is not None else None,
                "property_classification": row.property_classification,
                "GIS_owner_text": row.owner_name,
                "improvement_value": str(row.improvement_value)
                if row.improvement_value is not None
                else None,
                "review_bucket": row.bucket,
                "prior_year": periods[0],
                "current_year": periods[1],
                "current_payment_status": "unknown",
            }
        )
    filter_values = asdict(filters)
    for field in ("minimum_acres", "maximum_acres"):
        value = filter_values[field]
        filter_values[field] = str(number(value)) if value is not None else None
    ordered_issues = sorted(
        issues, key=lambda row: (row["kind"], row["artifact"], canonical(row["fields"]))
    )
    counts = {
        kind: sum(row["kind"] == kind for row in ordered_issues)
        for kind in sorted({row["kind"] for row in ordered_issues})
    }
    payload = {
        "schema_version": 1,
        "context": {
            **context,
            "scope": scope,
            "selected_parcel_id": identity.parcel_id if identity else None,
            "filters": filter_values,
            "effective_candidate_floor": str(dataset.minimum_acres),
            "candidate_count": len(candidates),
            "issue_row_count": len(ordered_issues),
            "issue_counts": counts,
            "issue_scope": "whole selected snapshot, independent of candidate filters",
            "view_counts_under_non_view_filters": dict(result.counts),
            "ordering": "active service sort, nulls last, ascending parcel-ID tie-break; all pages",
            "issue_ordering": "kind, artifact, canonical field values (lexical)",
            "holds": list(dataset.overview.holds),
            "warnings": list(WARNINGS) + list(dataset.overview.warnings),
            "csv_presentation": CSV_POLICY,
            "decimal_encoding": "exact base-10 strings; null remains unknown",
        },
        "candidates": candidates,
        "issues": ordered_issues,
    }
    return Worklist(dataset, filters, scope, identity, checked_at, canonical(payload))


def serialize(worklist: Worklist, format: str) -> bytes:
    """A pure serializer, only called by the service after fresh export validation."""
    if format not in {"csv", "json"}:
        raise ValueError("Unsupported worklist format")
    payload = worklist.payload()
    payload["context"]["integrity_checked_at"] = worklist.checked_at.isoformat()
    payload["context"]["preview_fingerprint"] = worklist.fingerprint
    if format == "json":
        body = (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode(
            "utf-8"
        )
    else:
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
        writer.writerow(
            (
                "record_type",
                "parcel_id",
                "GIS_owner_text",
                "deeded_acres",
                "improvement_value",
                "property_classification",
                "prior_year_json",
                "current_year_json",
                "issue_kind",
                "source_artifact",
                "issue_fields_json",
                "candidate_json",
                "context_json",
            )
        )
        context = canonical(payload["context"])
        records = [
            (
                "candidate",
                row["parcel_id"],
                row["GIS_owner_text"],
                row["deeded_acres"],
                row["improvement_value"],
                row["property_classification"],
                canonical(row["prior_year"]),
                canonical(row["current_year"]),
                None,
                None,
                None,
                canonical(row),
                context,
            )
            for row in payload["candidates"]
        ] + [
            (
                "issue",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                row["kind"],
                row["artifact"],
                canonical(row["fields"]),
                None,
                context,
            )
            for row in payload["issues"]
        ]
        for record in records or [("context_only", *([None] * 11), context)]:
            # Protect every text cell, including whitespace/control/formula-leading
            # values and exact decimal/ID text. CSV quoting alone is not protection.
            writer.writerow("UNKNOWN" if value is None else "'" + str(value) for value in record)
            if stream.tell() > MAX_OUTPUT_BYTES:
                raise ValueError("CSV exceeds output budget; no partial export")
        body = stream.getvalue().encode("utf-8-sig")
    if len(body) > MAX_OUTPUT_BYTES:
        raise ValueError("Worklist exceeds output byte budget")
    return body
