"""Versioned completion records shared by producers, readers and status.

The exclusively reserved directory is staging until completion.json is installed.
No group of flat compatibility files is published or overwritten.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Self
from uuid import uuid4

from mn_land.provenance import build_provenance, sha256_file

PARCEL_OUTPUTS = (
    "isanti_candidates.csv",
    "isanti_candidates.json",
    "isanti_verification_sample.csv",
    "isanti_tax_semantics_review_sample.csv",
)
JOIN_OUTPUTS = (
    "isanti_verified_delinquent_candidates.csv",
    "isanti_verified_delinquent_candidates.json",
    "isanti_verified_candidate_review_sample.csv",
    "isanti_unmatched_delinquency_records.csv",
    "isanti_duplicate_delinquency_records.csv",
    "isanti_overdue_current_year_parcels.csv",
    "isanti_overdue_current_year_parcels.json",
    "isanti_unverified_large_parcels.csv",
    "isanti_ambiguous_delinquency_matches.csv",
)
REVIEW_OUTPUTS = (
    "isanti_candidate_review.csv",
    "isanti_land_review.csv",
    "isanti_PILT_exempt_review.csv",
    "isanti_land_focused_review.csv",
    "isanti_duplicate_group_review.csv",
    "isanti_unmatched_parcel_review.csv",
    "isanti_county_verification_worklist.csv",
)
DEPENDENCIES = {
    "parcel_raw": {},
    "delinquency_raw": {},
    "parcel_processed": {"parcel": "parcel_raw"},
    "delinquency_processed": {"parcel": "parcel_raw", "delinquency": "delinquency_raw"},
    "review": {"join": "delinquency_processed"},
}
CONTROL_FILES = {"completion.json", "completion.pending.json", "failure.json"}
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_JSON_BYTES = 128 * 1024 * 1024


def workspace_path(path: Path) -> Path:
    """Support deeply pinned evidence on Windows without changing stored relative paths."""
    absolute = os.path.abspath(path)
    if os.name == "nt" and not absolute.startswith("\\\\?\\"):
        absolute = (
            ("\\\\?\\UNC\\" + absolute[2:]) if absolute.startswith("\\\\") else "\\\\?\\" + absolute
        )
    return Path(absolute)


class RunValidationError(ValueError):
    """An input is incomplete, legacy, corrupt or unsafe to consume."""


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for name, value in pairs:
        if name in result:
            raise RunValidationError("Duplicate JSON member")
        result[name] = value
    return result


def _read_bytes(path: Path, limit: int) -> bytes:
    with path.open("rb") as handle:
        body = handle.read(limit + 1)
    if len(body) > limit:
        raise RunValidationError("JSON evidence exceeds read budget")
    return body


def read_json(path: Path) -> Any:
    try:
        body = _read_bytes(path, MAX_JSON_BYTES)
        return json.loads(body, object_pairs_hook=_unique)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise RunValidationError(f"Cannot read run evidence: {path.name}") from exc


def write_json(path: Path, payload: Any) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def _relative_parts(name: str) -> list[str]:
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise RunValidationError("Unsafe manifest path")
    parts = name.split("/")
    if PurePosixPath(name).is_absolute() or any(
        not part
        or part in {".", ".."}
        or part.endswith((".", " "))
        or re.search(r'[<>?*"\x00-\x1f|]', part)
        or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)
        for part in parts
    ):
        raise RunValidationError("Unsafe manifest path")
    return parts


def safe_path(root: Path, name: str, *, directory: bool = False) -> Path:
    root = workspace_path(root)
    parts = _relative_parts(name)
    try:
        base = root.resolve(strict=True)
        candidate = root
        for part in parts:
            candidate /= part
            if candidate.is_symlink():
                raise RunValidationError("Manifest paths cannot traverse symlinks")
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(base) or (
            not resolved.is_dir() if directory else not resolved.is_file()
        ):
            raise RunValidationError("Manifest path escapes run or is not the required file type")
        return candidate
    except (OSError, RuntimeError) as exc:
        raise RunValidationError("Missing or inaccessible manifest artifact") from exc


def _integer(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise RunValidationError("Run count must be a nonnegative integer")
    return value


def artifact_row_count(path: Path) -> int:
    if path.suffix == ".csv":
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            header = next(reader, None)
            if not header:
                raise RunValidationError("Missing CSV header")
            rows = 0
            for row in reader:
                if len(row) != len(header):
                    raise RunValidationError("Malformed output CSV width")
                rows += 1
            return rows
    payload = read_json(path)
    if not isinstance(payload, list):
        raise RunValidationError("Expected output JSON array")
    return len(payload)


def _files(path: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    base = path.resolve(strict=True)
    visited = {base}
    pending = [path]
    while pending:
        for item in pending.pop().iterdir():
            if item.is_symlink():
                raise RunValidationError("Run artifacts cannot contain symlinks")
            if item.is_dir():
                resolved = item.resolve(strict=True)
                if not resolved.is_relative_to(base) or resolved in visited:
                    raise RunValidationError("Run directory escapes or cycles through evidence")
                visited.add(resolved)
                pending.append(item)
            elif item.is_file():
                name = item.relative_to(path).as_posix()
                if name not in CONTROL_FILES:
                    result[name] = item
            if len(result) + len(visited) > 20000:
                raise RunValidationError("Run inventory exceeds traversal budget")
    return result


@dataclass(frozen=True)
class ValidatedRun:
    path: Path
    completion: dict[str, Any]
    manifest: dict[str, Any]
    completion_sha256: str

    def source(self, label: str) -> Path:
        reference = next(ref for ref in self.completion["sources"] if ref["label"] == label)
        return safe_path(self.path, reference["path"], directory=True)


def validate_run(path: Path, kind: str, *, pending: bool = False, depth: int = 0) -> ValidatedRun:
    """Validate relative inventory, bytes, accounting and the pinned source graph.

    This is integrity/completion validation, not a signature or a county authority.
    Legacy inputs never enter this path via an automatic fallback.
    """
    path = workspace_path(path)
    try:
        if (
            kind not in DEPENDENCIES
            or depth > 3
            or path.is_symlink()
            or path.resolve(strict=True) != path.parent.resolve(strict=True) / path.name
            or (path / "failure.json").exists()
        ):
            raise RunValidationError("Unknown kind, failed run, symlink or invalid source graph")
        completion_path = safe_path(
            path, "completion.pending.json" if pending else "completion.json"
        )
        completion_body = _read_bytes(completion_path, MAX_MANIFEST_BYTES)
        completion_digest = hashlib.sha256(completion_body).hexdigest()
        completion = json.loads(completion_body, object_pairs_hook=_unique)
        json.dumps(completion, allow_nan=False, ensure_ascii=False).encode("utf-8")
        if (
            not isinstance(completion, dict)
            or type(completion.get("schema_version")) is not int
            or completion["schema_version"] != 2
        ):
            raise RunValidationError("Legacy/unverified run: version 2 completion record required")
        if (
            completion.get("kind") != kind
            or completion.get("county") != "Isanti"
            or completion.get("status") != "complete"
            or completion.get("run_id") != path.name
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", path.name)
        ):
            raise RunValidationError("Run identity/kind/county/status mismatch")
        stage = "raw_complete" if kind.endswith("_raw") else "processed_complete"
        if completion.get("stage") != stage:
            raise RunValidationError("Wrong completion stage")
        provenance = completion.get("provenance")
        if (
            not isinstance(provenance, dict)
            or type(provenance.get("schema_version")) is not int
            or provenance["schema_version"] != 1
        ):
            raise RunValidationError("Missing execution provenance")
        config = provenance["configuration"]
        encoded = json.dumps(
            config, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        if (
            not isinstance(config, dict)
            or config.get("kind") != kind
            or config.get("completion_protocol") != 2
            or hashlib.sha256(encoded).hexdigest() != provenance["configuration_sha256"]
            or not isinstance(provenance.get("code"), dict)
            or not isinstance(provenance.get("runtime"), dict)
        ):
            raise RunValidationError("Invalid execution/configuration identity")
        created = datetime.fromisoformat(completion["created_at"])
        if created.tzinfo is None:
            raise RunValidationError("Run time must have a timezone")
        entries = completion.get("artifacts")
        if not isinstance(entries, list) or not entries or len(entries) > 10000:
            raise RunValidationError("Missing or excessive artifact inventory")
        names = set()
        # Check containment/link safety once per actual tree, before opening any
        # listed artifact. Hash every file; do not cache results across reads.
        actual_files = _files(path)
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                raise RunValidationError("Malformed artifact entry")
            name, digest = entry["path"], entry["sha256"]
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise RunValidationError("Invalid artifact hash")
            if name.casefold() in names or name in CONTROL_FILES:
                raise RunValidationError("Duplicate or self-referencing artifact")
            names.add(name.casefold())
            _relative_parts(name)
            artifact = actual_files.get(name)
            if artifact is None:
                raise RunValidationError("Missing listed artifact")
            if (
                artifact.stat().st_size != _integer(entry["bytes"])
                or sha256_file(artifact) != digest
            ):
                raise RunValidationError(f"Artifact size/hash mismatch: {name}")
        if {entry["path"] for entry in entries} != set(actual_files):
            raise RunValidationError("Run inventory differs from actual artifacts")
        reservation = read_json(safe_path(path, "reservation.json"))
        if (
            not isinstance(reservation, dict)
            or reservation.get("kind") != kind
            or reservation.get("county") != "Isanti"
            or reservation.get("run_id") != completion["run_id"]
        ):
            raise RunValidationError("Reservation identity differs from completion")
        sources = completion.get("sources")
        if not isinstance(sources, list) or len(sources) != len(DEPENDENCIES[kind]):
            raise RunValidationError("Invalid source inventory")
        labels = set()
        for ref in sources:
            label = ref["label"]
            if label in labels or DEPENDENCIES[kind].get(label) != ref["kind"]:
                raise RunValidationError("Wrong or repeated source kind")
            labels.add(label)
            source_path = safe_path(path, ref["path"], directory=True)
            if ref["path"] != f"inputs/{label}/{ref['run_id']}":
                raise RunValidationError("Source must be a pinned contained snapshot")
            if sha256_file(source_path / "completion.json") != ref["completion_sha256"]:
                raise RunValidationError("Source completion hash mismatch")
            validate_run(source_path, ref["kind"], depth=depth + 1)
        manifest_name = "summary.json" if kind == "review" else "manifest.json"
        manifest = read_json(safe_path(path, manifest_name))
        if not isinstance(manifest, dict):
            raise RunValidationError("Operation manifest must be an object")
        from mn_land.run_checks import validate_content

        validate_content(path, completion, manifest)
        if sha256_file(completion_path) != completion_digest:
            raise RunValidationError("Completion changed during validation")
        return ValidatedRun(path, completion, manifest, completion_digest)
    except (OSError, KeyError, TypeError, ValueError, RuntimeError, csv.Error) as exc:
        if isinstance(exc, RunValidationError):
            raise
        raise RunValidationError(f"Invalid {kind} run: {path.name}") from exc


def select_latest(
    root: Path, kind: str, *, diagnostics: list[dict[str, Any]] | None = None
) -> ValidatedRun:
    root = workspace_path(root)
    diagnostics = diagnostics if diagnostics is not None else []
    pointer = root / "latest.json"
    if pointer.is_file():
        try:
            payload = read_json(safe_path(root, "latest.json"))
            run = validate_run(safe_path(root, payload["run_id"], directory=True), kind)
            if payload.get("kind") != kind or payload.get("completion_sha256") != sha256_file(
                run.path / "completion.json"
            ):
                raise RunValidationError("Latest pointer hash/kind mismatch")
            return run
        except (RunValidationError, KeyError, TypeError):
            diagnostics.append(
                {
                    "severity": "warning",
                    "reason": "invalid/stale latest pointer; checking prior complete runs",
                }
            )
    candidates = []
    for path in root.iterdir() if root.is_dir() else ():
        if not path.is_dir() or path.name.startswith("."):
            continue
        try:
            candidate = validate_run(safe_path(root, path.name, directory=True), kind)
            candidates.append(candidate)
        except RunValidationError:
            diagnostics.append(
                {
                    "snapshot": str(path),
                    "severity": "warning",
                    "reason": "ineligible: incomplete, invalid or legacy/unverified",
                }
            )
    if not candidates:
        raise RunValidationError(
            f"No eligible complete {kind} run; legacy snapshots are not automatically certified"
        )
    return max(
        candidates,
        key=lambda run: (datetime.fromisoformat(run.completion["created_at"]), run.path.name),
    )


def new_run_id() -> str:
    return uuid4().hex


class RunWorkspace:
    def __init__(self, root: Path, kind: str, *, run_id: str | None = None) -> None:
        self.kind = kind
        self.path = workspace_path(root / (run_id or new_run_id()))
        self.stage = "reserve"
        self.counts: dict[str, int] = {}
        self.sources: list[dict[str, str]] = []

    def __enter__(self) -> Self:
        if self.kind not in DEPENDENCIES or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,100}", self.path.name
        ):
            raise RunValidationError("Invalid run reservation")
        self.path.mkdir(parents=True, exist_ok=False)
        write_json(
            self.path / "reservation.json",
            {
                "kind": self.kind,
                "county": "Isanti",
                "run_id": self.path.name,
                "created_at": datetime.now(UTC).isoformat(),
            },
        )
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if exc is not None:
            try:
                write_json(
                    self.path / "failure.json",
                    {
                        "stage": self.stage,
                        "error_class": type(exc).__name__,
                        "reason": str(exc)[:2000],
                        "counts": self.counts,
                        "time": datetime.now(UTC).isoformat(),
                        "complete": False,
                    },
                )
            except (OSError, ValueError):
                # Disk full/hard interruption can prevent diagnostics. No marker
                # or an explicit failure still excludes the run in all readers.
                pass

    def pin(self, source: Path, label: str) -> Path:
        kind = DEPENDENCIES[self.kind][label]
        validated = validate_run(source, kind)
        source = validated.path
        target = self.path / "inputs" / label / source.name
        target.mkdir(parents=True, exist_ok=False)
        # Copy declared exact bytes, then enforce the source's captured hashes.
        for entry in validated.completion["artifacts"]:
            origin = safe_path(source, entry["path"])
            destination = target / entry["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            remaining = entry["bytes"]
            with origin.open("rb") as src, destination.open("xb") as dst:
                while remaining:
                    chunk = src.read(min(65536, remaining))
                    if not chunk:
                        raise RunValidationError("Source shortened while pinning")
                    dst.write(chunk)
                    remaining -= len(chunk)
                if src.read(1):
                    raise RunValidationError("Source grew while pinning")
            if sha256_file(destination) != entry["sha256"]:
                raise RunValidationError("Source artifact changed while pinning")
        with (target / "completion.json").open("xb") as handle:
            handle.write(_read_bytes(source / "completion.json", MAX_MANIFEST_BYTES))
        if sha256_file(target / "completion.json") != validated.completion_sha256:
            raise RunValidationError("Source completion changed while pinning")
        validate_run(target, kind)
        self.sources.append(
            {
                "label": label,
                "kind": kind,
                "path": target.relative_to(self.path).as_posix(),
                "run_id": source.name,
                "completion_sha256": sha256_file(target / "completion.json"),
            }
        )
        return target

    def publish(self, *, row_counts: dict[str, int] | None = None) -> None:
        self.stage = "hash_inventory"
        files = _files(self.path)
        inventory = [
            {"path": name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for name, path in sorted(files.items())
        ]
        completion = {
            "schema_version": 2,
            "kind": self.kind,
            "county": "Isanti",
            "run_id": self.path.name,
            "status": "complete",
            "stage": "raw_complete" if self.kind.endswith("_raw") else "processed_complete",
            "created_at": datetime.now(UTC).isoformat(),
            "sources": self.sources,
            "artifacts": inventory,
            "row_counts": row_counts or {},
            "provenance": build_provenance({"kind": self.kind, "completion_protocol": 2}),
        }
        self.stage = "completion_write"
        pending = self.path / "completion.pending.json"
        write_json(pending, completion)
        validate_run(self.path, self.kind, pending=True)
        self.stage = "completion_install"
        if (self.path / "completion.json").exists():
            raise RunValidationError("Completion record already exists")
        os.replace(pending, self.path / "completion.json")
        self.stage = "pointer_update"
        pointer_pending = self.path.parent / f".latest-{self.path.name}.pending.json"
        write_json(
            pointer_pending,
            {
                "kind": self.kind,
                "run_id": self.path.name,
                "completion_sha256": sha256_file(self.path / "completion.json"),
            },
        )
        os.replace(pointer_pending, self.path.parent / "latest.json")
        self.stage = "published"
