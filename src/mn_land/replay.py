"""Offline selection evidence; never a source-currentness or payment assertion."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from mn_land.provenance import sha256_file
from mn_land.runs import (
    JOIN_OUTPUTS,
    RunValidationError,
    ValidatedRun,
    read_json,
    safe_path,
    validate_run,
    workspace_path,
)


def selected_snapshot(path: Path, kind: str) -> ValidatedRun:
    if not (workspace_path(path) / "completion.json").is_file():
        raise RunValidationError(
            "Selected snapshot has no version-2 completion record; legacy/incomplete inputs "
            "remain unverified and cannot be certified by replay"
        )
    return validate_run(path, kind)


def normalized_digest(records: list[Any]) -> str:
    def encode(value: Any) -> str:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        raise TypeError(f"Unsupported normalized value: {type(value).__name__}")

    # Same canonical JSON array, without allocating a second full dataclass list.
    digest = hashlib.sha256(b"[")
    for index, record in enumerate(records):
        if index:
            digest.update(b",")
        digest.update(
            json.dumps(
                asdict(record),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
                default=encode,
            ).encode("utf-8")
        )
    digest.update(b"]")
    return digest.hexdigest()


def check_destination(root: Path, *sources: Path) -> None:
    """Never create a replay beneath, and thereby mutate, an immutable input."""
    destination = workspace_path(root).resolve()
    if any(
        destination.is_relative_to(workspace_path(source).resolve(strict=True))
        for source in sources
    ) or any(
        (ancestor / marker).exists()
        for ancestor in (destination, *destination.parents)
        for marker in (
            "reservation.json",
            "completion.json",
            "completion.pending.json",
            "failure.json",
        )
    ):
        raise RunValidationError(
            "Output directory cannot be inside a selected snapshot or another reserved/completed run"
        )


def input_dates(parcel: dict, imported: dict, publication: str | None) -> dict:
    parcel_at = datetime.fromisoformat(parcel["retrieved_at"])
    imported_at = datetime.fromisoformat(imported["imported_at"])
    if parcel_at.tzinfo is None or imported_at.tzinfo is None:
        raise RunValidationError("Selected source timestamps require timezones")
    delta = parcel_at.astimezone(UTC) - imported_at.astimezone(UTC)
    microseconds = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
    publication_date = date.fromisoformat(publication) if publication is not None else None
    warnings = []
    if microseconds:
        warnings.append("Parcel acquisition and delinquency capture are not simultaneous")
    if publication_date is None:
        warnings.append("Delinquency publication date is unknown")
    elif publication_date > imported_at.astimezone(UTC).date():
        warnings.append(
            "Recorded publication date postdates UTC import capture date; verify source dates"
        )
    return {
        "parcel_retrieved_at": parcel_at.isoformat(),
        "delinquency_imported_at": imported_at.isoformat(),
        "delinquency_publication_date": publication,
        "parcel_minus_import_seconds": str(Decimal(microseconds) / 1_000_000),
        "parcel_minus_publication_days": (
            (parcel_at.astimezone(UTC).date() - publication_date).days
            if publication_date is not None
            else None
        ),
        "warnings": warnings,
        "limitation": "Different source dates are disclosed, not synchronized; current payment status unknown",
    }


def validate_replay_evidence(path: Path, completion: dict, manifest: dict) -> None:
    """Reconcile new evidence; older complete runs keep unknown historical hashes."""
    if "selection" not in manifest and "reproducibility" not in manifest:
        return
    evidence, selection = manifest["reproducibility"], manifest["selection"]
    if (
        not isinstance(evidence, dict)
        or not isinstance(selection, dict)
        or type(evidence.get("schema_version")) is not int
        or evidence["schema_version"] != 1
    ):
        raise RunValidationError("Unsupported replay evidence schema")
    for field in ("normalized_parcels_sha256", "normalized_delinquency_sha256"):
        if not isinstance(evidence.get(field), str) or not re.fullmatch(
            r"[0-9a-f]{64}", evidence[field]
        ):
            raise RunValidationError("Missing normalized-content fingerprint")
    if evidence["exports_sha256"] != {
        name: sha256_file(path / name) for name in JOIN_OUTPUTS
    } or evidence["candidate_ids"] != sorted(
        row["parcel_id"] for row in read_json(path / "isanti_verified_delinquent_candidates.json")
    ):
        raise RunValidationError("Replay export/identity evidence does not reconcile")
    sources = {source["label"]: source for source in completion["sources"]}
    for label, prefix in (("parcel", "parcel"), ("delinquency", "import")):
        if (
            selection[f"{prefix}_run_id"] != sources[label]["run_id"]
            or selection[f"{prefix}_completion_sha256"] != sources[label]["completion_sha256"]
        ):
            raise RunValidationError("Selected source identities differ from pinned inputs")
    parcel = safe_path(path, sources["parcel"]["path"], directory=True)
    imported = safe_path(path, sources["delinquency"]["path"], directory=True)
    if selection["dates"] != input_dates(
        read_json(parcel / "manifest.json"),
        read_json(imported / "manifest.json"),
        read_json(imported / "mapping.json").get("publication_date"),
    ):
        raise RunValidationError("Selected source-date evidence does not reconcile")
    if selection["mode"] not in {"recorded_join", "explicit_pair", "latest_eligible_parcel"}:
        raise RunValidationError("Unknown snapshot selection mode")
    allowed = {
        "identical_exports_and_recorded_normalization",
        "identical_exports_historical_normalization_unknown",
        "threshold_changed_exports_not_compared",
    }
    if selection["mode"] == "recorded_join":
        reference = selection["replayed_from"]
        if (
            not isinstance(reference, dict)
            or not isinstance(reference.get("run_id"), str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", reference["run_id"])
            or not isinstance(reference.get("completion_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", reference["completion_sha256"])
            or selection["comparison"] not in allowed
        ):
            raise RunValidationError("Invalid replay reference/comparison evidence")
    elif selection["replayed_from"] is not None or selection["comparison"] != "not_requested":
        raise RunValidationError("Unexpected comparison without a selected join")
