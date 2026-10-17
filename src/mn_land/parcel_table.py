"""Immutable candidate projections and deterministic in-memory research filters.

No Streamlit, disk reads, acquisition, financial aggregation or opportunity ranking.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from mn_land.counties.isanti.delinquency import normalize_parcel_id
from mn_land.counties.isanti.review import review_bucket

if TYPE_CHECKING:
    from mn_land.review_service import SnapshotOverview

VIEWS = {
    "focused": "Land-focused prior-year",
    "outside_special": "Outside PILT/exempt prior-year",
    "prior": "All prior-year large parcels",
    "special": "PILT/exempt prior-year review",
    "current": "Current-year overdue large parcels",
    "either": "Prior or current (distinct parcels)",
    "both": "Both prior and current",
}
IMPROVEMENTS = ("all", "known", "unknown", "zero", "nonzero")
SPECIAL = ("all", "exclude", "only", "unknown")
SORTS = ("parcel_id", "deeded_acres", "improvement_value", "property_classification", "owner_name")


def number(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise TypeError("Expected finite decimal text, integer or null")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal value") from exc
    if not result.is_finite():
        raise ValueError("Expected a finite decimal")
    return result


@dataclass(frozen=True, slots=True)
class ParcelRow:
    parcel_id: str
    deeded_acres: Decimal | None
    property_classification: str | None
    improvement_value: Decimal | None
    owner_name: str | None
    prior: bool
    current: bool
    bucket: str

    @property
    def special(self) -> bool:
        return self.bucket == "PILT_or_exempt_review"

    @property
    def focused(self) -> bool:
        return self.bucket in {
            "rural_vacant_classification_review",
            "zero_improvement_value_review",
        }

    @property
    def periods(self) -> str:
        return (
            "Prior and current"
            if self.prior and self.current
            else "Prior-year unpaid"
            if self.prior
            else "Current-year overdue"
        )


@dataclass(frozen=True, slots=True)
class ParcelDataset:
    overview: SnapshotOverview
    minimum_acres: Decimal
    rows: tuple[ParcelRow, ...]


@dataclass(frozen=True, slots=True)
class ParcelIdentity:
    county: str
    snapshot_token: str
    completion_sha256: str
    parcel_id: str


@dataclass(frozen=True, slots=True)
class TableFilters:
    view: str = "focused"
    search: str = ""
    minimum_acres: Decimal | None = None
    maximum_acres: Decimal | None = None
    classifications: tuple[str | None, ...] = ()
    improvement: str = "all"
    special: str = "all"
    sort: str = "parcel_id"
    descending: bool = False


@dataclass(frozen=True, slots=True)
class TablePage:
    filtered: tuple[ParcelRow, ...]
    rows: tuple[ParcelRow, ...]
    counts: tuple[tuple[str, int], ...]
    page: int
    pages: int


def project_rows(prior: list[dict], current: list[dict], floor: Decimal) -> tuple[ParcelRow, ...]:
    """Allowlist fields from saved canonical exports; do not expose raw dictionaries."""
    merged: dict[str, ParcelRow] = {}
    fields = (
        "parcel_id",
        "deeded_acres",
        "property_classification",
        "improvement_value",
        "owner_name",
    )
    for period, records in (("prior", prior), ("current", current)):
        seen = set()
        for record in records:
            key = record["parcel_id"]
            if not isinstance(key, str) or not key or key in seen:
                raise ValueError("Duplicate or invalid parcel identity in a period view")
            seen.add(key)
            values = {field: record[field] for field in fields}
            for field in ("property_classification", "owner_name"):
                if values[field] is not None and not isinstance(values[field], str):
                    raise ValueError("Invalid source display text")
            values["deeded_acres"] = number(values["deeded_acres"])
            values["improvement_value"] = number(values["improvement_value"])
            row = ParcelRow(
                **values,
                prior=period == "prior",
                current=period == "current",
                bucket=review_bucket(record),
            )
            if key in merged:
                old = merged[key]
                if any(getattr(old, field) != getattr(row, field) for field in fields):
                    raise ValueError("Conflicting parcel facts across period views")
                row = ParcelRow(**values, prior=True, current=True, bucket=row.bucket)
            merged[key] = row
    return tuple(
        row
        for _, row in sorted(merged.items())
        if row.deeded_acres is not None and row.deeded_acres >= floor
    )


def in_view(row: ParcelRow, view: str) -> bool:
    return {
        "focused": row.prior and row.focused,
        "outside_special": row.prior and not row.special,
        "prior": row.prior,
        "special": row.prior and row.special,
        "current": row.current,
        "either": row.prior or row.current,
        "both": row.prior and row.current,
    }[view]


def query(
    dataset: ParcelDataset, filters: TableFilters, *, page: int = 1, page_size: int = 25
) -> TablePage:
    """Inclusive Decimal bounds, explicit null-last ordering and ID tie breaks.

    Counts reflect all non-view filters, so period overlap stays visible. Pagination
    never changes the full filtered identity set used by the keyboard selector.
    """
    if (
        filters.view not in VIEWS
        or filters.improvement not in IMPROVEMENTS
        or filters.special not in SPECIAL
        or filters.sort not in SORTS
        or type(filters.descending) is not bool
        or not isinstance(filters.search, str)
        or len(filters.search) > 200
        or type(page) is not int
        or page < 1
        or type(page_size) is not int
        or not 1 <= page_size <= 100
        or not isinstance(filters.classifications, tuple)
        or any(c is not None and not isinstance(c, str) for c in filters.classifications)
    ):
        raise ValueError("Invalid table filter, sort or pagination value")
    lower = (
        number(filters.minimum_acres)
        if filters.minimum_acres is not None
        else dataset.minimum_acres
    )
    upper = number(filters.maximum_acres)
    if lower < dataset.minimum_acres:
        raise ValueError(
            f"Minimum cannot be below the loaded candidate floor of {dataset.minimum_acres} acres"
        )
    if upper is not None and upper < lower:
        raise ValueError("Maximum acres must be at least minimum acres")
    term = filters.search.strip().casefold()
    try:
        id_term = normalize_parcel_id(term)
    except ValueError:
        id_term = None
    matches = []
    for row in dataset.rows:
        if (
            row.deeded_acres is None
            or row.deeded_acres < lower
            or (upper is not None and row.deeded_acres > upper)
        ):
            continue
        if (
            term
            and not (id_term and id_term in normalize_parcel_id(row.parcel_id))
            and not any(
                term in text.casefold()
                for text in (
                    row.parcel_id,
                    row.owner_name or "",
                    row.property_classification or "",
                )
            )
        ):
            continue
        if filters.classifications and row.property_classification not in filters.classifications:
            continue
        improvement = row.improvement_value
        if (
            (filters.improvement == "known" and improvement is None)
            or (filters.improvement == "unknown" and improvement is not None)
            or (filters.improvement == "zero" and improvement != 0)
            or (filters.improvement == "nonzero" and (improvement is None or improvement == 0))
        ):
            continue
        if (
            (filters.special == "only" and not row.special)
            or (
                filters.special == "exclude"
                and (row.special or row.property_classification is None)
            )
            or (filters.special == "unknown" and row.property_classification is not None)
        ):
            continue
        matches.append(row)
    counts = tuple((view, sum(in_view(row, view) for row in matches)) for view in VIEWS)
    selected = [row for row in matches if in_view(row, filters.view)]
    known = [row for row in selected if getattr(row, filters.sort) is not None]
    unknown = [row for row in selected if getattr(row, filters.sort) is None]
    # Two stable sorts keep the ID tie-break ascending even for descending values.
    known.sort(key=lambda row: row.parcel_id)
    known.sort(key=lambda row: getattr(row, filters.sort), reverse=filters.descending)
    unknown.sort(key=lambda row: row.parcel_id)
    ordered = tuple(known + unknown)
    pages = max(1, (len(ordered) + page_size - 1) // page_size)
    page = min(page, pages)
    start = (page - 1) * page_size
    return TablePage(ordered, ordered[start : start + page_size], counts, page, pages)


def select_parcel(dataset: ParcelDataset, result: TablePage, parcel_id: str) -> ParcelIdentity:
    if not any(row.parcel_id == parcel_id for row in result.filtered):
        raise ValueError("Parcel is not in the filtered result")
    return ParcelIdentity(
        "Isanti", dataset.overview.key.token, dataset.overview.completion_sha256, parcel_id
    )


def selected_row(
    dataset: ParcelDataset, result: TablePage, identity: ParcelIdentity
) -> ParcelRow | None:
    if (
        identity.county != "Isanti"
        or identity.snapshot_token != dataset.overview.key.token
        or identity.completion_sha256 != dataset.overview.completion_sha256
    ):
        return None
    return next((row for row in result.filtered if row.parcel_id == identity.parcel_id), None)


def selector_ids(result: TablePage, previous: str | None) -> tuple[str, ...]:
    """Bound browser option transfer, retaining any still-filtered selection."""
    if len(result.filtered) <= 2000:
        return tuple(row.parcel_id for row in result.filtered)
    ids = tuple(row.parcel_id for row in result.rows)
    if (
        previous is not None
        and previous not in ids
        and any(row.parcel_id == previous for row in result.filtered)
    ):
        ids += (previous,)
    return ids
