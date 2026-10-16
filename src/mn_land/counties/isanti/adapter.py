from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from mn_land.config.settings import SETTINGS, Settings
from mn_land.counties.base import CountyAdapter
from mn_land.ingestion.arcgis import ArcGISClient
from mn_land.models import Parcel, SourceMetadata
from mn_land.utils.validation import finite_decimal, optional_text

from .delinquency import normalize_parcel_id
from .mappings import (
    DATASET,
    LAYER_ID,
    MAILING_FIELDS,
    PAST_DUE_TAX_SEMANTICS_VERIFIED,
    QUERY_FIELDS,
    SERVICE_URL,
    SOURCE_FIELDS,
)
from .schema import validate_metadata


def parse_decimal(value: Any) -> Decimal | None:
    return finite_decimal(value, currency=True)


def clean_text(value: Any) -> str | None:
    return optional_text(value)


class ParcelRowError(ValueError):
    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        super().__init__(f"{field}: {reason}")


class IsantiAdapter(CountyAdapter):
    layer_name = DATASET
    validate_metadata = staticmethod(validate_metadata)

    def record_identifier(self, raw_record: Mapping[str, Any]) -> str | int | None:
        attributes = (
            raw_record.get("attributes", raw_record) if isinstance(raw_record, Mapping) else {}
        )
        identity = (
            attributes.get(SOURCE_FIELDS["object_id"]) if isinstance(attributes, Mapping) else None
        )
        return (
            identity
            if isinstance(identity, (str, int)) and not isinstance(identity, bool)
            else None
        )

    def __init__(
        self, client: ArcGISClient | None = None, *, settings: Settings = SETTINGS
    ) -> None:
        self.client = client or ArcGISClient(
            SERVICE_URL,
            LAYER_ID,
            page_size=settings.page_size,
            policy=settings.retrieval_policy(),
            expected_layer_name=DATASET,
        )

    def fetch_parcels(
        self, raw_run_dir: Path, retrieved_at: datetime, *, directory_reserved: bool = False
    ) -> Iterable[Mapping[str, Any]]:
        return self.client.fetch_all(
            out_fields=QUERY_FIELDS,
            raw_run_dir=raw_run_dir,
            retrieved_at=retrieved_at,
            return_geometry=False,
            metadata_validator=self.validate_metadata,
            directory_reserved=directory_reserved,
        )

    def validate_snapshot_source(self, manifest: Mapping[str, Any]) -> None:
        """Selected evidence must belong to this configured county service/layer.

        Tests can inject a synthetic client, but the CLI uses the reviewed official
        service. No request or alternate-source discovery is performed here.
        """
        if (
            manifest.get("service_url") != self.client.service_url
            or type(manifest.get("layer_id")) is not int
            or manifest["layer_id"] != self.client.layer_id
            or manifest.get("where") != "1=1"
        ):
            raise ValueError(
                "Parcel snapshot is incompatible with the configured Isanti "
                "source/layer or full-county query"
            )

    def normalize_parcel(self, raw_record: Mapping[str, Any], retrieved_at: datetime) -> Parcel:
        if not isinstance(raw_record, Mapping):
            raise ParcelRowError("attributes", "feature must be an object")
        attributes = raw_record.get("attributes", raw_record)
        if not isinstance(attributes, Mapping):
            raise ParcelRowError("attributes", "must be an object")

        def value(name: str, *, numeric: bool = False):
            try:
                return (
                    parse_decimal(attributes.get(name))
                    if numeric
                    else clean_text(attributes.get(name))
                )
            except ValueError as exc:
                raise ParcelRowError(name, str(exc)) from exc

        parcel_id = value(SOURCE_FIELDS["parcel_id"])
        if not parcel_id:
            raise ParcelRowError("PARCELID", "missing parcel ID")
        try:
            normalize_parcel_id(parcel_id)
        except ValueError as exc:
            raise ParcelRowError("PARCELID", str(exc)) from exc
        address = ", ".join(part for name in MAILING_FIELDS if (part := value(name))) or None
        previous = value(SOURCE_FIELDS["previous_taxes_owed"], numeric=True)
        acres = value(SOURCE_FIELDS["deeded_acres"], numeric=True)
        if acres is not None and acres < 0:
            raise ParcelRowError("DEEDEDACRES", "acreage must be non-negative")
        missing = sorted(
            {*SOURCE_FIELDS.values(), *MAILING_FIELDS} - set(attributes) - {"OBJECTID"}
        )
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
            validation_warnings=tuple(f"missing optional attribute: {name}" for name in missing),
        )
        return Parcel(
            county="Isanti",
            parcel_id=parcel_id,
            owner_name=value(SOURCE_FIELDS["owner_name"]),
            owner_mailing_address=address,
            deeded_acres=acres,
            previous_taxes_owed=previous,
            past_due_tax_amount=previous if PAST_DUE_TAX_SEMANTICS_VERIFIED else None,
            current_tax_amount=value(SOURCE_FIELDS["current_tax_amount"], numeric=True),
            land_value=value(SOURCE_FIELDS["land_value"], numeric=True),
            improvement_value=value(SOURCE_FIELDS["improvement_value"], numeric=True),
            assessed_value=value(SOURCE_FIELDS["assessed_value"], numeric=True),
            property_classification=value(SOURCE_FIELDS["property_classification"]),
            legal_description=value(SOURCE_FIELDS["legal_description"]),
            geometry=raw_record.get("geometry"),
            source_reference=value(SOURCE_FIELDS["source_reference"]),
            source_metadata=source,
            tax_semantics_verified=PAST_DUE_TAX_SEMANTICS_VERIFIED,
        )
