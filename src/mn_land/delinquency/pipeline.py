from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from mn_land.config.input_limits import DEFAULT_INPUT_LIMITS, InputLimits
from mn_land.config.settings import SETTINGS
from mn_land.counties.isanti import IsantiAdapter
from mn_land.delinquency.exporters import export_join_result
from mn_land.delinquency.file_loader import DelinquencyMapping, FileDelinquencySource
from mn_land.delinquency.join import join_delinquency_records
from mn_land.delinquency.tabular import read_input
from mn_land.ingestion.normalization import normalize_with_diagnostics
from mn_land.models import Parcel, TaxPeriodStatus
from mn_land.provenance import build_provenance, sha256_file
from mn_land.replay import check_destination, input_dates, normalized_digest, selected_snapshot
from mn_land.runs import (
    JOIN_OUTPUTS,
    RunValidationError,
    RunWorkspace,
    ValidatedRun,
    artifact_row_count,
    read_json,
    safe_path,
    select_latest,
    validate_run,
    write_json,
)
from mn_land.utils.validation import minimum_acres


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


def _copy_input(origin: Path, target: Path, limits: InputLimits) -> str:
    # One bounded byte capture; normalization never rereads the mutable original.
    body = read_input(origin, limits)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as handle:
        handle.write(body)
    return hashlib.sha256(body).hexdigest()


def import_and_join_delinquency(
    file_path: Path,
    mapping_path: Path,
    min_acres: Decimal,
    *,
    adapter: IsantiAdapter | None = None,
    raw_root: Path | None = None,
    processed_root: Path | None = None,
    limits: InputLimits = DEFAULT_INPUT_LIMITS,
    parcel_snapshot: Path | None = None,
) -> DelinquencyPipelineStats:
    min_acres = minimum_acres(min_acres)
    check_destination((processed_root or SETTINGS.processed_dir) / "isanti/delinquency")
    check_destination((raw_root or SETTINGS.raw_dir) / "isanti/delinquency")
    if parcel_snapshot is not None:
        selected = selected_snapshot(parcel_snapshot, "parcel_raw")
        (adapter or IsantiAdapter()).validate_snapshot_source(selected.manifest)
        check_destination(
            (processed_root or SETTINGS.processed_dir) / "isanti/delinquency", selected.path
        )
        check_destination((raw_root or SETTINGS.raw_dir) / "isanti/delinquency", selected.path)
    # Capture the bounded mapping first. Resolve/validate its references before
    # copying any source/supporting bytes; rejected mappings remain private evidence.
    raw_root = raw_root or SETTINGS.raw_dir
    processed_root = processed_root or SETTINGS.processed_dir
    run_at = datetime.now(UTC)
    with RunWorkspace(raw_root / "isanti" / "delinquency", "delinquency_raw") as raw:
        raw.stage = "capture_mapping"
        mapping_digest = _copy_input(mapping_path, raw.path / "mapping.json", limits)
        mapping = DelinquencyMapping.from_json(
            raw.path / "mapping.json", limits=limits, supporting_root=mapping_path.parent
        )
        raw.stage = "capture_source_and_supporting"
        source_copy = raw.path / f"source{file_path.suffix.lower()}"
        source_digest = _copy_input(file_path, source_copy, limits)
        supporting = []
        for name, source_document in mapping.supporting_paths(mapping_path.parent).items():
            supporting.append(
                {
                    "file": f"supporting/{name}",
                    "sha256": _copy_input(source_document, raw.path / "supporting" / name, limits),
                }
            )
        mapping = DelinquencyMapping.from_json(
            raw.path / "mapping.json", limits=limits, supporting_root=raw.path / "supporting"
        )
        raw.stage = "validate_retained_import"
        records = FileDelinquencySource(
            source_copy, mapping, limits=limits, retrieved_at=run_at
        ).load_records()
        raw.counts["records"] = len(records)
        write_json(
            raw.path / "manifest.json",
            {
                "county": "Isanti",
                "imported_at": run_at.isoformat(),
                "source_original_name": file_path.name,
                "source_file": source_copy.name,
                "source_sha256": source_digest,
                "mapping_sha256": mapping_digest,
                "record_count": len(records),
                "input_limits": asdict(limits),
                "supporting_documents": supporting,
            },
        )
        raw.publish()

    return _join_snapshots(
        raw.path, min_acres, parcel_snapshot=parcel_snapshot, adapter=adapter,
        raw_root=raw_root, processed_root=processed_root,
        command="import-delinquency", enforce_source=parcel_snapshot is not None,
    )


