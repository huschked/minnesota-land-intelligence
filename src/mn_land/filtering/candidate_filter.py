from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal

from mn_land.models import Parcel
from mn_land.utils.validation import minimum_acres


@dataclass(slots=True)
class FilterResult:
    accepted: list[Parcel] = field(default_factory=list)
    rejected: Counter[str] = field(default_factory=Counter)


def filter_candidates(parcels: list[Parcel], min_acres: Decimal) -> FilterResult:
    min_acres = minimum_acres(min_acres)
    result = FilterResult()
    for parcel in parcels:
        if parcel.deeded_acres is None:
            result.rejected["missing_acreage"] += 1
        elif parcel.deeded_acres < min_acres:
            result.rejected["under_minimum_acreage"] += 1
        elif not parcel.tax_semantics_verified:
            result.rejected["ambiguous_tax_semantics"] += 1
        elif parcel.past_due_tax_amount is None:
            result.rejected["missing_past_due_tax"] += 1
        elif parcel.past_due_tax_amount <= 0:
            result.rejected["no_past_due_tax"] += 1
        else:
            result.accepted.append(parcel)
    return result
