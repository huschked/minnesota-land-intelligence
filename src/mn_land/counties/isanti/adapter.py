from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from mn_land.config.settings import SETTINGS
from mn_land.counties.base import CountyAdapter
from mn_land.ingestion.arcgis import ArcGISClient
from mn_land.models import Parcel, SourceMetadata

from .mappings import (
    DATASET,
    LAYER_ID,
    MAILING_FIELDS,
    PAST_DUE_TAX_SEMANTICS_VERIFIED,
    QUERY_FIELDS,
    SERVICE_URL,
    SOURCE_FIELDS,
)


def parse_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise TypeError("boolean is not a numeric parcel value")
    try:
        text = str(value).strip().replace("$", "").replace(",", "")
        return Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"cannot parse numeric value {value!r}") from exc


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class IsantiAdapter(CountyAdapter):
    def __init__(self, client: ArcGISClient | None = None) -> None:
        self.client = client or ArcGISClient(
            SERVICE_URL,
            LAYER_ID,
            page_size=SETTINGS.page_size,
        )

    def fetch_parcels(self, raw_run_dir: Path, retrieved_at: datetime) -> Iterable[Mapping[str, Any]]:
        return self.client.fetch_all(
            out_fields=QUERY_FIELDS,
            raw_run_dir=raw_run_dir,
            retrieved_at=retrieved_at,
            return_geometry=False,
        )

    def normalize_parcel(self, raw_record: Mapping[str, Any], retrieved_at: datetime) -> Parcel:
        attributes = raw_record.get("attributes", raw_record)
        parcel_id = clean_text(attributes.get(SOURCE_FIELDS["parcel_id"]))
        if not parcel_id:
            raise ValueError("missing parcel ID")
        address = ", ".join(
            part for name in MAILING_FIELDS if (part := clean_text(attributes.get(name)))
        ) or None
        previous = parse_decimal(attributes.get(SOURCE_FIELDS["previous_taxes_owed"]))
        source = SourceMetadata(
            agency="Isanti County GIS",
            dataset=DATASET,
            service_url=SERVICE_URL,
            layer_id=LAYER_ID,
            retrieved_at=retrieved_at,
            source_fields=dict(SOURCE_FIELDS),
            notes=(
                "TOTPRVTXTOD is officially aliased Total Previous Taxes Owed, but delinquent/past-due semantics are not documented.",
            ),
        )
        return Parcel(
            county="Isanti",
            parcel_id=parcel_id,
            owner_name=clean_text(attributes.get(SOURCE_FIELDS["owner_name"])),
            owner_mailing_address=address,
            deeded_acres=parse_decimal(attributes.get(SOURCE_FIELDS["deeded_acres"])),
            previous_taxes_owed=previous,
            past_due_tax_amount=previous if PAST_DUE_TAX_SEMANTICS_VERIFIED else None,
            current_tax_amount=parse_decimal(attributes.get(SOURCE_FIELDS["current_tax_amount"])),
            land_value=parse_decimal(attributes.get(SOURCE_FIELDS["land_value"])),
            improvement_value=parse_decimal(attributes.get(SOURCE_FIELDS["improvement_value"])),
            assessed_value=parse_decimal(attributes.get(SOURCE_FIELDS["assessed_value"])),
            property_classification=clean_text(attributes.get(SOURCE_FIELDS["property_classification"])),
            legal_description=clean_text(attributes.get(SOURCE_FIELDS["legal_description"])),
            geometry=raw_record.get("geometry"),
            source_reference=clean_text(attributes.get(SOURCE_FIELDS["source_reference"])),
            source_metadata=source,
            tax_semantics_verified=PAST_DUE_TAX_SEMANTICS_VERIFIED,
        )
