"""Allowlisted immutable parcel evidence; no filesystem, network or UI actions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from mn_land.counties.isanti.delinquency import classify_assessment_years, normalize_parcel_id
from mn_land.counties.isanti.evidence import LISTING_FIELDS, public_link, report_link
from mn_land.delinquency.file_loader import parse_money, parse_years
from mn_land.delinquency.tabular import SourceRow
from mn_land.parcel_table import ParcelIdentity, ParcelRow, number

Scalar = str | int | float | None
MONEY = ("delinquent_tax_amount", "penalty_amount", "total_taxes_and_penalties_due")
ATTRIBUTES = (
    ("Owner mailing address (GIS combined postal fields)", "owner_mailing_address"),
    ("Land assessment value (GIS LNDVALUE)", "land_value"),
    ("Improvement assessment value (GIS IMPRVALUE)", "improvement_value"),
    ("Total assessed value (GIS CNTASSDVAL)", "assessed_value"),
    ("Legal description (GIS LEGALDESCRIPT)", "legal_description"),
)


@dataclass(frozen=True, slots=True)
class ListingRow:
    number: int
    sheet: str | None
    line_start: int | None
    line_end: int | None
    owner_text: Scalar
    owner_field: str | None
    assessment_year: int | None
    payable_year: int | None
    report_payable_year: int | None
    period: str
    fields: tuple[tuple[str, Scalar], ...]
    omitted_columns: int


@dataclass(frozen=True, slots=True)
class PeriodEvidence:
    category: str
    status: str
    assessment_years: tuple[int, ...]
    payable_years: tuple[int, ...]
    source_rows: tuple[int, ...]
    money: tuple[tuple[str, Decimal | None], ...]
    aggregation_status: str


@dataclass(frozen=True, slots=True)
class SampleFinding:
    result: str
    payable_years: tuple[int, ...] | None
    aligns_with_selected_prior_years: bool | None


@dataclass(frozen=True, slots=True)
class ParcelDetails:
    identity: ParcelIdentity
    checked_at: datetime
    parcel: ParcelRow
    attributes: tuple[tuple[str, Scalar], ...]
    periods: tuple[PeriodEvidence, ...]
    rows: tuple[ListingRow, ...]
    source_context: tuple[tuple[str, str | None], ...]
    year_convention: str | None
    year_evidence_name: str | None
    year_evidence_sha256: str | None
    links: tuple[tuple[str, str], ...]
    sample_findings: tuple[SampleFinding, ...]
    warnings: tuple[str, ...]


def _years(value: object) -> tuple[int, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(
        type(year) is not int or not 1000 <= year <= 9999 for year in value
    ):
        raise ValueError("Invalid recorded canonical years")
    return tuple(value)


def project_details(
    identity: ParcelIdentity,
    parcel: ParcelRow,
    prior: list[dict],
    current: list[dict],
    source_rows: list[SourceRow],
    mapping: dict,
    context: tuple[tuple[str, str | None], ...],
    gis_url: str,
    *,
    checked_at: datetime,
    synthetic: bool,
    year_evidence: tuple[str, str] | None = None,
    comparison: dict | None = None,
) -> ParcelDetails:
    key = normalize_parcel_id(identity.parcel_id)
    if parcel.parcel_id != identity.parcel_id:
        raise ValueError("Parcel detail identity differs from the loaded table")
    selected = []
    for label, rows in (("Prior-year unpaid", prior), ("Current-year overdue", current)):
        matches = [row for row in rows if row["parcel_id"] == identity.parcel_id]
        if len(matches) > 1:
            raise ValueError("Duplicate parcel detail identity")
        if matches:
            selected.append((label, matches[0]))
    if not selected:
        raise ValueError("Parcel is not a saved candidate")
    base = selected[0][1]
    for _, entry in selected[1:]:
        if any(entry[field] != base[field] for _, field in ATTRIBUTES):
            raise ValueError("Conflicting GIS detail observations across periods")
    columns = mapping["columns"]
    raw = {
        (row.number, row.sheet): row
        for row in source_rows
        if normalize_parcel_id(row.values[columns["parcel_id"]]) == key
    }
    references = {}
    periods = []
    for label, entry in selected:
        records = entry["delinquency_source_records"]
        if not records:
            raise ValueError("Missing source-record evidence")
        seen = set()
        for record in records:
            reference = (record["source_row_number"], record["source_metadata"].get("source_sheet"))
            if reference in seen:
                raise ValueError("Duplicate source-row reference within a period")
            seen.add(reference)
            if reference in references and references[reference] != record:
                raise ValueError("Conflicting source-row references across periods")
            references[reference] = record
        money = tuple((field, number(entry[field])) for field in MONEY)
        for field, amount in money:
            if amount is not None and (
                len(records) != 1
                or field not in columns
                or parse_money(records[0]["original_row"].get(columns[field])) != amount
            ):
                raise ValueError("Unsupported canonical monetary claim")
        assessment_years = _years(entry["assessment_years"])
        payable_years = _years(entry["taxes_payable_years"])
        for years, field in (
            (assessment_years, "assessment_year"),
            (payable_years, "taxes_payable_year"),
        ):
            recorded = {record[field] for record in records if record[field] is not None}
            if set(years) != recorded or len(years) != len(recorded):
                raise ValueError("Period years disagree with contributing source rows")
        periods.append(
            PeriodEvidence(
                label,
                entry["delinquency_status"],
                assessment_years,
                payable_years,
                tuple(record["source_row_number"] for record in records),
                money,
                entry["balance_aggregation_status"],
            )
        )
    if raw.keys() != references.keys():
        raise ValueError("Parcel source rows are missing or have incompatible source locations")
    allowed = LISTING_FIELDS | set(columns.values())
    owner_field = columns.get("owner_name")
    listing = []
    for reference in sorted(raw, key=lambda item: item[0]):
        original, record = raw[reference], references[reference]
        if original.values != record["original_row"]:
            raise ValueError("Saved source row differs from retained input bytes")
        assessment = record["assessment_year"]
        payable = record["taxes_payable_year"]
        period = record["tax_period_status"]
        report_payable = None
        if mapping.get("tax_year_convention") == "isanti_assessment_year_plus_one":
            expected = classify_assessment_years(
                original.values.get("ASMTYR"), original.values.get("TAXYR")
            )
            if (assessment, payable, period) != (expected[0], expected[1], expected[3]):
                raise ValueError("Recorded year semantics differ from reviewed county convention")
            report_payable = expected[2]
        listing.append(
            ListingRow(
                original.number,
                original.sheet,
                original.line_start,
                original.line_end,
                original.values.get(owner_field) if owner_field else None,
                owner_field,
                assessment,
                payable,
                report_payable,
                period,
                tuple(
                    (field, value) for field, value in original.values.items() if field in allowed
                ),
                len(set(original.values) - allowed),
            )
        )
    links = []
    if not synthetic:
        for label, candidate in (
            ("Open county parcel report", report_link(identity.parcel_id)),
            ("Open county GIS layer reference", gis_url),
            ("Open listing public-source reference", mapping.get("source_url")),
        ):
            url = public_link(candidate, identity.parcel_id)
            if url is not None and url not in {value for _, value in links}:
                links.append((label, url))
    prior_years = next(
        (set(period.payable_years) for period in periods if period.category == "Prior-year unpaid"),
        set(),
    )
    findings = []
    for finding in (comparison or {}).get("findings", []):
        try:
            if normalize_parcel_id(finding.get("parcel_id")) != key:
                continue
        except ValueError:
            continue
        try:
            years = parse_years(finding.get("listed_taxes_payable_years"))
        except ValueError:
            years = None
        findings.append(
            SampleFinding(
                str(finding["verification_result"]),
                years,
                set(years) == prior_years if years is not None and prior_years else None,
            )
        )
    warnings = (
        "Current payment status is unknown. Dated listing categories are not a current balance check.",
        "Raw monetary fields are unaggregated observations; do not sum repeated rows or infer county accounting definitions.",
        "GIS and listing owner text are separate observations, not a preferred-owner or identity conclusion.",
        "Sample findings apply only to this parcel and the recorded years. Source-hash binding and report verification date are not established by the retained comparison schema.",
        "Access, usable/buildable acres, wetlands, floodplain, zoning, resale value and profit: not assessed.",
        "External records can be newer than this snapshot. Link validation does not verify their contents.",
    )
    return ParcelDetails(
        identity,
        checked_at,
        parcel,
        tuple((label, base[field]) for label, field in ATTRIBUTES),
        tuple(periods),
        tuple(listing),
        context,
        mapping.get("tax_year_convention"),
        year_evidence[0] if year_evidence else None,
        year_evidence[1] if year_evidence else None,
        tuple(links),
        tuple(findings),
        warnings,
    )
