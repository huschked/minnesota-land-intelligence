from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from mn_land.counties.isanti.delinquency import normalize_parcel_id
from mn_land.models import (
    DelinquencyRecord,
    DelinquencyStatus,
    Parcel,
    ParcelDelinquencyMatch,
    TaxPeriodStatus,
)


@dataclass(frozen=True, slots=True)
class JoinResult:
    matches: tuple[ParcelDelinquencyMatch, ...]
    unmatched_records: tuple[DelinquencyRecord, ...]
    duplicate_records: dict[str, tuple[DelinquencyRecord, ...]]
    ambiguous_records: tuple[DelinquencyRecord, ...]
    parcel_count: int
    delinquency_record_count: int

    @property
    def exact_matches(self) -> tuple[ParcelDelinquencyMatch, ...]:
        return tuple(
            match for match in self.matches
            if match.status in (
                DelinquencyStatus.VERIFIED_DELINQUENT, DelinquencyStatus.UNVERIFIED
                , DelinquencyStatus.OVERDUE_CURRENT_YEAR
            )
        )

    @property
    def verified_matches(self) -> tuple[ParcelDelinquencyMatch, ...]:
        return tuple(match for match in self.matches if match.status == DelinquencyStatus.VERIFIED_DELINQUENT)


def join_delinquency_records(
    parcels: list[Parcel], records: list[DelinquencyRecord]
) -> JoinResult:
    parcel_index: dict[str, list[Parcel]] = defaultdict(list)
    for parcel in parcels:
        parcel_index[normalize_parcel_id(parcel.parcel_id)].append(parcel)

    record_index: dict[str, list[DelinquencyRecord]] = defaultdict(list)
    for record in records:
        record_index[record.normalized_parcel_id].append(record)

    matches: list[ParcelDelinquencyMatch] = []
    unmatched: list[DelinquencyRecord] = []
    ambiguous: list[DelinquencyRecord] = []
    duplicates = {
        key: tuple(group) for key, group in record_index.items() if len(group) > 1
    }

    for key, group in record_index.items():
        parcel_group = parcel_index.get(key, [])
        if not parcel_group:
            unmatched.extend(group)
            continue
        if len(parcel_group) == 1 and all(
            record.tax_period_status != TaxPeriodStatus.UNVERIFIED for record in group
        ):
            # Multiple authoritative unpaid rows establish presence, not an additive balance.
            prior = any(r.tax_period_status == TaxPeriodStatus.PRIOR_YEAR_UNPAID for r in group)
            hold = next((r.verification_hold_reason for r in group if r.verification_hold_reason), None)
            status = (
                DelinquencyStatus.UNVERIFIED if hold
                else DelinquencyStatus.VERIFIED_DELINQUENT if prior
                else DelinquencyStatus.OVERDUE_CURRENT_YEAR
            )
            matches.append(ParcelDelinquencyMatch(
                parcel_group[0], group[0] if len(group) == 1 else None,
                status, hold, tuple(group),
            ))
            continue
        if len(group) > 1:
            ambiguous.extend(group)
            for parcel in parcel_group:
                matches.append(
                    ParcelDelinquencyMatch(
                        parcel, None, DelinquencyStatus.AMBIGUOUS, "duplicate delinquency rows"
                    )
                )
            continue
        if len(parcel_group) > 1:
            ambiguous.extend(group)
            for parcel in parcel_group:
                matches.append(
                    ParcelDelinquencyMatch(
                        parcel, group[0], DelinquencyStatus.AMBIGUOUS, "duplicate parcel join key"
                    )
                )
            continue
        matches.append(
            ParcelDelinquencyMatch(
                parcel_group[0], group[0],
                DelinquencyStatus.UNVERIFIED if group[0].verification_hold_reason
                else DelinquencyStatus.VERIFIED_DELINQUENT,
                group[0].verification_hold_reason,
            )
        )

    return JoinResult(
        matches=tuple(matches),
        unmatched_records=tuple(unmatched),
        duplicate_records=duplicates,
        ambiguous_records=tuple(ambiguous),
        parcel_count=len(parcels),
        delinquency_record_count=len(records),
    )
