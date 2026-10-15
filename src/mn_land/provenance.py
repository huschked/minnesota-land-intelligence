"""Local execution identity and byte-level evidence; never a data authority."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from collections.abc import Iterable, Mapping
from importlib.metadata import distributions
from pathlib import Path
from typing import Any

from mn_land import __version__

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_identity(root: Path) -> dict[str, Any]:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), *args],
            check=True, capture_output=True, text=True, timeout=5,
        ).stdout.strip()

    identity: dict[str, Any] = {"revision": None, "dirty": None, "status": "unavailable"}
    try:
        # An installed wheel must not accidentally claim an unrelated enclosing repo.
        if Path(git("rev-parse", "--show-toplevel")).resolve() != root.resolve():
            return identity
        identity["dirty"] = bool(git("status", "--porcelain", "--untracked-files=normal"))
        identity["revision"] = git("rev-parse", "--verify", "HEAD")
        identity["status"] = "available"
    except (OSError, subprocess.SubprocessError):
        # Missing Git, unborn HEAD, and source archives remain explicitly unknown.
        pass
    return identity


def build_provenance(
    configuration: Mapping[str, Any],
    *,
    inputs: Iterable[Path] = (),
    outputs: Iterable[Path] = (),
) -> dict[str, Any]:
    """Hash explicit artifacts, not directories guessed from the working directory.

    Callers supply JSON-compatible, nonsecret effective configuration. Missing
    artifacts raise an error; unavailable Git identity does not prevent a run.
    """
    encoded_config = json.dumps(
        dict(configuration), sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    package_root = Path(__file__).resolve().parent
    source_files = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(package_root.rglob("*.py"))
    }
    source_hash = hashlib.sha256(
        json.dumps(source_files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    def artifacts(paths: Iterable[Path]) -> list[dict[str, str]]:
        return [
            {"path": str(path.resolve()), "sha256": sha256_file(path)}
            for path in sorted(set(paths))
        ]

    constraints = PROJECT_ROOT / "constraints-dev.txt"
    return {
        "schema_version": 1,
        "code": {
            "package_version": __version__,
            "git": _git_identity(PROJECT_ROOT),
            "python_sources_sha256": source_hash,
            "python_source_files": source_files,
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "installed_distributions": sorted(
                ({"name": d.metadata["Name"], "version": d.version} for d in distributions()),
                key=lambda d: (d["name"].lower(), d["version"]),
            ),
            "constraints_sha256": sha256_file(constraints) if constraints.is_file() else None,
        },
        "configuration": json.loads(encoded_config),
        "configuration_sha256": hashlib.sha256(encoded_config.encode("utf-8")).hexdigest(),
        "inputs": artifacts(inputs),
        "outputs": artifacts(outputs),
    }
