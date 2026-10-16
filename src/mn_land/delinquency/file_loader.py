from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from mn_land.config.input_limits import DEFAULT_INPUT_LIMITS, InputLimits
from mn_land.counties.isanti.delinquency import classify_assessment_years, normalize_parcel_id
from mn_land.delinquency.base import DelinquencySource
from mn_land.delinquency.errors import DelinquencyFileError
from mn_land.delinquency.mapping import (
    DELINQUENCY_ASSERTION,
    MIXED_UNPAID_ASSERTION,
    DelinquencyMapping,
)
from mn_land.delinquency.tabular import SourceRow, read_table
from mn_land.models import DelinquencyRecord, SourceMetadata, TaxPeriodStatus
from mn_land.utils.validation import finite_decimal, optional_text, year_number

__all__ = [
    "DELINQUENCY_ASSERTION",
    "MIXED_UNPAID_ASSERTION",
    "DelinquencyFileError",
    "DelinquencyMapping",
    "FileDelinquencySource",
    "FileInspection",
    "inspect_delinquency_file",
    "parse_money",
    "parse_years",
    "read_tabular_file",
]

SUGGESTION_ALIASES = {
    "parcel_id": {"parcelid", "parcelnumber", "parcelno", "pin", "propertyid"},
    "taxpayer_name": {"taxpayer", "taxpayername"},
    "owner_name": {"owner", "ownername"},
    "mailing_address": {"mailingaddress", "postaladdress"},
    "delinquent_years": {"delinquentyear", "delinquentyears", "taxyear", "taxyears"},
    "delinquent_tax_amount": {"delinquenttax", "delinquenttaxamount"},
    "penalty_amount": {"penalty", "penaltyamount"},
    "total_taxes_and_penalties_due": {
        "taxespenalties",
        "taxesandpenalties",
        "totaldue",
        "totaltaxesandpenaltiesdue",
    },
}


@dataclass(frozen=True, slots=True)
class FileInspection:
    path: Path
    file_type: str
    columns: tuple[str, ...]
    row_count: int
    potential_mapping: dict[str, str]
    ambiguous_suggestions: dict[str, tuple[str, ...]]


def parse_money(value: Any) -> Decimal | None:
    try:
        return finite_decimal(value, currency=True)
    except ValueError as exc:
        raise DelinquencyFileError(f"cannot parse money: {exc}") from exc


def parse_years(value: Any) -> tuple[int, ...] | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        values = re.split(r"[,;/|\s]+", value.strip()) if isinstance(value, str) else [value]
        return tuple(sorted({year_number(candidate) for candidate in values}))
    except ValueError as exc:
        raise DelinquencyFileError(f"invalid delinquent year: {exc}") from exc


def inspect_delinquency_file(
    path: Path, *, limits: InputLimits = DEFAULT_INPUT_LIMITS
) -> FileInspection:
    columns, rows = read_table(path, limits)
    potential: dict[str, str] = {}
    ambiguous: dict[str, tuple[str, ...]] = {}
    for canonical, aliases in SUGGESTION_ALIASES.items():
        matches = tuple(column for column in columns if _column_key(column) in aliases)
        if len(matches) == 1:
            potential[canonical] = matches[0]
        elif len(matches) > 1:
            ambiguous[canonical] = matches
    return FileInspection(
        path, path.suffix.lower().removeprefix("."), columns, len(rows), potential, ambiguous
    )


def read_tabular_file(
    path: Path,
    *,
    limits: InputLimits = DEFAULT_INPUT_LIMITS,
) -> tuple[tuple[str, ...], list[dict[str, Any]]]:
    """Compatibility view; ingestion uses read_table's source locations."""
    columns, rows = read_table(path, limits)
    return columns, [row.values for row in rows]


