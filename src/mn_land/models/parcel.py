from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .source import SourceMetadata


@dataclass(frozen=True, slots=True)
class Parcel:
    county: str
    parcel_id: str
    owner_name: str | None
    owner_mailing_address: str | None
    deeded_acres: Decimal | None
    previous_taxes_owed: Decimal | None
    past_due_tax_amount: Decimal | None
    current_tax_amount: Decimal | None
    land_value: Decimal | None
    improvement_value: Decimal | None
    assessed_value: Decimal | None
    property_classification: str | None
    legal_description: str | None
    geometry: dict[str, Any] | None
    source_reference: str | None
    source_metadata: SourceMetadata
    tax_semantics_verified: bool = False
