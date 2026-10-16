"""Choose CI coverage conservatively; unknown changes require the full matrix."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

FAST_MATRIX = {"include": [{"os": "ubuntu-latest", "python": "3.12"}]}
FULL_MATRIX = {
    "include": [
        {"os": os_name, "python": version}
        for os_name in ("ubuntu-latest", "windows-latest")
        for version in ("3.11", "3.12")
    ]
}
FAST_FILES = {"README.md", "AGENTS.md", "LICENSE", ".gitignore", "scripts/render_kanban.py"}
SHA = re.compile(r"[0-9a-fA-F]{40}")


def full_matrix_reason(event_name: str, event: dict[str, Any], paths: list[str] | None) -> str:
    if event_name in {"workflow_dispatch", "schedule", "release"}:
        return f"{event_name} explicitly requires all platforms"
    if event_name not in {"push", "pull_request"}:
        return "unknown event requires all platforms"
    if str(event.get("ref", "")).startswith("refs/tags/"):
        return "tag/milestone requires all platforms"
    commit = event.get("head_commit") or {}
    pull = event.get("pull_request") or {}
    if not isinstance(commit, dict) or not isinstance(pull, dict):
        return "malformed event requires all platforms"
    if "[full-ci]" in str(commit.get("message", "")) or "[full-ci]" in str(pull.get("title", "")):
        return "explicit milestone [full-ci] request"
    if not paths:
        return "missing, empty or unavailable diff requires all platforms"
    for name in paths:
        path = PurePosixPath(name)
        if not name or "\\" in name or path.is_absolute() or ".." in path.parts:
            return "unrecognized path requires all platforms"
        if name in FAST_FILES:
            continue
        if path.parts[0] == "docs" and path.suffix.lower() == ".md":
            continue
        return "code, tests, configuration or unrecognized changes require all platforms"
    return ""


def changed_paths(event_name: str, event: dict[str, Any]) -> list[str] | None:
    """Use complete Git diffs, never a truncated API file list; fail closed."""
    try:
        if event_name == "push":
            base, head = event["before"], event["after"]
        elif event_name == "pull_request":
            pull = event["pull_request"]
            base, head = pull["base"]["sha"], pull["head"]["sha"]
        else:
            return None
        if any(not SHA.fullmatch(value) or value == "0" * 40 for value in (base, head)):
            return None
        if event_name == "pull_request":
            base = subprocess.run(
                ["git", "merge-base", base, head], check=True, capture_output=True,
                text=True, timeout=30,
            ).stdout.strip()
        result = subprocess.run(
            ["git", "diff", "--no-renames", "--name-only", "-z", base, head, "--"],
            check=True, capture_output=True, timeout=30,
        )
        return [name for name in result.stdout.decode("utf-8", errors="strict").split("\0") if name]
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
        return None


def gate_passes(plan_result: str, checks_result: str) -> bool:
    return plan_result == checks_result == "success"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", nargs=2, metavar=("PLAN_RESULT", "CHECKS_RESULT"))
    args = parser.parse_args()
    if args.gate is not None:
        if not gate_passes(*args.gate):
            print("CI gate failed: required plan or selected checks did not succeed.")
            return 1
        print("All selected CI checks passed; see the plan for actual platform coverage.")
        return 0
    event_name = os.environ.get("GITHUB_EVENT_NAME", "unknown")
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        if not isinstance(event, dict):
            raise TypeError("Event must be an object")
        reason = full_matrix_reason(event_name, event, changed_paths(event_name, event))
    except (KeyError, ValueError, TypeError, OSError):
        reason = "unreadable event requires all platforms"
    matrix = FULL_MATRIX if reason else FAST_MATRIX
    mode = "full" if reason else "fast"
    explanation = reason or "documentation/board-only diff; Linux only, Windows not run"
    print(f"CI mode: {mode}. {explanation}")
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
            output.write(f"matrix={json.dumps(matrix, separators=(',', ':'))}\nmode={mode}\n")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as summary:
            summary.write(f"## Selected CI coverage\n\nMode: **{mode}**. {explanation}.\n")
            summary.write("\n".join(
                f"- {item['os']}, Python {item['python']}" for item in matrix["include"]
            ) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
