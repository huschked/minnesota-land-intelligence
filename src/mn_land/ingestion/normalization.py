"""Retain explicit row quarantines/warnings without losing raw source references."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from mn_land.counties.base import CountyAdapter
from mn_land.models import Parcel


def normalize_with_diagnostics(
    adapter: CountyAdapter,
    raw: Mapping[str, Any],
    retrieved_at: datetime,
    location: dict[str, Any],
    diagnostics: list[dict[str, Any]],
) -> Parcel | None:
    reference = {**location, "source_record_id": adapter.record_identifier(raw)}
    try:
        parcel = adapter.normalize_parcel(raw, retrieved_at)
    except ValueError as exc:
        diagnostics.append(
            {
                **reference,
                "severity": "error",
                "field": getattr(exc, "field", None),
                "reason": str(exc),
            }
        )
        return None
    for warning in parcel.source_metadata.validation_warnings:
        diagnostics.append({**reference, "severity": "warning", "reason": warning})
    return parcel