def replay_delinquency(
    *, snapshot: Path | None = None,
    parcel_snapshot: Path | None = None, import_snapshot: Path | None = None,
    min_acres: Decimal | None = None, processed_root: Path | None = None,
    adapter: IsantiAdapter | None = None,
) -> DelinquencyPipelineStats:
    """Reprocess explicit completed retained inputs, without raw writes or HTTP.

    An existing join supplies its pinned sources and recorded threshold. Selecting
    a raw pair instead never consults latest or historical absolute path fields.
    Legacy/failed inputs cannot be certified by replay.
    """
    expected = None
    if snapshot is not None:
        if parcel_snapshot is not None or import_snapshot is not None:
            raise ValueError("Choose a completed join OR an explicit parcel/import pair, not both")
        expected = selected_snapshot(snapshot, "delinquency_processed")
        parcel_snapshot, import_snapshot = expected.source("parcel"), expected.source("delinquency")
        threshold = minimum_acres(expected.manifest["minimum_acres"])
    else:
        if parcel_snapshot is None or import_snapshot is None:
            raise ValueError("Replay requires both --parcel-snapshot and --import-snapshot")
        threshold = Decimal(SETTINGS.default_min_acres)
    threshold = threshold if min_acres is None else minimum_acres(min_acres)
    parcel = selected_snapshot(parcel_snapshot, "parcel_raw")
    imported = selected_snapshot(import_snapshot, "delinquency_raw")
    if imported.manifest.get("county") != "Isanti":
        raise RunValidationError("Import snapshot is incompatible with Isanti County")
    (adapter or IsantiAdapter()).validate_snapshot_source(parcel.manifest)
    root = (processed_root or SETTINGS.processed_dir) / "isanti/delinquency"
    check_destination(root, parcel.path, imported.path, *([expected.path] if expected else []))
    return _join_snapshots(
        imported.path, threshold, parcel_snapshot=parcel.path, adapter=adapter,
        processed_root=processed_root or SETTINGS.processed_dir,
        command="replay-delinquency", enforce_source=True, expected=expected,
    )


