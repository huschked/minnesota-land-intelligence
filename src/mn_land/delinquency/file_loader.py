from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from mn_land.counties.isanti.delinquency import classify_assessment_years, normalize_parcel_id
from mn_land.delinquency.base import DelinquencySource
from mn_land.models import DelinquencyRecord, SourceMetadata, TaxPeriodStatus

SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}
CANONICAL_COLUMNS = {
    "parcel_id",
    "taxpayer_name",
    "owner_name",
    "mailing_address",
    "delinquent_years",
    "delinquent_tax_amount",
    "penalty_amount",
    "total_taxes_and_penalties_due",
}
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
DELINQUENCY_ASSERTION = "each_row_represents_delinquent_parcel"
MIXED_UNPAID_ASSERTION = "mixed_unpaid_prior_and_overdue_current_year_taxes"


class DelinquencyFileError(ValueError):
    """A delinquency file or mapping is unusable without guessing."""


@dataclass(frozen=True, slots=True)
class FileInspection:
    path: Path
    file_type: str
    columns: tuple[str, ...]
    row_count: int
    potential_mapping: dict[str, str]
    ambiguous_suggestions: dict[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class DelinquencyMapping:
    source_agency: str
    dataset: str
    columns: dict[str, str]
    delinquency_assertion: str
    source_url: str | None = None
    publication_date: str | None = None
    verification_hold_reason: str | None = None
    tax_year_convention: str | None = None
    year_semantics_reference: str | None = None
    supporting_documents: tuple[str, ...] = ()

    @classmethod
    def from_json(cls, path: Path) -> DelinquencyMapping:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DelinquencyFileError(f"cannot read mapping JSON {path}: {exc}") from exc
        required = ("source_agency", "dataset", "columns", "delinquency_assertion")
        missing = [name for name in required if not payload.get(name)]
        if missing:
            raise DelinquencyFileError(f"mapping is missing required keys: {', '.join(missing)}")
        if payload["delinquency_assertion"] not in (DELINQUENCY_ASSERTION, MIXED_UNPAID_ASSERTION):
            raise DelinquencyFileError(
                "unsupported delinquency_assertion"
            )
        convention = payload.get("tax_year_convention")
        if convention is not None and convention != "isanti_assessment_year_plus_one":
            raise DelinquencyFileError("unsupported tax_year_convention")
        if payload["delinquency_assertion"] == MIXED_UNPAID_ASSERTION and (
            convention is None or not payload.get("year_semantics_reference")
        ):
            raise DelinquencyFileError("mixed tax data requires verified year convention and reference")
        if not str(payload["source_agency"]).casefold().startswith("isanti county"):
            raise DelinquencyFileError(
                "source_agency must identify Isanti County as the authoritative publisher"
            )
        columns = payload["columns"]
        if not isinstance(columns, dict) or not columns.get("parcel_id"):
            raise DelinquencyFileError("mapping columns must include parcel_id")
        unsupported = set(columns) - CANONICAL_COLUMNS
        if unsupported:
            raise DelinquencyFileError(
                f"mapping contains unsupported canonical fields: {', '.join(sorted(unsupported))}"
            )
        return cls(
            source_agency=str(payload["source_agency"]),
            dataset=str(payload["dataset"]),
            columns={str(key): str(value) for key, value in columns.items()},
            delinquency_assertion=str(payload["delinquency_assertion"]),
            source_url=str(payload["source_url"]) if payload.get("source_url") else None,
            publication_date=(
                str(payload["publication_date"]) if payload.get("publication_date") else None
            ),
            verification_hold_reason=(
                str(payload["verification_hold_reason"])
                if payload.get("verification_hold_reason") else None
            ),
            tax_year_convention=convention,
            year_semantics_reference=payload.get("year_semantics_reference"),
            supporting_documents=tuple(payload.get("supporting_documents", [])),
        )


def parse_money(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise TypeError("boolean is not a monetary value")
    cleaned = str(value).strip().replace("$", "").replace(",", "")
    if not cleaned:
        return None
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise DelinquencyFileError(f"cannot parse money value {value!r}") from exc


def parse_years(value: Any) -> tuple[int, ...] | None:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, bool):
        raise TypeError("boolean is not a delinquent year")
    if isinstance(value, (int, float)) and int(value) == value:
        candidates = [str(int(value))]
    else:
        candidates = [item for item in re.split(r"[,;/|\s]+", str(value).strip()) if item]
    years: list[int] = []
    for candidate in candidates:
        if not re.fullmatch(r"\d{4}", candidate):
            raise DelinquencyFileError(f"cannot parse delinquent year {candidate!r}")
        years.append(int(candidate))
    return tuple(sorted(set(years)))


def inspect_delinquency_file(path: Path) -> FileInspection:
    columns, rows = read_tabular_file(path)
    potential: dict[str, str] = {}
    ambiguous: dict[str, tuple[str, ...]] = {}
    for canonical, aliases in SUGGESTION_ALIASES.items():
        matches = tuple(column for column in columns if _column_key(column) in aliases)
        if len(matches) == 1:
            potential[canonical] = matches[0]
        elif len(matches) > 1:
            ambiguous[canonical] = matches
    return FileInspection(
        path=path,
        file_type=path.suffix.lower().removeprefix("."),
        columns=columns,
        row_count=len(rows),
        potential_mapping=potential,
        ambiguous_suggestions=ambiguous,
    )


def read_tabular_file(path: Path) -> tuple[tuple[str, ...], list[dict[str, Any]]]:
    if not path.is_file():
        raise DelinquencyFileError(f"file does not exist: {path}")
    extension = path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise DelinquencyFileError(
            f"unsupported file type {extension or '<none>'}; supported: CSV, XLSX"
        )
    if extension == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise DelinquencyFileError("CSV has no header row")
            columns = tuple(str(name).strip() for name in reader.fieldnames)
            if not all(columns) or len(set(columns)) != len(columns):
                raise DelinquencyFileError("CSV headers must be nonblank and unique")
            rows = [
                {str(key).strip(): value for key, value in row.items()} for row in reader
            ]
            return columns, rows
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise DelinquencyFileError("XLSX support requires the openpyxl package") from exc
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    values = sheet.iter_rows(values_only=True)
    try:
        header = next(values)
    except StopIteration as exc:
        raise DelinquencyFileError("XLSX worksheet is empty") from exc
    columns = tuple(str(value).strip() if value is not None else "" for value in header)
    if not all(columns) or len(set(columns)) != len(columns):
        raise DelinquencyFileError("XLSX headers must be nonblank and unique")
    rows = [dict(zip(columns, row, strict=True)) for row in values if any(value is not None for value in row)]
    workbook.close()
    return columns, rows


class FileDelinquencySource(DelinquencySource):
    def __init__(self, path: Path, mapping: DelinquencyMapping) -> None:
        self.path = path
        self.mapping = mapping

    def load_records(self) -> list[DelinquencyRecord]:
        columns, rows = read_tabular_file(self.path)
        missing = set(self.mapping.columns.values()) - set(columns)
        if self.mapping.tax_year_convention == "isanti_assessment_year_plus_one":
            missing |= {"ASMTYR", "TAXYR"} - set(columns)
        if missing:
            raise DelinquencyFileError(
                f"mapped source columns are absent: {', '.join(sorted(missing))}"
            )
        retrieved_at = datetime.now(UTC)
        records: list[DelinquencyRecord] = []
        for row_number, row in enumerate(rows, start=2):
            parcel_id = _text(row.get(self.mapping.columns["parcel_id"]))
            if parcel_id is None:
                raise DelinquencyFileError(f"row {row_number}: parcel ID is missing")
            try:
                normalized = normalize_parcel_id(parcel_id)
                record = self._normalize_row(row, row_number, parcel_id, normalized, retrieved_at)
            except (DelinquencyFileError, TypeError, ValueError) as exc:
                raise DelinquencyFileError(f"row {row_number}: {exc}") from exc
            records.append(record)
        if not records:
            raise DelinquencyFileError("file contains no delinquency records")
        return records

    def _normalize_row(
        self,
        row: dict[str, Any],
        row_number: int,
        parcel_id: str,
        normalized: str,
        retrieved_at: datetime,
    ) -> DelinquencyRecord:
        def raw(canonical: str) -> Any:
            source_column = self.mapping.columns.get(canonical)
            return row.get(source_column) if source_column else None

        source = SourceMetadata(
            agency=self.mapping.source_agency,
            dataset=self.mapping.dataset,
            service_url=self.mapping.source_url or self.path.name,
            layer_id=None,
            retrieved_at=retrieved_at,
            source_fields={
                **self.mapping.columns,
                **({"assessment_year": "ASMTYR", "report_assessment_year": "TAXYR"}
                   if self.mapping.tax_year_convention else {}),
            },
            notes=(f"Source assertion: {self.mapping.delinquency_assertion}.",)
            + ((self.mapping.verification_hold_reason,) if self.mapping.verification_hold_reason else ())
            + ((f"Year semantics: {self.mapping.year_semantics_reference}",) if self.mapping.year_semantics_reference else ()),
            publication_date=self.mapping.publication_date,
            source_record_id=f"row:{row_number}",
            original_identifier=parcel_id,
            normalized_identifier=normalized,
        )
        assessment_year = payable_year = report_payable_year = None
        period = TaxPeriodStatus.UNVERIFIED
        delinquent_years = parse_years(raw("delinquent_years"))
        if self.mapping.tax_year_convention == "isanti_assessment_year_plus_one":
            assessment_year, payable_year, report_payable_year, period = classify_assessment_years(
                row.get("ASMTYR"), row.get("TAXYR")
            )
            delinquent_years = (
                (payable_year,) if period == TaxPeriodStatus.PRIOR_YEAR_UNPAID else None
            )
        return DelinquencyRecord(
            county="Isanti",
            parcel_id=parcel_id,
            normalized_parcel_id=normalized,
            taxpayer_name=_text(raw("taxpayer_name")),
            owner_name=_text(raw("owner_name")),
            mailing_address=_text(raw("mailing_address")),
            delinquent_years=delinquent_years,
            delinquent_tax_amount=parse_money(raw("delinquent_tax_amount")),
            penalty_amount=parse_money(raw("penalty_amount")),
            total_taxes_and_penalties_due=parse_money(raw("total_taxes_and_penalties_due")),
            source_metadata=source,
            source_row_number=row_number,
            original_row=dict(row),
            verification_hold_reason=self.mapping.verification_hold_reason,
            assessment_year=assessment_year,
            taxes_payable_year=payable_year,
            report_taxes_payable_year=report_payable_year,
            tax_period_status=period,
        )


def _column_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
