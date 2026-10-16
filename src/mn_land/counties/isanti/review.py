"""Deterministic Phase 1.1 review of preserved Isanti inputs.

This module creates review views; it does not change delinquency status or
interpret abbreviated accounting fields as canonical balances.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from mn_land.config.input_limits import DEFAULT_INPUT_LIMITS
from mn_land.counties.isanti import IsantiAdapter
from mn_land.counties.isanti.delinquency import normalize_parcel_id
from mn_land.delinquency.file_loader import parse_money
from mn_land.delinquency.pipeline import DelinquencyPipelineError, _copy_input, load_parcel_snapshot
from mn_land.delinquency.tabular import read_table
from mn_land.provenance import build_provenance
from mn_land.runs import (
    REVIEW_OUTPUTS,
    RunValidationError,
    RunWorkspace,
    artifact_row_count,
    read_json,
    validate_run,
)
from mn_land.utils.validation import minimum_acres

SPECIAL_CLASSES = {"PILT-Payment In-Lieu of Taxes", "5E-Exempt Properties"}
ACCOUNTING_FIELDS = (
    "TAXAMT",
    "PENAMT",
    "INTAMT",
    "FEEAMT",
    "TOTAMT",
    "PENAMT2",
    "INTAMT2",
    "TOTAMT2",
    "SPAAMT",
    "TAXONLYAMT",
)


def review_bucket(parcel: dict[str, Any]) -> str:
    classification = parcel.get("property_classification") or ""
    if classification in SPECIAL_CLASSES:
        return "PILT_or_exempt_review"
    if "Rural Vacant Land/Non-Productive" in classification:
        return "rural_vacant_classification_review"
    improvement = parse_money(parcel.get("improvement_value"))
    if improvement is None:
        return "unknown_improvement_review"
    if improvement == 0:
        return "zero_improvement_value_review"
    return "positive_improvement_value_review"


def duplicate_profile(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Compare source values without summing or choosing a preferred owner."""
    fiscal_variants = {
        (
            row.get("TAXYR"),
            row.get("ASMTYR"),
            *(parse_money(row.get(field)) for field in ACCOUNTING_FIELDS),
        )
        for row in rows
    }
    return {
        "source_row_count": len(rows),
        "distinct_fiscal_value_sets": len(fiscal_variants),
        "distinct_owner_texts": len({row.get("OWN1") for row in rows}),
        "fiscal_review": (
            "identical_fiscal_values_do_not_sum"
            if len(fiscal_variants) == 1
            else "differing_fiscal_values_do_not_sum"
        ),
    }


def build_review(
    snapshot: Path, min_acres: Decimal = Decimal(10), *, comparison_path: Path | None = None
) -> Path:
    min_acres = minimum_acres(min_acres)
    validate_run(snapshot, "delinquency_processed")
    with RunWorkspace(snapshot.parent.parent / "review", "review") as run:
        run.stage = "pin_review_inputs"
        pinned = run.pin(snapshot, "join")
        comparison_copy = None
        if comparison_path is not None:
            comparison_copy = run.path / "inputs" / "official_report_comparison.json"
            _copy_input(comparison_path, comparison_copy, DEFAULT_INPUT_LIMITS)
            if not isinstance(read_json(comparison_copy), dict):
                raise RunValidationError("Comparison evidence must be an object")
            comparison = read_json(comparison_copy)
            findings = comparison.get("findings", [])
            if (
                not isinstance(findings, list)
                or any(
                    not isinstance(finding, dict)
                    or not isinstance(finding.get("parcel_id"), str)
                    or not isinstance(finding.get("verification_result"), str)
                    for finding in findings
                )
                or (
                    "reports_compared" in comparison
                    and (
                        type(comparison["reports_compared"]) is not int
                        or comparison["reports_compared"] != len(findings)
                    )
                )
                or (
                    "operational_status" in comparison
                    and not isinstance(comparison["operational_status"], str)
                )
            ):
                raise RunValidationError(
                    "Invalid comparison counts, findings or operational status"
                )
        run.stage = "review_exports"
        _write_review(pinned, min_acres, run.path, comparison_copy)
        run.counts["reviewed_candidates"] = read_json(run.path / "summary.json")[
            "large_listing_matches"
        ]
        run.publish(
            row_counts={name: artifact_row_count(run.path / name) for name in REVIEW_OUTPUTS}
        )
    return run.path