def _join_snapshots(
    import_snapshot: Path, min_acres: Decimal, *,
    parcel_snapshot: Path | None, adapter: IsantiAdapter | None,
    processed_root: Path, raw_root: Path | None = None,
    command: str, enforce_source: bool, expected: ValidatedRun | None = None,
) -> DelinquencyPipelineStats:
    adapter = adapter or IsantiAdapter()
    with RunWorkspace(
        processed_root / "isanti" / "delinquency", "delinquency_processed"
    ) as processed:
        processed.stage = "select_and_pin_sources"
        selection_diagnostics = []
        selected = (
            validate_run(parcel_snapshot, "parcel_raw")
            if parcel_snapshot is not None else select_latest(
                (raw_root or SETTINGS.raw_dir) / "isanti", "parcel_raw",
                diagnostics=selection_diagnostics,
            )
        )
        parcel_snapshot = processed.pin(selected.path, "parcel")
        raw_snapshot = processed.pin(import_snapshot, "delinquency")
        parcel_input = validate_run(parcel_snapshot, "parcel_raw")
        retained_input = validate_run(raw_snapshot, "delinquency_raw")
        if retained_input.manifest.get("county") != "Isanti":
            raise RunValidationError("Import snapshot is incompatible with Isanti County")
        if enforce_source:
            adapter.validate_snapshot_source(parcel_input.manifest)
        limits = InputLimits(**retained_input.manifest["input_limits"])
        # Re-normalize from these pinned inputs, not the original/copy used to validate raw completion.
        pinned_mapping = DelinquencyMapping.from_json(
            raw_snapshot / "mapping.json",
            limits=limits,
            supporting_root=raw_snapshot / "supporting",
        )
        retained_manifest = read_json(raw_snapshot / "manifest.json")
        source_name = retained_manifest["source_file"]
        processed.stage = "normalization_and_join"
        records = FileDelinquencySource(
            raw_snapshot / source_name,
            pinned_mapping,
            limits=limits,
            retrieved_at=datetime.fromisoformat(retained_manifest["imported_at"]),
        ).load_records()
        diagnostics: list[dict[str, Any]] = []
        parcels, parcel_errors, _ = load_parcel_snapshot(
            adapter, parcel_snapshot, diagnostics=diagnostics
        )
        result = join_delinquency_records(parcels, records)
        accounting = {
            "matched": sorted(
                record.source_row_number
                for match in result.exact_matches
                for record in match.records
            ),
            "unmatched": sorted(record.source_row_number for record in result.unmatched_records),
            "ambiguous": sorted(record.source_row_number for record in result.ambiguous_records),
            "duplicate_review": sorted(
                record.source_row_number
                for group in result.duplicate_records.values()
                for record in group
            ),
            "prior_year": sorted(
                record.source_row_number
                for record in records
                if record.tax_period_status == TaxPeriodStatus.PRIOR_YEAR_UNPAID
            ),
            "current_year": sorted(
                record.source_row_number
                for record in records
                if record.tax_period_status == TaxPeriodStatus.OVERDUE_CURRENT_YEAR
            ),
            "unverified_period": sorted(
                record.source_row_number
                for record in records
                if record.tax_period_status == TaxPeriodStatus.UNVERIFIED
            ),
        }
        processed.counts.update(
            records=len(records), parcels=len(parcels), quarantined=parcel_errors
        )
        write_json(processed.path / "accounting.json", accounting)
        write_json(processed.path / "normalization_diagnostics.json", diagnostics)
        processed.stage = "join_exports"
        outputs, candidate_count = export_join_result(
            result, processed.path, min_acres, directory_reserved=True
        )
        row_counts = {name: artifact_row_count(processed.path / name) for name in JOIN_OUTPUTS}
        reproduction = {
            "schema_version": 1,
            "normalized_parcels_sha256": normalized_digest(parcels),
            "normalized_delinquency_sha256": normalized_digest(records),
            "exports_sha256": {name: sha256_file(processed.path / name) for name in JOIN_OUTPUTS},
            "candidate_ids": sorted(
                row["parcel_id"] for row in read_json(
                    processed.path / "isanti_verified_delinquent_candidates.json"
                )
            ),
        }
        comparison = "not_requested"
        if expected is not None:
            previous = expected.manifest.get("reproducibility")
            if previous is not None and any(
                previous[name] != reproduction[name]
                for name in ("normalized_parcels_sha256", "normalized_delinquency_sha256")
            ):
                raise RunValidationError("Replay normalized content differs from the selected result")
            if min_acres == minimum_acres(expected.manifest["minimum_acres"]):
                old_exports = {
                    entry["path"]: entry["sha256"] for entry in expected.completion["artifacts"]
                }
                if any(
                    old_exports[name] != digest
                    for name, digest in reproduction["exports_sha256"].items()
                ):
                    raise RunValidationError("Replay exports differ from the selected result")
                comparison = (
                    "identical_exports_and_recorded_normalization" if previous
                    else "identical_exports_historical_normalization_unknown"
                )
            else:
                comparison = "threshold_changed_exports_not_compared"
        selection = {
            "mode": (
                "recorded_join" if expected else "explicit_pair" if enforce_source
                else "latest_eligible_parcel"
            ),
            "parcel_run_id": parcel_input.path.name,
            "import_run_id": retained_input.path.name,
            "parcel_completion_sha256": parcel_input.completion_sha256,
            "import_completion_sha256": retained_input.completion_sha256,
            "dates": input_dates(
                parcel_input.manifest, retained_input.manifest, pinned_mapping.publication_date
            ),
            "replayed_from": None if expected is None else {
                "run_id": expected.path.name, "completion_sha256": expected.completion_sha256,
                "minimum_acres": expected.manifest["minimum_acres"],
            },
            "comparison": comparison,
        }
        manifest = {
            "county": "Isanti",
            "created_at": datetime.now(UTC).isoformat(),
            "parcel_snapshot": str(parcel_snapshot),
            "delinquency_snapshot": str(raw_snapshot),
            "processed_snapshot": str(processed.path),
            "minimum_acres": str(min_acres),
            "parcel_records_loaded": len(parcels),
            "parcel_normalization_errors": parcel_errors,
            "delinquency_records_loaded": len(records),
            "exact_normalized_matches": len(result.exact_matches),
            "verified_delinquency_matches": len(result.verified_matches),
            "overdue_current_year_only_matches": sum(
                match.status.value == "overdue_current_year" for match in result.matches
            ),
            "prior_year_source_rows": len(accounting["prior_year"]),
            "current_year_source_rows": len(accounting["current_year"]),
            "unverified_matches": sum(
                match.status.value == "unverified" for match in result.matches
            ),
            "unmatched_delinquency_records": len(result.unmatched_records),
            "duplicate_delinquency_parcel_ids": len(result.duplicate_records),
            "ambiguous_records": len(result.ambiguous_records),
            "verified_candidates": candidate_count,
            "current_year_view_count": row_counts["isanti_overdue_current_year_parcels.json"],
            "parcel_normalization_diagnostics": diagnostics,
            "selection_diagnostics": selection_diagnostics,
            "input_limits": asdict(limits),
            "selection": selection,
            "reproducibility": reproduction,
        }
        manifest["provenance"] = build_provenance(
            {
                "command": command,
                "county": "Isanti",
                "minimum_acres": str(min_acres),
                "input_limits": asdict(limits),
            },
            inputs=[path for path in (processed.path / "inputs").rglob("*") if path.is_file()],
            outputs=outputs,
        )
        write_json(processed.path / "manifest.json", manifest)
        processed.publish(row_counts=row_counts)
    return DelinquencyPipelineStats(
        records_loaded=len(records),
        parcels_loaded=len(parcels),
        parcel_normalization_errors=parcel_errors,
        exact_matches=len(result.exact_matches),
        unmatched_records=len(result.unmatched_records),
        duplicate_parcel_ids=len(result.duplicate_records),
        ambiguous_records=len(result.ambiguous_records),
        verified_candidates=candidate_count,
        raw_snapshot_dir=import_snapshot,
        processed_snapshot_dir=processed.path,
        output_paths=(
            *outputs,
            processed.path / "manifest.json",
            processed.path / "completion.json",
        ),
    )


