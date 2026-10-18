"""Read-only saved-result boundary. No Streamlit, acquisition or replay imports.

Overview, candidate-table and source-evidence DTOs are immutable allowlists.
Contextual exports revalidate pinned evidence rather than serving saved raw files.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from itertools import islice
from pathlib import Path

from mn_land.config.input_limits import InputLimits
from mn_land.counties.isanti.evidence import public_link
from mn_land.counties.isanti.worklists import ISSUE_TABLES
from mn_land.delinquency.tabular import read_table_bytes
from mn_land.parcel_details import ParcelDetails, project_details
from mn_land.parcel_table import ParcelDataset, ParcelIdentity, TableFilters, project_rows
from mn_land.provenance import sha256_file
from mn_land.runs import (
    RunValidationError,
    ValidatedRun,
    read_artifact_bytes,
    read_artifact_json,
    read_json,
    safe_path,
    validate_run,
    workspace_path,
)
from mn_land.utils.validation import minimum_acres
from mn_land.worklists import Worklist, issue_rows, project_worklist, serialize

KINDS = {"delinquency_processed": "delinquency", "review": "review"}
MAX_SNAPSHOTS_PER_KIND = 200


@dataclass(frozen=True, slots=True)
class SnapshotKey:
    kind: str
    run_id: str

    def __post_init__(self) -> None:
        if self.kind not in KINDS or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", self.run_id):
            raise RunValidationError("Choose a supported saved-result identity")

    @property
    def token(self) -> str:
        return f"{self.kind}/{self.run_id}"


@dataclass(frozen=True, slots=True)
class SnapshotEntry:
    key: SnapshotKey
    state: str
    reason: str

    @property
    def eligible(self) -> bool:
        return self.state == "complete"

    @property
    def label(self) -> str:
        kind = "Review" if self.key.kind == "review" else "Join"
        return f"{kind} {self.key.run_id} — {self.state}"


@dataclass(frozen=True, slots=True)
class Catalog:
    entries: tuple[SnapshotEntry, ...]
    notices: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SnapshotOverview:
    key: SnapshotKey
    completion_sha256: str
    join_id: str
    parcel_id: str
    import_id: str
    validated_at: datetime
    created_at: datetime
    listing_publication_date: date | None
    listing_captured_at: datetime
    gis_captured_at: datetime
    report_verification_date: date | None
    minimum_acres: Decimal
    counts: tuple[tuple[str, int], ...]
    unknown_counts: tuple[tuple[str, int], ...]
    holds: tuple[str, ...]
    warnings: tuple[str, ...]
    manual_verification: str
    synthetic: bool
    listing_agency: str
    listing_dataset: str
    gis_layer: str


def _timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise RunValidationError("Source timestamps must have a timezone")
    return result


def _source(parent: ValidatedRun, label: str, kind: str) -> ValidatedRun:
    child = validate_run(parent.source(label), kind)
    reference = next(ref for ref in parent.completion["sources"] if ref["label"] == label)
    if child.completion_sha256 != reference["completion_sha256"]:
        raise RunValidationError("Pinned source changed between reads")
    return child


class ReviewService:
    """Fixed configured local roots, explicit identities, no latest fallback.

    The root is operator configuration, never a widget/query-param file path.
    Overview DTOs are immutable observations as of validated_at. Every load and
    revalidation checks the full graph; no pathname/mtime trust cache is used.
    """

    def __init__(self, processed_root: Path) -> None:
        self.root = workspace_path(processed_root).resolve()

    def _root(self, kind: str) -> Path:
        if kind not in KINDS:
            raise RunValidationError("Unsupported viewer result kind")
        county = self.root / "isanti"
        root = county / KINDS[kind]
        if county.is_symlink() or root.is_symlink():
            raise RunValidationError("Viewer result folders cannot be links")
        return root

    def catalog(self) -> Catalog:
        entries, notices = [], []
        for kind, folder in KINDS.items():
            try:
                root = self._root(kind)
                if not root.exists():
                    notices.append(f"No saved {folder} result folder exists yet.")
                    continue
                children = list(islice(root.iterdir(), MAX_SNAPSHOTS_PER_KIND + 1))
                if len(children) > MAX_SNAPSHOTS_PER_KIND:
                    notices.append(f"Too many {folder} entries; this folder was not listed.")
                    continue
                for path in sorted(children, key=lambda item: item.name):
                    if not path.is_dir() and not path.is_symlink():
                        continue
                    try:
                        key = SnapshotKey(kind, path.name)
                    except (RunValidationError, TypeError):
                        notices.append(
                            "An unsafe result name was omitted; operator review required."
                        )
                        continue
                    entries.append(self._entry(key))
            except (OSError, RunValidationError):
                notices.append(f"Cannot safely read the {folder} result folder.")
        return Catalog(tuple(entries), tuple(notices))

    def _path(self, key: SnapshotKey) -> Path:
        # Reconstruct the key so forged widget state never becomes a file path.
        key = SnapshotKey(key.kind, key.run_id)
        return safe_path(self._root(key.kind), key.run_id, directory=True)

    def _entry(self, key: SnapshotKey) -> SnapshotEntry:
        try:
            path = self._path(key)
            if (path / "failure.json").exists():
                return SnapshotEntry(
                    key, "failed", "Failed run; prepare a new run outside the viewer."
                )
            if not (path / "completion.json").exists():
                legacy = (path / "manifest.json").exists() or (path / "summary.json").exists()
                return SnapshotEntry(
                    key,
                    "legacy" if legacy else "incomplete",
                    "No version-2 completion evidence; never certified by this viewer.",
                )
            marker = read_json(safe_path(path, "completion.json"))
            if not isinstance(marker, dict):
                raise RunValidationError("Malformed completion")
            if marker.get("schema_version") != 2:
                return SnapshotEntry(key, "unsupported", "Unsupported completion version.")
            validate_run(path, key.kind)
            return SnapshotEntry(
                key, "complete", "Eligible at scan time; load revalidates all inputs."
            )
        except (RunValidationError, OSError):
            return SnapshotEntry(
                key,
                "invalid",
                "Missing, corrupt or unsafe evidence; no automatic fallback.",
            )

    def load(
        self,
        key: SnapshotKey,
        *,
        expected_completion: str | None = None,
    ) -> SnapshotOverview:
        """A new disk read always revalidates; failure never selects another run."""
        try:
            selected = validate_run(self._path(key), key.kind)
            if (
                expected_completion is not None
                and selected.completion_sha256 != expected_completion
            ):
                raise RunValidationError("Selected completion changed; select and load again")
            join = (
                _source(selected, "join", "delinquency_processed")
                if key.kind == "review"
                else selected
            )
            parcel = _source(join, "parcel", "parcel_raw")
            imported = _source(join, "delinquency", "delinquency_raw")
            # Use inventoried-byte readers rather than trusting a later mutable reread.
            manifest = read_artifact_json(join, "manifest.json")
            gis = read_artifact_json(parcel, "manifest.json")
            file = read_artifact_json(imported, "manifest.json")
            mapping = read_artifact_json(imported, "mapping.json")
            rows = read_artifact_json(join, "isanti_verified_delinquent_candidates.json")
            current = read_artifact_json(join, "isanti_overdue_current_year_parcels.json")
            summary = read_artifact_json(selected, "summary.json") if key.kind == "review" else {}
            holds = []
            if mapping.get("verification_hold_reason"):
                holds.append(str(mapping["verification_hold_reason"]))
            if manifest.get("unverified_matches"):
                holds.append("Unverified listing matches remain; do not treat them as candidates.")
            if any(
                entry["path"] == "inputs/official_report_comparison.json"
                for entry in selected.completion["artifacts"]
            ):
                comparison = read_artifact_json(selected, "inputs/official_report_comparison.json")
                if comparison.get("operational_status") == "HOLD_COUNTY_RECONCILIATION_REQUIRED":
                    holds.append("Official report comparison requires county reconciliation.")
            counts = [
                ("Listing source rows", manifest["delinquency_records_loaded"]),
                ("Prior-year source rows", manifest["prior_year_source_rows"]),
                ("Overdue current-year source rows", manifest["current_year_source_rows"]),
                ("Normalized GIS records", manifest["parcel_records_loaded"]),
                ("Quarantined GIS records", manifest["parcel_normalization_errors"]),
                ("Prior-year large parcels", len(rows)),
                ("Current-year overdue large parcels", len(current)),
                ("Unmatched listing rows", manifest["unmatched_delinquency_records"]),
                ("Ambiguous listing rows", manifest["ambiguous_records"]),
            ]
            if summary:
                for label, name in (
                    ("Outside PILT/exempt", "isanti_land_review.csv"),
                    ("Focused land review", "isanti_land_focused_review.csv"),
                    ("PILT/exempt review", "isanti_PILT_exempt_review.csv"),
                ):
                    counts.append((label, selected.completion["row_counts"][name]))
            unknown = tuple(
                (label, sum(row[field] is None for row in rows))
                for label, field in (
                    ("Combined tax/penalty balance", "total_taxes_and_penalties_due"),
                    ("Delinquent tax amount", "delinquent_tax_amount"),
                    ("Penalty amount", "penalty_amount"),
                    ("Improvement value", "improvement_value"),
                )
            )
            warnings = [
                "Saved listing evidence is not current payment status or an offer recommendation.",
                "Prior/current views can overlap; do not add them as unique parcels.",
                "Report verification date is unknown; no new county report is fetched here.",
            ]
            if _timestamp(gis["retrieved_at"]) != _timestamp(file["imported_at"]):
                warnings.append("GIS and listing captures are not simultaneous.")
            if not mapping.get("publication_date"):
                warnings.append("Listing publication date is unknown.")
            if summary.get("monetary_analysis_ready") is False:
                warnings.append(
                    "County accounting definitions remain unresolved; monetary analysis is not ready."
                )
            synthetic = selected.completion["provenance"]["code"].get("git", {}).get(
                "status"
            ) == "synthetic_test_fixture" or any(
                word in mapping["dataset"].lower() for word in ("synthetic", "test fixture")
            )
            if sha256_file(selected.path / "completion.json") != selected.completion_sha256:
                raise RunValidationError("Selected completion changed during load")
            return SnapshotOverview(
                key=key,
                completion_sha256=selected.completion_sha256,
                join_id=join.path.name,
                parcel_id=parcel.path.name,
                import_id=imported.path.name,
                validated_at=datetime.now(UTC),
                created_at=_timestamp(selected.completion["created_at"]),
                listing_publication_date=(
                    date.fromisoformat(mapping["publication_date"])
                    if mapping.get("publication_date")
                    else None
                ),
                listing_captured_at=_timestamp(file["imported_at"]),
                gis_captured_at=_timestamp(gis["retrieved_at"]),
                report_verification_date=None,
                minimum_acres=minimum_acres(manifest["minimum_acres"]),
                counts=tuple(counts),
                unknown_counts=unknown,
                holds=tuple(holds),
                warnings=tuple(warnings),
                manual_verification=str(summary.get("manual_verification_status", "unknown")),
                synthetic=synthetic,
                listing_agency=mapping["source_agency"],
                listing_dataset=mapping["dataset"],
                gis_layer=f"{gis['service_url']}/{gis['layer_id']}",
            )
        except (RunValidationError, OSError, ValueError, KeyError, TypeError) as exc:
            raise RunValidationError(
                "Selected evidence is missing, changed, incompatible or invalid. "
                "Clear the loaded result, inspect local runs and explicitly load a valid selection; "
                "nothing was refreshed, repaired or substituted."
            ) from exc

    def revalidate(self, overview: SnapshotOverview) -> SnapshotOverview:
        """Required gate for any future disk-backed detail read or export."""
        return self.load(overview.key, expected_completion=overview.completion_sha256)

    def load_parcels(
        self,
        key: SnapshotKey,
        *,
        expected_completion: str | None = None,
    ) -> ParcelDataset:
        """Explicit disk-backed load; later filtering only uses its immutable DTOs."""
        overview = self.load(key, expected_completion=expected_completion)
        try:
            selected = validate_run(self._path(key), key.kind)
            if selected.completion_sha256 != overview.completion_sha256:
                raise RunValidationError("Selected evidence changed between reads")
            join = (
                _source(selected, "join", "delinquency_processed")
                if key.kind == "review"
                else selected
            )
            prior = read_artifact_json(join, "isanti_verified_delinquent_candidates.json")
            current = read_artifact_json(join, "isanti_overdue_current_year_parcels.json")
            floor = overview.minimum_acres
            if key.kind == "review":
                summary = read_artifact_json(selected, "summary.json")
                floor = max(floor, minimum_acres(summary["minimum_acres"]))
            rows = project_rows(prior, current, floor) if not overview.holds else ()
            if sha256_file(selected.path / "completion.json") != selected.completion_sha256:
                raise RunValidationError("Selected evidence changed during table load")
            return ParcelDataset(overview, floor, rows)
        except (RunValidationError, OSError, ValueError, KeyError, TypeError) as exc:
            raise RunValidationError(
                "Parcel table evidence is missing, changed or invalid. Clear and load again; "
                "nothing was refreshed, repaired or substituted."
            ) from exc

    def load_details(self, dataset: ParcelDataset, identity: ParcelIdentity) -> ParcelDetails:
        """Revalidate on an explicit detail action; never follow input paths/URLs."""
        try:
            if (
                identity.county != "Isanti"
                or identity.snapshot_token != dataset.overview.key.token
                or identity.completion_sha256 != dataset.overview.completion_sha256
                or not any(row.parcel_id == identity.parcel_id for row in dataset.rows)
            ):
                raise RunValidationError("Parcel is not in the loaded candidate observation")
            fresh = self.load_parcels(
                dataset.overview.key, expected_completion=identity.completion_sha256
            )
            row = next((row for row in fresh.rows if row.parcel_id == identity.parcel_id), None)
            if row is None:
                raise RunValidationError("Parcel is not eligible after revalidation")
            selected = validate_run(self._path(fresh.overview.key), fresh.overview.key.kind)
            if selected.completion_sha256 != identity.completion_sha256:
                raise RunValidationError("Selected evidence changed")
            join = (
                _source(selected, "join", "delinquency_processed")
                if fresh.overview.key.kind == "review"
                else selected
            )
            imported = _source(join, "delinquency", "delinquency_raw")
            gis = _source(join, "parcel", "parcel_raw")
            file = read_artifact_json(imported, "manifest.json")
            mapping = read_artifact_json(imported, "mapping.json")
            limits = InputLimits(**file["input_limits"])
            body = read_artifact_bytes(
                imported, file["source_file"], max_bytes=limits.max_file_bytes
            )
            _, source_rows = read_table_bytes(body, Path(file["source_file"]).suffix, limits)
            prior = read_artifact_json(join, "isanti_verified_delinquent_candidates.json")
            current = read_artifact_json(join, "isanti_overdue_current_year_parcels.json")
            gis_manifest = read_artifact_json(gis, "manifest.json")
            reference = mapping.get("year_semantics_reference")
            year_evidence = None
            if reference is not None:
                entry = next(
                    item
                    for item in imported.completion["artifacts"]
                    if item["path"] == f"supporting/{reference}"
                )
                year_evidence = (Path(reference).name, entry["sha256"])
            comparison = None
            if any(
                item["path"] == "inputs/official_report_comparison.json"
                for item in selected.completion["artifacts"]
            ):
                comparison = read_artifact_json(selected, "inputs/official_report_comparison.json")
            context = (
                ("Selected completion SHA-256", selected.completion_sha256),
                ("Join run", join.path.name),
                ("Listing import run", imported.path.name),
                ("GIS run", gis.path.name),
                ("Listing agency", fresh.overview.listing_agency),
                ("Listing dataset", fresh.overview.listing_dataset),
                ("Listing publication date", mapping.get("publication_date")),
                ("Listing captured", fresh.overview.listing_captured_at.isoformat()),
                ("GIS captured", fresh.overview.gis_captured_at.isoformat()),
                ("Listing bytes SHA-256", file["source_sha256"]),
                ("Reviewed mapping SHA-256", file["mapping_sha256"]),
                ("Report verification date", None),
            )
            detail = project_details(
                identity,
                row,
                prior,
                current,
                source_rows,
                mapping,
                context,
                f"{gis_manifest['service_url']}/{gis_manifest['layer_id']}",
                checked_at=datetime.now(UTC),
                synthetic=fresh.overview.synthetic,
                year_evidence=year_evidence,
                comparison=comparison,
            )
            final = validate_run(selected.path, selected.completion["kind"])
            if final.completion_sha256 != selected.completion_sha256:
                raise RunValidationError("Evidence changed during detail load")
            return detail
        except (RunValidationError, OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
            raise RunValidationError(
                "Parcel evidence is missing, changed, held or incompatible. Reload and explicitly load a valid snapshot; "
                "nothing was fetched, repaired or substituted."
            ) from exc

    def prepare_export(
        self,
        dataset: ParcelDataset,
        filters: TableFilters,
        *,
        scope: str = "filtered",
        identity: ParcelIdentity | None = None,
    ) -> Worklist:
        """Fresh, immutable preview from pinned saved evidence; no file outputs."""
        try:
            fresh = self.load_parcels(
                dataset.overview.key,
                expected_completion=dataset.overview.completion_sha256,
            )
            selected = validate_run(self._path(fresh.overview.key), fresh.overview.key.kind)
            if selected.completion_sha256 != fresh.overview.completion_sha256:
                raise RunValidationError("Selected evidence changed")
            join = (
                _source(selected, "join", "delinquency_processed")
                if fresh.overview.key.kind == "review"
                else selected
            )
            imported = _source(join, "delinquency", "delinquency_raw")
            gis = _source(join, "parcel", "parcel_raw")
            prior = read_artifact_json(join, "isanti_verified_delinquent_candidates.json")
            current = read_artifact_json(join, "isanti_overdue_current_year_parcels.json")
            file = read_artifact_json(imported, "manifest.json")
            mapping = read_artifact_json(imported, "mapping.json")
            accounting = read_artifact_json(join, "accounting.json")
            diagnostics = read_artifact_json(join, "normalization_diagnostics.json")
            issues = []
            for location, name, kind, fields in ISSUE_TABLES:
                if location == "review" and fresh.overview.key.kind != "review":
                    continue
                source = selected if location == "review" else join
                captured = read_artifact_bytes(source, name, max_bytes=32 * 1024 * 1024)
                for ordinal, values in enumerate(
                    issue_rows(captured, fields, source.completion["row_counts"][name]), 1
                ):
                    issues.append(
                        {
                            "kind": kind,
                            "artifact": name,
                            "record_ordinal": ordinal,
                            "fields": values,
                        }
                    )
            for ordinal, reference in enumerate(accounting["unverified_period"], 1):
                issues.append(
                    {
                        "kind": "unverified_period",
                        "artifact": "accounting.json",
                        "record_ordinal": ordinal,
                        "fields": {"source_row_number": reference},
                    }
                )
            for ordinal, diagnostic in enumerate(diagnostics, 1):
                issues.append(
                    {
                        "kind": "GIS_normalization_diagnostic",
                        "artifact": "normalization_diagnostics.json",
                        "record_ordinal": ordinal,
                        "fields": {
                            field: diagnostic.get(field)
                            for field in (
                                "feature_number",
                                "source_record_id",
                                "severity",
                                "field",
                            )
                        },
                    }
                )
            issues.append(
                {
                    "kind": "source_accounting",
                    "artifact": "accounting.json",
                    "record_ordinal": 1,
                    "fields": {
                        name: len(accounting[name])
                        for name in (
                            "matched",
                            "unmatched",
                            "ambiguous",
                            "duplicate_review",
                            "prior_year",
                            "current_year",
                            "unverified_period",
                        )
                    },
                }
            )
            # Full diagnostic reasons may contain local paths/source values. Keep
            # allowlisted diagnostic identities above and the overview count here.
            issues.append(
                {
                    "kind": "GIS_quarantine_count",
                    "artifact": "normalization_diagnostics.json",
                    "record_ordinal": 1,
                    "fields": {
                        "quarantined_GIS_records": dict(fresh.overview.counts)[
                            "Quarantined GIS records"
                        ]
                    },
                }
            )
            overview = fresh.overview
            context = {
                "county": "Isanti",
                "snapshot": overview.key.token,
                "completion_sha256": overview.completion_sha256,
                "join_run": overview.join_id,
                "join_completion_sha256": join.completion_sha256,
                "GIS_run": overview.parcel_id,
                "GIS_completion_sha256": gis.completion_sha256,
                "listing_import_run": overview.import_id,
                "listing_completion_sha256": imported.completion_sha256,
                "listing_bytes_sha256": file["source_sha256"],
                "mapping_sha256": file["mapping_sha256"],
                "listing_agency": overview.listing_agency,
                "listing_dataset": overview.listing_dataset,
                "listing_publication_date": mapping.get("publication_date"),
                "listing_captured_at": overview.listing_captured_at.isoformat(),
                "GIS_captured_at": overview.gis_captured_at.isoformat(),
                "GIS_layer_reference": public_link(overview.gis_layer, ""),
                "report_verification_date": None,
                "manual_verification": overview.manual_verification,
                "tax_year_convention": mapping.get("tax_year_convention"),
                "synthetic": overview.synthetic,
            }
            worklist = project_worklist(
                fresh,
                filters,
                prior,
                current,
                issues,
                context,
                checked_at=datetime.now(UTC),
                scope=scope,
                identity=identity,
            )
            # Reuse ML-204's exact row/year/mapping/money evidence checks once per
            # exported parcel. Parse captured input once, not one disk load per ID.
            limits = InputLimits(**file["input_limits"])
            captured = read_artifact_bytes(
                imported, file["source_file"], max_bytes=limits.max_file_bytes
            )
            _, source_rows = read_table_bytes(captured, Path(file["source_file"]).suffix, limits)
            indexed = {row.parcel_id: row for row in fresh.rows}
            for candidate in worklist.payload()["candidates"]:
                parcel_id = candidate["parcel_id"]
                project_details(
                    ParcelIdentity(
                        "Isanti", overview.key.token, overview.completion_sha256, parcel_id
                    ),
                    indexed[parcel_id],
                    prior,
                    current,
                    source_rows,
                    mapping,
                    (),
                    "",
                    checked_at=worklist.checked_at,
                    synthetic=True,
                )
            final = validate_run(selected.path, selected.completion["kind"])
            if final.completion_sha256 != selected.completion_sha256:
                raise RunValidationError("Evidence changed during export preview")
            return worklist
        except (RunValidationError, OSError, ValueError, KeyError, TypeError, csv.Error) as exc:
            raise RunValidationError(
                "Worklist evidence or selection is missing, changed, held or incompatible. "
                "Reload and explicitly preview again; no file was exported, fetched, repaired or substituted."
            ) from exc

    def download_export(self, preview: Worklist, format: str) -> bytes:
        """Revalidate at each actual download, not just when rendering a button."""
        try:
            if format not in {"csv", "json"}:
                raise ValueError("Unsupported worklist format")
            fresh = self.prepare_export(
                preview.dataset,
                preview.filters,
                scope=preview.scope,
                identity=preview.identity,
            )
            if fresh.fingerprint != preview.fingerprint:
                raise RunValidationError("Preview changed; preview again")
            return serialize(fresh, format)
        except (RunValidationError, ValueError, TypeError) as exc:
            raise RunValidationError(
                "Download refused: evidence or preview changed or output exceeded its budget. "
                "Reload and preview again. No stale/partial worklist was supplied."
            ) from exc
