from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from mn_land.config.settings import SETTINGS
from mn_land.counties.isanti import IsantiAdapter
from mn_land.delinquency.exporters import export_join_result
from mn_land.delinquency.file_loader import (
    DelinquencyMapping,
    FileDelinquencySource,
)
from mn_land.delinquency.join import JoinResult, join_delinquency_records
from mn_land.models import Parcel
from mn_land.provenance import build_provenance


class DelinquencyPipelineError(RuntimeError):
    """The authoritative delinquency workflow cannot complete safely."""


@dataclass(frozen=True, slots=True)
class DelinquencyPipelineStats:
    records_loaded: int
    parcels_loaded: int
    parcel_normalization_errors: int
    exact_matches: int
    unmatched_records: int
    duplicate_parcel_ids: int
    ambiguous_records: int
    verified_candidates: int
    raw_snapshot_dir: Path
    processed_snapshot_dir: Path
    output_paths: tuple[Path, ...]


def import_and_join_delinquency(
    file_path: Path,
    mapping_path: Path,
    min_acres: Decimal,
    *,
    adapter: IsantiAdapter | None = None,
    raw_root: Path | None = None,
    processed_root: Path | None = None,
) -> DelinquencyPipelineStats:
    mapping = DelinquencyMapping.from_json(mapping_path)
    for document in mapping.supporting_documents:
        if not (mapping_path.parent / document).is_file():
            raise DelinquencyPipelineError(f"supporting source document missing: {document}")
    source = FileDelinquencySource(file_path, mapping)
    records = source.load_records()
    run_at = datetime.now(UTC)
    run_id = run_at.strftime("%Y-%m-%dT%H%M%S%fZ")
    raw_root = raw_root or SETTINGS.raw_dir
    processed_root = processed_root or SETTINGS.processed_dir
    raw_snapshot = raw_root / "isanti" / "delinquency" / run_id
    processed_snapshot = processed_root / "isanti" / "delinquency" / run_id
    _preserve_import(file_path, mapping_path, raw_snapshot, records, run_at)

    parcels, parcel_errors, parcel_snapshot = load_latest_parcel_snapshot(
        adapter or IsantiAdapter(), raw_root / "isanti"
    )
    result = join_delinquency_records(parcels, records)
    outputs, candidate_count = export_join_result(result, processed_snapshot, min_acres)
    manifest = _join_manifest(
        result,
        parcel_errors,
        parcel_snapshot,
        raw_snapshot,
        processed_snapshot,
        min_acres,
        candidate_count,
        run_at,
    )
    manifest_path = processed_snapshot / "manifest.json"
    manifest["provenance"] = build_provenance(
        {"command": "import-delinquency", "county": "Isanti", "minimum_acres": str(min_acres)},
        inputs=[
            *[path for path in raw_snapshot.rglob("*") if path.is_file()],
            parcel_snapshot / "manifest.json",
            *parcel_snapshot.glob("page_*.json"),
        ],
        outputs=outputs,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return DelinquencyPipelineStats(
        records_loaded=len(records),
        parcels_loaded=len(parcels),
        parcel_normalization_errors=parcel_errors,
        exact_matches=len(result.exact_matches),
        unmatched_records=len(result.unmatched_records),
        duplicate_parcel_ids=len(result.duplicate_records),
        ambiguous_records=len(result.ambiguous_records),
        verified_candidates=candidate_count,
        raw_snapshot_dir=raw_snapshot,
        processed_snapshot_dir=processed_snapshot,
        output_paths=(*outputs, manifest_path),
    )


def load_latest_parcel_snapshot(
    adapter: IsantiAdapter, county_raw_root: Path
) -> tuple[list[Parcel], int, Path]:
    snapshots = sorted(
        path
        for path in county_raw_root.iterdir()
        if path.is_dir() and path.name != "delinquency" and (path / "manifest.json").is_file()
    ) if county_raw_root.is_dir() else []
    if not snapshots:
        raise DelinquencyPipelineError(
            "no preserved Isanti parcel snapshot found; run find-candidates first"
        )
    snapshot = snapshots[-1]
    return load_parcel_snapshot(adapter, snapshot)


def load_parcel_snapshot(
    adapter: IsantiAdapter, snapshot: Path
) -> tuple[list[Parcel], int, Path]:
    """Normalize an explicitly selected preserved GIS snapshot."""
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    retrieved_at = datetime.fromisoformat(manifest["retrieved_at"])
    parcels: list[Parcel] = []
    errors = 0
    for page_path in sorted(snapshot.glob("page_*.json")):
        payload = json.loads(page_path.read_text(encoding="utf-8"))
        for raw_record in payload.get("features", []):
            try:
                parcels.append(adapter.normalize_parcel(raw_record, retrieved_at))
            except ValueError:
                errors += 1
    expected = manifest.get("record_count")
    if expected is not None and len(parcels) + errors != expected:
        raise DelinquencyPipelineError(
            f"parcel snapshot expected {expected} records but loaded {len(parcels) + errors}"
        )
    return parcels, errors, snapshot


def _preserve_import(
    file_path: Path,
    mapping_path: Path,
    snapshot: Path,
    records: list[Any],
    run_at: datetime,
) -> None:
    snapshot.mkdir(parents=True, exist_ok=False)
    source_copy = snapshot / f"source{file_path.suffix.lower()}"
    mapping_copy = snapshot / "mapping.json"
    shutil.copy2(file_path, source_copy)
    shutil.copy2(mapping_path, mapping_copy)
    mapping = DelinquencyMapping.from_json(mapping_copy)
    supporting = []
    for document in mapping.supporting_documents:
        source_document = mapping_path.parent / document
        target_dir = snapshot / "supporting"
        target_dir.mkdir(exist_ok=True)
        target_document = target_dir / source_document.name
        shutil.copy2(source_document, target_document)
        supporting.append({"file": str(target_document), "sha256": _sha256(target_document)})
    manifest = {
        "county": "Isanti",
        "imported_at": run_at.isoformat(),
        "source_original_name": file_path.name,
        "source_sha256": _sha256(source_copy),
        "mapping_sha256": _sha256(mapping_copy),
        "record_count": len(records),
        "supporting_documents": supporting,
    }
    (snapshot / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def _join_manifest(
    result: JoinResult,
    parcel_errors: int,
    parcel_snapshot: Path,
    raw_snapshot: Path,
    processed_snapshot: Path,
    min_acres: Decimal,
    candidate_count: int,
    run_at: datetime,
) -> dict[str, Any]:
    return {
        "county": "Isanti",
        "created_at": run_at.isoformat(),
        "parcel_snapshot": str(parcel_snapshot),
        "delinquency_snapshot": str(raw_snapshot),
        "processed_snapshot": str(processed_snapshot),
        "minimum_acres": str(min_acres),
        "parcel_records_loaded": result.parcel_count,
        "parcel_normalization_errors": parcel_errors,
        "delinquency_records_loaded": result.delinquency_record_count,
        "exact_normalized_matches": len(result.exact_matches),
        "verified_delinquency_matches": len(result.verified_matches),
        "overdue_current_year_only_matches": sum(match.status.value == "overdue_current_year" for match in result.matches),
        "prior_year_source_rows": sum(r.tax_period_status.value == "prior_year_unpaid" for match in result.matches for r in match.records)
            + sum(r.tax_period_status.value == "prior_year_unpaid" for r in result.unmatched_records),
        "current_year_source_rows": sum(r.tax_period_status.value == "overdue_current_year" for match in result.matches for r in match.records)
            + sum(r.tax_period_status.value == "overdue_current_year" for r in result.unmatched_records),
        "unverified_matches": sum(match.status.value == "unverified" for match in result.matches),
        "unmatched_delinquency_records": len(result.unmatched_records),
        "duplicate_delinquency_parcel_ids": len(result.duplicate_records),
        "ambiguous_records": len(result.ambiguous_records),
        "verified_candidates": candidate_count,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