def load_latest_parcel_snapshot(
    adapter: IsantiAdapter,
    county_raw_root: Path,
    *,
    diagnostics: list[dict[str, Any]] | None = None,
) -> tuple[list[Parcel], int, Path]:
    selected = select_latest(county_raw_root, "parcel_raw", diagnostics=diagnostics)
    return load_parcel_snapshot(adapter, selected.path, diagnostics=diagnostics)


def load_parcel_snapshot(
    adapter: IsantiAdapter,
    snapshot: Path,
    *,
    diagnostics: list[dict[str, Any]] | None = None,
    allow_legacy: bool = False,
) -> tuple[list[Parcel], int, Path]:
    """Read complete inputs, or deliberately inspect legacy evidence read-only.

    Legacy mode never publishes a marker and is not used by new producers/latest.
    An invalid version-2 record cannot be downgraded to legacy to bypass checks.
    """
    diagnostics = diagnostics if diagnostics is not None else []
    if allow_legacy and not (snapshot / "completion.json").exists():
        if any(
            (snapshot / name).exists()
            for name in ("reservation.json", "completion.pending.json", "failure.json")
        ):
            raise RunValidationError(
                "New-protocol staging/failed runs cannot use legacy compatibility"
            )
        manifest = read_json(safe_path(snapshot, "manifest.json"))
        expected = manifest.get("record_count")
        if type(expected) is not int or expected < 0:
            raise RunValidationError("Legacy input needs an explicit valid record count")
        for artifact in manifest.get("provenance", {}).get("outputs", []):
            # Historical absolute provenance locations are not followed. Validate
            # their corresponding contained artifacts at the selected snapshot.
            original = Path(artifact["path"])
            name = f"http/{original.name}" if original.parent.name == "http" else original.name
            if sha256_file(safe_path(snapshot, name)) != artifact["sha256"]:
                raise RunValidationError("Legacy available artifact hash mismatch")
        diagnostics.append(
            {
                "severity": "warning",
                "reason": "legacy/unverified read-only access; completion/source-consistency checks unavailable",
            }
        )
    else:
        validated = validate_run(snapshot, "parcel_raw")
        snapshot, manifest = validated.path, validated.manifest
    retrieved_at = datetime.fromisoformat(manifest["retrieved_at"])
    if retrieved_at.tzinfo is None:
        raise RunValidationError("Snapshot date requires timezone")
    metadata_path = snapshot / "layer_metadata.json"
    if metadata_path.is_file():
        adapter.validate_metadata(read_json(safe_path(snapshot, metadata_path.name)))
    else:
        diagnostics.append(
            {
                "severity": "warning",
                "field": "schema",
                "reason": "legacy snapshot has no layer metadata",
            }
        )
    parcels, errors = [], 0
    pages = sorted(snapshot.glob("page_*.json"))
    if "pages" in manifest and manifest["pages"] != len(pages):
        raise RunValidationError("Snapshot page count mismatch")
    for page_path in pages:
        payload = read_json(safe_path(snapshot, page_path.name))
        if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
            raise RunValidationError("Missing snapshot feature list")
        for index, raw_record in enumerate(payload["features"], 1):
            parcel = normalize_with_diagnostics(
                adapter,
                raw_record,
                retrieved_at,
                {"raw_page": str(page_path), "feature_number": index},
                diagnostics,
            )
            if parcel is None:
                errors += 1
            else:
                parcels.append(parcel)
    if len(parcels) + errors != manifest["record_count"]:
        raise RunValidationError("Parcel snapshot record count mismatch")
    return parcels, errors, snapshot
