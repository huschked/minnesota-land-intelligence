from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from .source import SourceMetadata

if TYPE_CHECKING:
    from .parcel import Parcel


class DelinquencyStatus(StrEnum):
    VERIFIED_DELINQUENT = "verified_delinquent"
    VERIFIED_NOT_DELINQUENT = "verified_not_delinquent"
    UNVERIFIED = "unverified"
    UNMATCHED = "unmatched"
    AMBIGUOUS = "ambiguous"
    OVERDUE_CURRENT_YEAR = "overdue_current_year"


class TaxPeriodStatus(StrEnum):
    PRIOR_YEAR_UNPAID = "prior_year_unpaid"
    OVERDUE_CURRENT_YEAR = "overdue_current_year"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class DelinquencyRecord:
    county: str
    parcel_id: str
    normalized_parcel_id: str
    taxpayer_name: str | None
    owner_name: str | None
    mailing_address: str | None
    delinquent_years: tuple[int, ...] | None
    delinquent_tax_amount: Decimal | None
    penalty_amount: Decimal | None
    total_taxes_and_penalties_due: Decimal | None
    source_metadata: SourceMetadata
    source_row_number: int
    original_row: dict[str, Any]
    verification_hold_reason: str | None = None
    assessment_year: int | None = None
    taxes_payable_year: int | None = None
    report_taxes_payable_year: int | None = None
    tax_period_status: TaxPeriodStatus = TaxPeriodStatus.UNVERIFIED


@dataclass(frozen=True, slots=True)
class ParcelDelinquencyMatch:
    parcel: Parcel
    delinquency: DelinquencyRecord | None
    status: DelinquencyStatus
    reason: str | None = None
    delinquency_records: tuple[DelinquencyRecord, ...] = ()

    @property
    def records(self) -> tuple[DelinquencyRecord, ...]:
        if self.delinquency_records:
            return self.delinquency_records
        return (self.delinquency,) if self.delinquency is not None else ()