class FileDelinquencySource(DelinquencySource):
    def __init__(
        self,
        path: Path,
        mapping: DelinquencyMapping,
        *,
        limits: InputLimits = DEFAULT_INPUT_LIMITS,
        retrieved_at: datetime | None = None,
    ) -> None:
        self.path = path
        self.mapping = mapping
        self.limits = limits
        if retrieved_at is not None and retrieved_at.tzinfo is None:
            raise DelinquencyFileError("retrieved_at requires a timezone")
        self.retrieved_at = retrieved_at

    def load_records(self) -> list[DelinquencyRecord]:
        self.mapping.__post_init__()  # Recheck mutable nested mappings at the public boundary.
        columns, rows = read_table(self.path, self.limits)
        missing = set(self.mapping.columns.values()) - set(columns)
        if self.mapping.tax_year_convention == "isanti_assessment_year_plus_one":
            missing |= {"ASMTYR", "TAXYR"} - set(columns)
        if missing:
            raise DelinquencyFileError(
                f"mapped source columns are absent: {', '.join(sorted(missing))}"
            )
        retrieved_at = self.retrieved_at or datetime.now(UTC)
        records = []
        for row in rows:
            location = (
                f"sheet {row.sheet}, row {row.number}" if row.sheet else f"CSV record {row.number}"
            )
            try:
                try:
                    parcel_id = optional_text(row.values.get(self.mapping.columns["parcel_id"]))
                except ValueError as exc:
                    raise DelinquencyFileError(
                        f"field {self.mapping.columns['parcel_id']}: {exc}"
                    ) from exc
                if parcel_id is None:
                    raise DelinquencyFileError("parcel ID is missing")
                normalized = normalize_parcel_id(parcel_id)
                records.append(self._normalize_row(row, parcel_id, normalized, retrieved_at))
            except ValueError as exc:
                raise DelinquencyFileError(f"{location}: {exc}") from exc
        return records

    def _normalize_row(
        self,
        entry: SourceRow,
        parcel_id: str,
        normalized: str,
        retrieved_at: datetime,
    ) -> DelinquencyRecord:
        row = entry.values

        def raw(canonical: str) -> Any:
            source_column = self.mapping.columns.get(canonical)
            return row.get(source_column) if source_column else None

        def text(canonical: str) -> str | None:
            try:
                return optional_text(raw(canonical))
            except ValueError as exc:
                raise DelinquencyFileError(
                    f"field {self.mapping.columns.get(canonical)}: {exc}"
                ) from exc

        def money(canonical: str) -> Decimal | None:
            try:
                return parse_money(raw(canonical))
            except ValueError as exc:
                raise DelinquencyFileError(
                    f"field {self.mapping.columns.get(canonical)}: {exc}"
                ) from exc

        source = SourceMetadata(
            agency=self.mapping.source_agency,
            dataset=self.mapping.dataset,
            service_url=self.mapping.source_url or self.path.name,
            layer_id=None,
            retrieved_at=retrieved_at,
            source_fields={
                **self.mapping.columns,
                **(
                    {"assessment_year": "ASMTYR", "report_assessment_year": "TAXYR"}
                    if self.mapping.tax_year_convention
                    else {}
                ),
            },
            notes=(f"Source assertion: {self.mapping.delinquency_assertion}.",)
            + (
                (self.mapping.verification_hold_reason,)
                if self.mapping.verification_hold_reason
                else ()
            )
            + (
                (f"Year semantics: {self.mapping.year_semantics_reference}",)
                if self.mapping.year_semantics_reference
                else ()
            ),
            publication_date=self.mapping.publication_date,
            source_record_id=f"sheet:{entry.sheet}:row:{entry.number}"
            if entry.sheet
            else f"row:{entry.number}",
            original_identifier=parcel_id,
            normalized_identifier=normalized,
            source_sheet=entry.sheet,
            source_line_start=entry.line_start,
            source_line_end=entry.line_end,
        )
        assessment_year = payable_year = report_payable_year = None
        period = TaxPeriodStatus.UNVERIFIED
        try:
            delinquent_years = parse_years(raw("delinquent_years"))
        except ValueError as exc:
            raise DelinquencyFileError(
                f"field {self.mapping.columns.get('delinquent_years')}: {exc}"
            ) from exc
        if self.mapping.tax_year_convention == "isanti_assessment_year_plus_one":
            assessment_year, payable_year, report_payable_year, period = classify_assessment_years(
                row.get("ASMTYR"),
                row.get("TAXYR"),
            )
            delinquent_years = (
                (payable_year,) if period == TaxPeriodStatus.PRIOR_YEAR_UNPAID else None
            )
        return DelinquencyRecord(
            county="Isanti",
            parcel_id=parcel_id,
            normalized_parcel_id=normalized,
            taxpayer_name=text("taxpayer_name"),
            owner_name=text("owner_name"),
            mailing_address=text("mailing_address"),
            delinquent_years=delinquent_years,
            delinquent_tax_amount=money("delinquent_tax_amount"),
            penalty_amount=money("penalty_amount"),
            total_taxes_and_penalties_due=money("total_taxes_and_penalties_due"),
            source_metadata=source,
            source_row_number=entry.number,
            original_row={key: _source_value(value) for key, value in row.items()},
            verification_hold_reason=self.mapping.verification_hold_reason,
            assessment_year=assessment_year,
            taxes_payable_year=payable_year,
            report_taxes_payable_year=report_payable_year,
            tax_period_status=period,
        )


def _column_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _source_value(value: Any) -> Any:
    """JSON-safe evidence for unmapped spreadsheet dates, never a canonical fact."""
    if isinstance(value, (datetime, date, time)):
        return {"source_cell_type": type(value).__name__, "iso8601": value.isoformat()}
    if isinstance(value, timedelta):
        return {
            "source_cell_type": "timedelta",
            "days": value.days,
            "seconds": value.seconds,
            "microseconds": value.microseconds,
        }
    return value
