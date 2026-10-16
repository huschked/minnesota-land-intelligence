from __future__ import annotations

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
from mn_land.run_checks import parcel_ids
from mn_land.runs import PARCEL_OUTPUTS, RunWorkspace, artifact_row_count, write_json
from mn_land.utils.validation import minimum_acres


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
    processed_run_dir: Path


def run_pipeline(adapter: CountyAdapter, min_acres: Decimal) -> PipelineStats:
    min_acres = minimum_acres(min_acres)
    retrieved_at = datetime.now(UTC)
    with RunWorkspace(SETTINGS.raw_dir / "isanti", "parcel_raw") as raw:
        raw.stage = "acquisition"
        # Drain retrieval before any normalization/export. The retained pages,
        # not separately yielded in-memory objects, become the authoritative input.
        for _ in adapter.fetch_parcels(raw.path, retrieved_at, directory_reserved=True):
            raw.counts["retrieved"] = raw.counts.get("retrieved", 0) + 1
        raw.publish()

    with RunWorkspace(
        SETTINGS.processed_dir / "isanti" / "parcels", "parcel_processed"
    ) as processed:
        processed.stage = "pin_raw"
        pinned = processed.pin(raw.path, "parcel")
        processed.stage = "normalization"
        from mn_land.delinquency.pipeline import load_parcel_snapshot

        diagnostics = []
        parcels, errors, _ = load_parcel_snapshot(adapter, pinned, diagnostics=diagnostics)
        ids = parcel_ids(pinned)
        quarantined = {
            entry["source_record_id"] for entry in diagnostics if entry.get("severity") == "error"
        }
        processed.counts.update(retrieved=len(ids), normalized=len(parcels), quarantined=errors)
        write_json(processed.path / "normalization_diagnostics.json", diagnostics)
        write_json(
            processed.path / "accounting.json",
            {
                "normalized_source_ids": sorted(ids - quarantined),
                "quarantined_source_ids": sorted(quarantined),
            },
        )
        processed.stage = "filter_and_exports"
        filtered = filter_candidates(parcels, min_acres)
        csv_path, json_path = export_candidates(filtered.accepted, processed.path)
        sample_path = export_verification_sample(filtered.accepted, processed.path)
        review_path, review_count = export_tax_semantics_review_sample(
            parcels, processed.path, min_acres
        )
        exports = (csv_path, json_path, sample_path, review_path)
        execution = build_provenance(
            {
                "command": "find-candidates",
                "minimum_acres": str(min_acres),
                "adapter": f"{type(adapter).__module__}.{type(adapter).__qualname__}",
            },
            inputs=[path for path in pinned.rglob("*") if path.is_file()],
            outputs=exports,
        )
        write_json(processed.path / "execution.json", execution)
        write_json(
            processed.path / "manifest.json",
            {
                "county": "Isanti",
                "retrieved": len(ids),
                "normalized": len(parcels),
                "quarantined": errors,
                "candidates": len(filtered.accepted),
                "minimum_acres": str(min_acres),
                "provenance": execution,
            },
        )
        processed.publish(
            row_counts={name: artifact_row_count(processed.path / name) for name in PARCEL_OUTPUTS}
        )
    return PipelineStats(
        retrieved=len(ids),
        normalized=len(parcels),
        normalization_errors=errors,
        candidates=len(filtered.accepted),
        tax_semantics_review_records=review_count,
        rejected=filtered.rejected,
        raw_run_dir=raw.path,
        processed_run_dir=processed.path,
        output_paths=(
            *exports,
            processed.path / "execution.json",
            processed.path / "completion.json",
        ),
    )
