from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from mn_land.counties.isanti.delinquency import normalize_parcel_id
from mn_land.delinquency.join import JoinResult
from mn_land.models import (
    DelinquencyRecord,
    DelinquencyStatus,
    ParcelDelinquencyMatch,
    TaxPeriodStatus,
)

VERIFIED_FIELDS = (
    "parcel_id",
    "owner_name",
    "taxpayer_name",
    "owner_mailing_address",
    "deeded_acres",
    "delinquent_years",
    "total_taxes_and_penalties_due",
    "delinquent_tax_amount",
    "penalty_amount",
    "current_tax_amount",
    "previous_taxes_owed_source_value",
    "land_value",
    "improvement_value",
    "assessed_value",
    "property_classification",
    "legal_description",
    "delinquency_status",
    "parcel_source",
    "delinquency_source",
    "source_publication_date",
    "parcel_retrieved_at",
    "delinquency_retrieved_at",
    "delinquency_source_row",
    "assessment_years",
    "taxes_payable_years",
    "source_record_count",
    "balance_aggregation_status",
    "has_overdue_current_year",
)


def export_join_result(
    result: JoinResult, output_dir: Path, min_acres: Decimal
) -> tuple[tuple[Path, ...], int]:
    output_dir.mkdir(parents=True, exist_ok=False)
    candidates = [
        match
        for match in result.verified_matches
        if match.parcel.deeded_acres is not None and match.parcel.deeded_acres >= min_acres
    ]
    rows = [_verified_row(match) for match in candidates]
    csv_path = output_dir / "isanti_verified_delinquent_candidates.csv"
    json_path = output_dir / "isanti_verified_delinquent_candidates.json"
    _write_csv(csv_path, VERIFIED_FIELDS, rows)
    with json_path.open("x", encoding="utf-8") as handle:
        json_rows = [_json_row(match) for match in candidates]
        json.dump(json_rows, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    current_matches = [
        match for match in result.exact_matches
        if match.status != DelinquencyStatus.UNVERIFIED
        and match.parcel.deeded_acres is not None and match.parcel.deeded_acres >= min_acres
        and any(r.tax_period_status == TaxPeriodStatus.OVERDUE_CURRENT_YEAR for r in match.records)
    ]
    current_path = output_dir / "isanti_overdue_current_year_parcels.csv"
    current_json = output_dir / "isanti_overdue_current_year_parcels.json"
    _write_csv(current_path, VERIFIED_FIELDS, [_verified_row(match, current=True) for match in current_matches])
    with current_json.open("x", encoding="utf-8") as handle:
        json.dump([_json_row(match, current=True) for match in current_matches], handle, indent=2)
        handle.write("\n")

    review_path = output_dir / "isanti_verified_candidate_review_sample.csv"
    review_fields = (
        "parcel_id",
        "owner_name",
        "deeded_acres",
        "delinquent_years",
        "total_taxes_and_penalties_due",
        "assessed_value",
        "parcel_source",
        "delinquency_source",
        "source_publication_date",
        "delinquency_source_row",
    )
    selected = sorted(rows, key=lambda row: str(row["parcel_id"]))[:10]
    _write_csv(
        review_path,
        review_fields,
        [{field: row[field] for field in review_fields} for row in selected],
    )

    unmatched_path = output_dir / "isanti_unmatched_delinquency_records.csv"
    issue_fields = (
        "original_parcel_id",
        "normalized_parcel_id",
        "source_row_number",
        "source_dataset",
        "source_publication_date",
        "status",
        "assessment_year",
        "taxes_payable_year",
        "tax_period_status",
    )
    _write_csv(
        unmatched_path,
        issue_fields,
        [_issue_row(record, "unmatched") for record in result.unmatched_records],
    )
    duplicates_path = output_dir / "isanti_duplicate_delinquency_records.csv"
    duplicate_rows = [
        _issue_row(record, "duplicate")
        for key in sorted(result.duplicate_records)
        for record in result.duplicate_records[key]
    ]
    _write_csv(duplicates_path, issue_fields, duplicate_rows)
    unverified_path = output_dir / "isanti_unverified_large_parcels.csv"
    _write_csv(
        unverified_path,
        (*VERIFIED_FIELDS, "verification_hold_reason"),
        [
            {**_verified_row(match), "verification_hold_reason": match.reason}
            for match in result.matches
            if match.status == DelinquencyStatus.UNVERIFIED
            and match.parcel.deeded_acres is not None
            and match.parcel.deeded_acres >= min_acres
        ],
    )
    ambiguous_path = output_dir / "isanti_ambiguous_delinquency_matches.csv"
    ambiguous_fields = (
        "parcel_id",
        "deeded_acres",
        "owner_name",
        "status",
        "reason",
        "delinquency_source_rows",
    )
    _write_csv(
        ambiguous_path,
        ambiguous_fields,
        [
            {
                "parcel_id": match.parcel.parcel_id,
                "deeded_acres": (
                    str(match.parcel.deeded_acres)
                    if match.parcel.deeded_acres is not None
                    else None
                ),
                "owner_name": match.parcel.owner_name,
                "status": match.status.value,
                "reason": match.reason,
                "delinquency_source_rows": ";".join(
                    str(record.source_row_number)
                    for record in result.ambiguous_records
                    if record.normalized_parcel_id
                    == normalize_parcel_id(match.parcel.parcel_id)
                ),
            }
            for match in result.matches
            if match.status == DelinquencyStatus.AMBIGUOUS
        ],
    )
    return (
        csv_path, json_path, review_path, unmatched_path, duplicates_path,
        current_path, current_json, unverified_path, ambiguous_path
    ), len(candidates)


def _relevant_records(
    match: ParcelDelinquencyMatch, *, current: bool = False
) -> tuple[DelinquencyRecord, ...]:
    period = TaxPeriodStatus.OVERDUE_CURRENT_YEAR if current else TaxPeriodStatus.PRIOR_YEAR_UNPAID
    selected = tuple(r for r in match.records if r.tax_period_status == period)
    return selected if selected else match.records


def _verified_row(match: ParcelDelinquencyMatch, *, current: bool = False) -> dict[str, Any]:
    parcel = match.parcel
    records = _relevant_records(match, current=current)
    if not records:
        raise ValueError("match is missing its source records")
    # Selecting one row is appropriate only for a genuinely single-row match.
    record = records[0] if len(records) == 1 else None
    source = records[0].source_metadata  # common dataset lineage, not a chosen balance/owner
    years = sorted({year for r in records for year in r.delinquent_years or ()})

    def value(item: Any) -> Any:
        return str(item) if isinstance(item, Decimal) else item

    return {
        "parcel_id": parcel.parcel_id,
        "owner_name": parcel.owner_name,
        "taxpayer_name": record.taxpayer_name if record else None,
        "owner_mailing_address": parcel.owner_mailing_address,
        "deeded_acres": value(parcel.deeded_acres),
        "delinquent_years": (
            ";".join(str(year) for year in years) if years else None
        ),
        "total_taxes_and_penalties_due": value(record.total_taxes_and_penalties_due) if record else None,
        "delinquent_tax_amount": value(record.delinquent_tax_amount) if record else None,
        "penalty_amount": value(record.penalty_amount) if record else None,
        "current_tax_amount": value(parcel.current_tax_amount),
        "previous_taxes_owed_source_value": value(parcel.previous_taxes_owed),
        "land_value": value(parcel.land_value),
        "improvement_value": value(parcel.improvement_value),
        "assessed_value": value(parcel.assessed_value),
        "property_classification": parcel.property_classification,
        "legal_description": parcel.legal_description,
        "delinquency_status": (
            DelinquencyStatus.OVERDUE_CURRENT_YEAR.value if current else match.status.value
        ),
        "parcel_source": parcel.source_metadata.layer_url,
        "delinquency_source": source.service_url,
        "source_publication_date": source.publication_date,
        "parcel_retrieved_at": parcel.source_metadata.retrieved_at.isoformat(),
        "delinquency_retrieved_at": source.retrieved_at.isoformat(),
        "delinquency_source_row": ";".join(str(r.source_row_number) for r in records),
        "assessment_years": ";".join(str(y) for y in sorted({r.assessment_year for r in records if r.assessment_year is not None})) or None,
        "taxes_payable_years": ";".join(str(y) for y in sorted({r.taxes_payable_year for r in records if r.taxes_payable_year is not None})) or None,
        "source_record_count": len(records),
        "balance_aggregation_status": "not_aggregated" if len(records) > 1 else "single_source_row",
        "has_overdue_current_year": any(r.tax_period_status == TaxPeriodStatus.OVERDUE_CURRENT_YEAR for r in match.records),
    }


def _json_row(match: ParcelDelinquencyMatch, *, current: bool = False) -> dict[str, Any]:
    records = _relevant_records(match, current=current)
    row = _verified_row(match, current=current)
    return {
        **row,
        "delinquent_years": sorted({year for r in records for year in r.delinquent_years or ()}) or None,
        "assessment_years": sorted({r.assessment_year for r in records if r.assessment_year is not None}) or None,
        "taxes_payable_years": sorted({r.taxes_payable_year for r in records if r.taxes_payable_year is not None}) or None,
        "delinquency_original_row": records[0].original_row if len(records) == 1 else None,
        "delinquency_source_metadata": records[0].source_metadata.to_dict() if len(records) == 1 else None,
        "delinquency_source_records": [
            {
                "source_row_number": r.source_row_number,
                "assessment_year": r.assessment_year,
                "taxes_payable_year": r.taxes_payable_year,
                "tax_period_status": r.tax_period_status.value,
                "original_row": r.original_row,
                "source_metadata": r.source_metadata.to_dict(),
            }
            for r in records
        ],
    }


def _issue_row(record: DelinquencyRecord, status: str) -> dict[str, Any]:
    return {
        "original_parcel_id": record.parcel_id,
        "normalized_parcel_id": record.normalized_parcel_id,
        "source_row_number": record.source_row_number,
        "source_dataset": record.source_metadata.dataset,
        "source_publication_date": record.source_metadata.publication_date,
        "status": status,
        "assessment_year": record.assessment_year,
        "taxes_payable_year": record.taxes_payable_year,
        "tax_period_status": record.tax_period_status.value,
    }


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
