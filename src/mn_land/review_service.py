"""Read-only saved-result boundary. No Streamlit, acquisition or replay imports.

Only overview DTOs are exposed in ML-202. Parcel views/details/exports are later
stories, not raw dictionaries passed through to the browser.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from itertools import islice
from pathlib import Path

from mn_land.provenance import sha256_file
from mn_land.runs import (
    RunValidationError,
    ValidatedRun,
    read_artifact_json,
    read_json,
    safe_path,
    validate_run,
    workspace_path,
)
from mn_land.utils.validation import minimum_acres

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
                        notices.append("An unsafe result name was omitted; operator review required.")
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
                return SnapshotEntry(key, "failed", "Failed run; prepare a new run outside the viewer.")
            if not (path / "completion.json").exists():
                legacy = (path / "manifest.json").exists() or (path / "summary.json").exists()
                return SnapshotEntry(
                    key, "legacy" if legacy else "incomplete",
                    "No version-2 completion evidence; never certified by this viewer.",
                )
            marker = read_json(safe_path(path, "completion.json"))
            if not isinstance(marker, dict):
                raise RunValidationError("Malformed completion")
            if marker.get("schema_version") != 2:
                return SnapshotEntry(key, "unsupported", "Unsupported completion version.")
            validate_run(path, key.kind)
            return SnapshotEntry(key, "complete", "Eligible at scan time; load revalidates all inputs.")
        except (RunValidationError, OSError):
            return SnapshotEntry(
                key, "invalid", "Missing, corrupt or unsafe evidence; no automatic fallback.",
            )

    def load(
        self, key: SnapshotKey, *, expected_completion: str | None = None,
    ) -> SnapshotOverview:
        """A new disk read always revalidates; failure never selects another run."""
        try:
            selected = validate_run(self._path(key), key.kind)
            if expected_completion is not None and selected.completion_sha256 != expected_completion:
                raise RunValidationError("Selected completion changed; select and load again")
            join = (
                _source(selected, "join", "delinquency_processed")
                if key.kind == "review" else selected
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
                warnings.append("County accounting definitions remain unresolved; monetary analysis is not ready.")
            synthetic = (
                selected.completion["provenance"]["code"].get("git", {}).get("status")
                == "synthetic_test_fixture"
                or any(word in mapping["dataset"].lower() for word in ("synthetic", "test fixture"))
            )
            if sha256_file(selected.path / "completion.json") != selected.completion_sha256:
                raise RunValidationError("Selected completion changed during load")
            return SnapshotOverview(
                key=key, completion_sha256=selected.completion_sha256,
                join_id=join.path.name, parcel_id=parcel.path.name, import_id=imported.path.name,
                validated_at=datetime.now(UTC), created_at=_timestamp(selected.completion["created_at"]),
                listing_publication_date=(
                    date.fromisoformat(mapping["publication_date"])
                    if mapping.get("publication_date") else None
                ),
                listing_captured_at=_timestamp(file["imported_at"]),
                gis_captured_at=_timestamp(gis["retrieved_at"]), report_verification_date=None,
                minimum_acres=minimum_acres(manifest["minimum_acres"]),
                counts=tuple(counts), unknown_counts=unknown, holds=tuple(holds), warnings=tuple(warnings),
                manual_verification=str(summary.get("manual_verification_status", "unknown")),
                synthetic=synthetic, listing_agency=mapping["source_agency"],
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
