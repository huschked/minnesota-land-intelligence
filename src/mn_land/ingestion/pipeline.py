from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from mn_land.config.settings import SETTINGS
from mn_land.counties.base import CountyAdapter
from mn_land.export.exporters import (
    export_candidates,
    export_tax_semantics_review_sample,
    export_verification_sample,
)
from mn_land.filtering.candidate_filter import filter_candidates
from mn_land.provenance import build_provenance

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PipelineStats:
    retrieved: int
    normalized: int
    normalization_errors: int
    candidates: int
    tax_semantics_review_records: int
    rejected: Counter[str]
    raw_run_dir: Path
    output_paths: tuple[Path, ...]


def run_pipeline(adapter: CountyAdapter, min_acres: Decimal) -> PipelineStats:
    retrieved_at = datetime.now(UTC)
    run_id = retrieved_at.strftime("%Y-%m-%dT%H%M%SZ")
    raw_run_dir = SETTINGS.raw_dir / "isanti" / run_id
    parcels = []
    retrieved = 0
    errors = 0
    for raw in adapter.fetch_parcels(raw_run_dir, retrieved_at):
        retrieved += 1
        try:
            parcels.append(adapter.normalize_parcel(raw, retrieved_at))
        except ValueError as exc:
            errors += 1
            LOGGER.warning("normalization_failed record=%s error=%s", retrieved, exc)
    filtered = filter_candidates(parcels, min_acres)
    csv_path, json_path = export_candidates(filtered.accepted, SETTINGS.processed_dir)
    sample_path = export_verification_sample(filtered.accepted, SETTINGS.processed_dir)
    review_path, review_count = export_tax_semantics_review_sample(
        parcels, SETTINGS.processed_dir, min_acres
    )
    execution_path = raw_run_dir / "execution.json"
    execution = build_provenance(
        {"command": "find-candidates", "minimum_acres": str(min_acres),
         "adapter": f"{type(adapter).__module__}.{type(adapter).__qualname__}"},
        inputs=[path for path in raw_run_dir.iterdir() if path.is_file()],
        outputs=(csv_path, json_path, sample_path, review_path),
    )
    with execution_path.open("x", encoding="utf-8") as handle:
        json.dump(execution, handle, indent=2)
        handle.write("\n")
    return PipelineStats(
        retrieved=retrieved,
        normalized=len(parcels),
        normalization_errors=errors,
        candidates=len(filtered.accepted),
        tax_semantics_review_records=review_count,
        rejected=filtered.rejected,
        raw_run_dir=raw_run_dir,
        output_paths=(csv_path, json_path, sample_path, review_path, execution_path),
    )