def _write_review(
    snapshot: Path, min_acres: Decimal, output: Path, comparison_path: Path | None
) -> Path:
    """Write new review artifacts derived from one explicit import snapshot."""
    min_acres = minimum_acres(min_acres)
    validated = validate_run(snapshot, "delinquency_processed")
    manifest = validated.manifest
    if min_acres < minimum_acres(manifest["minimum_acres"]):
        raise DelinquencyPipelineError(
            "Review minimum acreage cannot be lower than the imported candidate threshold."
        )
    raw_import = validated.source("delinquency")
    source_mapping = (
        json.loads((raw_import / "mapping.json").read_text(encoding="utf-8"))
        if (raw_import / "mapping.json").is_file()
        else {}
    )
    confirmed_years = source_mapping.get("tax_year_convention") == "isanti_assessment_year_plus_one"
    parcel_snapshot = validated.source("parcel")
    candidates = json.loads(
        (snapshot / "isanti_verified_delinquent_candidates.json").read_text(encoding="utf-8")
    )
    candidates = [
        row
        for row in candidates
        if row.get("deeded_acres") is not None and Decimal(row["deeded_acres"]) >= min_acres
    ]
    held = bool(source_mapping.get("verification_hold_reason"))
    comparison = {}
    if comparison_path is not None:
        comparison = read_json(comparison_path)
        held = held or comparison.get("operational_status") == "HOLD_COUNTY_RECONCILIATION_REQUIRED"
    listing_path = raw_import / "source.csv"
    if not listing_path.is_file():
        listing_path = raw_import / "source.xlsx"
    _, source_rows = read_table(listing_path)
    grouped: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
    for entry in source_rows:
        grouped[normalize_parcel_id(entry.values["PARID"])].append((entry.number, entry.values))

    # Pin the exact recorded GIS snapshot, rather than substituting a later run.
    adapter = IsantiAdapter()
    diagnostics: list[dict[str, Any]] = []
    parcels, errors, _ = load_parcel_snapshot(adapter, parcel_snapshot, diagnostics=diagnostics)
    parcel_groups: dict[str, list[Any]] = defaultdict(list)
    for parcel in parcels:
        parcel_groups[normalize_parcel_id(parcel.parcel_id)].append(parcel)

    review_rows = []
    for candidate in sorted(candidates, key=lambda row: row["parcel_id"]):
        records = candidate.get("delinquency_source_records") or [
            {
                "source_row_number": candidate["delinquency_source_row"],
                "original_row": candidate["delinquency_original_row"],
            }
        ]
        originals = [record["original_row"] for record in records]
        owners = sorted({row.get("OWN1") or "" for row in originals})
        review_rows.append(
            {
                "parcel_id": candidate["parcel_id"],
                "deeded_acres": candidate["deeded_acres"],
                "review_bucket": review_bucket(candidate),
                "GIS_owner_name": candidate["owner_name"],
                "county_listing_OWN1": json.dumps(owners, ensure_ascii=False),
                "owner_text_differs": any(candidate["owner_name"] != owner for owner in owners),
                "property_classification": candidate["property_classification"],
                "improvement_value": candidate["improvement_value"],
                "assessed_value": candidate["assessed_value"],
                "listed_TAXYR": _source_values(originals, "TAXYR"),
                "listed_ASMTYR": _source_values(originals, "ASMTYR"),
                "taxes_payable_years": ";".join(
                    str(y) for y in candidate.get("taxes_payable_years") or ()
                )
                or None,
                "delinquency_status": candidate.get("delinquency_status"),
                "source_record_count": len(records),
                "source_TOTAMT_uninterpreted": json.dumps(
                    [
                        {
                            "source_row_number": record["source_row_number"],
                            "ASMTYR": record["original_row"].get("ASMTYR"),
                            "TOTAMT": record["original_row"].get("TOTAMT"),
                        }
                        for record in records
                    ],
                    ensure_ascii=False,
                ),
                "source_EFFDATE": _source_values(originals, "EFFDATE"),
                "source_row_number": candidate["delinquency_source_row"],
                "parcel_report_url": _report_url(candidate["parcel_id"]),
                "county_verification_status": (
                    "hold_county_reconciliation_required"
                    if held
                    else "official_report_positive_prior_year_sample"
                    if any(
                        finding["parcel_id"] == candidate["parcel_id"]
                        and finding["verification_result"]
                        == "positive_outstanding_for_listed_prior_year"
                        for finding in comparison.get("findings", [])
                    )
                    else "listed_prior_year_unpaid_unsampled"
                    if confirmed_years
                    else "pending_official_record_comparison"
                ),
            }
        )
    _csv(output / "isanti_candidate_review.csv", review_rows)
    _csv(
        output / "isanti_land_review.csv",
        [row for row in review_rows if row["review_bucket"] != "PILT_or_exempt_review"],
        tuple(review_rows[0]) if review_rows else (),
    )
    _csv(
        output / "isanti_PILT_exempt_review.csv",
        [row for row in review_rows if row["review_bucket"] == "PILT_or_exempt_review"],
        tuple(review_rows[0]) if review_rows else (),
    )
    _csv(
        output / "isanti_land_focused_review.csv",
        [
            row
            for row in review_rows
            if row["review_bucket"]
            in {"rural_vacant_classification_review", "zero_improvement_value_review"}
        ],
        tuple(review_rows[0]) if review_rows else (),
    )
    duplicate_rows = []
    unmatched_rows = []
    for key, group in sorted(grouped.items()):
        matches = parcel_groups.get(key, [])
        row_refs = ";".join(str(number) for number, _ in group)
        if len(group) > 1:
            duplicate_rows.append(
                {
                    "normalized_parcel_id": key,
                    **duplicate_profile([row for _, row in group]),
                    "source_row_numbers": row_refs,
                    "GIS_match_count": len(matches),
                    "GIS_deeded_acres": (
                        str(matches[0].deeded_acres)
                        if len(matches) == 1 and matches[0].deeded_acres is not None
                        else None
                    ),
                    "GIS_owner_name": matches[0].owner_name if len(matches) == 1 else None,
                    "review_status": (
                        "balance_structure_pending_status_classified"
                        if confirmed_years
                        else "ambiguous_county_explanation_required"
                    ),
                }
            )
        if not matches:
            unmatched_rows.append(
                {
                    "normalized_parcel_id": key,
                    "source_row_count": len(group),
                    "source_row_numbers": row_refs,
                    "listed_TAXYR": ";".join(sorted({str(row["TAXYR"]) for _, row in group})),
                    "original_OWN1_values": json.dumps(
                        sorted({row["OWN1"] for _, row in group}), ensure_ascii=False
                    ),
                    "review_status": "unmatched_requires_county_identity_verification",
                }
            )
    _csv(output / "isanti_duplicate_group_review.csv", duplicate_rows)
    _csv(output / "isanti_unmatched_parcel_review.csv", unmatched_rows)

    # Stratified deterministic sample, not an opportunity ranking.
    buckets = sorted({row["review_bucket"] for row in review_rows})
    sample: list[dict[str, Any]] = []
    for index in range(10):
        for bucket in buckets:
            group = [row for row in review_rows if row["review_bucket"] == bucket]
            if index < len(group) and len(sample) < 10:
                sample.append(group[index])
    _csv(output / "isanti_county_verification_worklist.csv", sample)
    summary = {
        "source_join_snapshot": str(snapshot.resolve()),
        "source_listing_snapshot": str(raw_import),
        "source_parcel_snapshot": str(parcel_snapshot),
        "minimum_acres": str(min_acres),
        "large_listing_matches": len(review_rows),
        "buckets": {
            bucket: sum(row["review_bucket"] == bucket for row in review_rows) for bucket in buckets
        },
        "duplicate_parcel_groups": len(duplicate_rows),
        "identical_fiscal_value_groups": sum(
            row["distinct_fiscal_value_sets"] == 1 for row in duplicate_rows
        ),
        "differing_fiscal_value_groups": sum(
            row["distinct_fiscal_value_sets"] > 1 for row in duplicate_rows
        ),
        "unmatched_distinct_parcels": len(unmatched_rows),
        "unmatched_source_rows": sum(row["source_row_count"] for row in unmatched_rows),
        "duplicate_large_parcels": sum(
            row["GIS_deeded_acres"] is not None and Decimal(row["GIS_deeded_acres"]) >= min_acres
            for row in duplicate_rows
        ),
        "parcel_normalization_errors": errors,
        "parcel_normalization_diagnostics": diagnostics,
        "worklist_records": len(sample),
        "manual_verification_status": (
            "verification_hold"
            if held and not comparison
            else "reports_compared_unreconciled"
            if held
            else "sample_reports_compared"
            if comparison.get("reports_compared")
            else "pending"
        ),
        "official_sample_comparison": str(comparison_path) if comparison_path else None,
        "tax_status_screening_ready": confirmed_years and not held,
        "monetary_analysis_ready": False,
        "accounting_definition_status": "pending_county_data_dictionary",
        "year_semantics_status": "county_confirmed" if confirmed_years else "unverified",
        "delinquency_status_changes": 0,
    }
    summary["provenance"] = build_provenance(
        {"command": "review-delinquency", "county": "Isanti", "minimum_acres": str(min_acres)},
        inputs=[
            snapshot / "manifest.json",
            snapshot / "isanti_verified_delinquent_candidates.json",
            listing_path,
            parcel_snapshot / "manifest.json",
            *parcel_snapshot.glob("page_*.json"),
            *([raw_import / "mapping.json"] if (raw_import / "mapping.json").is_file() else []),
            *([comparison_path] if comparison_path else []),
        ],
        outputs=output.glob("*.csv"),
    )
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return output


def _report_url(parcel_id: str) -> str:
    return "https://gis.co.isanti.mn.us/ParcelReports/PublicParcelReport.ashx?PIN=" + parcel_id


def _source_values(rows: list[dict[str, Any]], field: str) -> str | None:
    values = sorted({str(row[field]) for row in rows if row.get(field) is not None})
    return ";".join(values) or None


def _csv(path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...] | None = None) -> None:
    fields = fields if fields is not None else tuple(rows[0]) if rows else ("review_status",)
    fields = fields or ("review_status",)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
