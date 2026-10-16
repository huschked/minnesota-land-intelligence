from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from mn_land.models import Parcel

FIELDS = (
    "county",
    "parcel_id",
    "owner_name",
    "owner_mailing_address",
    "deeded_acres",
    "previous_taxes_owed",
    "past_due_tax_amount",
    "current_tax_amount",
    "land_value",
    "improvement_value",
    "assessed_value",
    "property_classification",
    "legal_description",
    "source_reference",
    "source_url",
    "retrieved_at",
    "tax_semantics_verified",
)


def parcel_row(parcel: Parcel) -> dict[str, Any]:
    def value(item: Any) -> Any:
        return str(item) if isinstance(item, Decimal) else item

    return {
        "county": parcel.county,
        "parcel_id": parcel.parcel_id,
        "owner_name": parcel.owner_name,
        "owner_mailing_address": parcel.owner_mailing_address,
        "deeded_acres": value(parcel.deeded_acres),
        "previous_taxes_owed": value(parcel.previous_taxes_owed),
        "past_due_tax_amount": value(parcel.past_due_tax_amount),
        "current_tax_amount": value(parcel.current_tax_amount),
        "land_value": value(parcel.land_value),
        "improvement_value": value(parcel.improvement_value),
        "assessed_value": value(parcel.assessed_value),
        "property_classification": parcel.property_classification,
        "legal_description": parcel.legal_description,
        "source_reference": parcel.source_reference,
        "source_url": parcel.source_metadata.layer_url,
        "retrieved_at": parcel.source_metadata.retrieved_at.isoformat(),
        "tax_semantics_verified": parcel.tax_semantics_verified,
    }


def export_candidates(parcels: list[Parcel], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "isanti_candidates.csv"
    json_path = output_dir / "isanti_candidates.json"
    rows = [parcel_row(parcel) for parcel in parcels]
    with csv_path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with json_path.open("x", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return csv_path, json_path


def export_verification_sample(parcels: list[Parcel], output_dir: Path, size: int = 10) -> Path:
    path = output_dir / "isanti_verification_sample.csv"
    selected = sorted(parcels, key=lambda parcel: parcel.parcel_id)[:size]
    fields = (
        "parcel_id",
        "deeded_acres",
        "past_due_tax_amount",
        "owner_name",
        "assessed_value",
        "source_reference",
    )
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for parcel in selected:
            row = parcel_row(parcel)
            writer.writerow({field: row[field] for field in fields})
    return path


def export_tax_semantics_review_sample(
    parcels: list[Parcel], output_dir: Path, min_acres: Decimal, size: int = 10
) -> tuple[Path, int]:
    """Export source-aligned examples without claiming they are candidates."""
    review_pool = [
        parcel
        for parcel in parcels
        if parcel.deeded_acres is not None
        and parcel.deeded_acres >= min_acres
        and parcel.previous_taxes_owed is not None
        and parcel.previous_taxes_owed > 0
    ]
    selected = sorted(review_pool, key=lambda parcel: parcel.parcel_id)[:size]
    path = output_dir / "isanti_tax_semantics_review_sample.csv"
    fields = (
        "parcel_id",
        "deeded_acres",
        "source_previous_taxes_owed",
        "owner_name",
        "assessed_value",
        "source_reference",
        "review_status",
    )
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for parcel in selected:
            row = parcel_row(parcel)
            writer.writerow(
                {
                    "parcel_id": row["parcel_id"],
                    "deeded_acres": row["deeded_acres"],
                    "source_previous_taxes_owed": row["previous_taxes_owed"],
                    "owner_name": row["owner_name"],
                    "assessed_value": row["assessed_value"],
                    "source_reference": row["source_reference"],
                    "review_status": "NOT A CANDIDATE - tax semantics unverified",
                }
            )
    return path, len(review_pool)
