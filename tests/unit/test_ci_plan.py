"""CI selection is fail-closed; no government service or GitHub API is used."""

import json
import subprocess
from itertools import product
from pathlib import Path

import pytest

from scripts import ci_plan


@pytest.mark.parametrize("paths", [
    ["README.md"], ["docs/testing.md", "docs/planning/kanban.md"],
    ["scripts/render_kanban.py", ".gitignore", "AGENTS.md"],
])
@pytest.mark.parametrize("event_name", ["push", "pull_request"])
def test_documentation_changes_select_linux_only(paths, event_name):
    assert ci_plan.full_matrix_reason(event_name, {}, paths) == ""
    assert ci_plan.FAST_MATRIX == {"include": [{"os": "ubuntu-latest", "python": "3.12"}]}


@pytest.mark.parametrize("paths", [
    None, [], ["src/mn_land/runs.py"], ["tests/unit/test_provenance.py"],
    ["tests/fixtures/isanti_parcel.json"], ["pyproject.toml"], ["constraints-dev.txt"],
    [".github/workflows/ci.yml"], ["scripts/ci_plan.py"], ["docs/example.csv"],
    ["new-unknown-file"], ["README.md", "src/mn_land/cli.py"], ["../README.md"],
    ["/README.md"], ["docs\\testing.md"], [""],
])
def test_sensitive_unknown_and_unavailable_changes_select_full(paths):
    assert ci_plan.full_matrix_reason("push", {}, paths)
    assert len(ci_plan.FULL_MATRIX["include"]) == 4


@pytest.mark.parametrize("event_name,event", [
    ("schedule", {}), ("workflow_dispatch", {}), ("release", {}), ("unknown", {}),
    ("push", {"ref": "refs/tags/v0.2"}),
    ("push", {"head_commit": {"message": "Milestone [full-ci]"}}),
    ("pull_request", {"pull_request": {"title": "Milestone [full-ci]"}}),
    ("push", {"head_commit": "malformed"}),
])
def test_explicit_full_and_malformed_events_cannot_select_fast(event_name, event):
    assert ci_plan.full_matrix_reason(event_name, event, ["README.md"])


@pytest.mark.parametrize("plan,checks", list(product(
    ["success", "failure", "cancelled", "skipped"], repeat=2,
)))
def test_gate_never_turns_failure_cancellation_or_skip_into_success(plan, checks):
    assert ci_plan.gate_passes(plan, checks) == (plan == checks == "success")


def test_push_diff_uses_complete_git_history_without_rename_filtering(monkeypatch):
    def run(arguments, **kwargs):
        assert arguments == [
            "git", "diff", "--no-renames", "--name-only", "-z", "a" * 40, "b" * 40, "--",
        ]
        assert kwargs["timeout"] == 30
        return subprocess.CompletedProcess(arguments, 0, stdout=b"README.md\0deleted.py\0")
    monkeypatch.setattr(subprocess, "run", run)
    assert ci_plan.changed_paths("push", {"before": "a" * 40, "after": "b" * 40}) == [
        "README.md", "deleted.py",
    ]


def test_pull_request_uses_merge_base_not_only_last_commit(monkeypatch):
    calls = []

    def run(arguments, **kwargs):
        calls.append(arguments)
        output = "c" * 40 + "\n" if "merge-base" in arguments else b"src/mn_land/runs.py\0"
        return subprocess.CompletedProcess(arguments, 0, stdout=output)
    monkeypatch.setattr(subprocess, "run", run)
    event = {"pull_request": {"base": {"sha": "a" * 40}, "head": {"sha": "b" * 40}}}
    assert ci_plan.changed_paths("pull_request", event) == ["src/mn_land/runs.py"]
    assert calls[0] == ["git", "merge-base", "a" * 40, "b" * 40]
    assert calls[1][-3:] == ["c" * 40, "b" * 40, "--"]


@pytest.mark.parametrize("event", [
    {}, {"before": "0" * 40, "after": "b" * 40},
    {"before": "--option", "after": "b" * 40}, {"before": None, "after": "b" * 40},
])
def test_invalid_diff_identity_is_not_executed(monkeypatch, event):
    def unexpected(*args, **kwargs):
        pytest.fail("Untrusted/invalid commit cannot become a Git argument")
    monkeypatch.setattr(subprocess, "run", unexpected)
    assert ci_plan.changed_paths("push", event) is None


def test_git_failure_selects_full(monkeypatch):
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(128, "git")
    monkeypatch.setattr(subprocess, "run", fail)
    paths = ci_plan.changed_paths("push", {"before": "a" * 40, "after": "b" * 40})
    assert paths is None
    assert ci_plan.full_matrix_reason("push", {}, paths)


@pytest.mark.parametrize("mode", ["fast", "full", "unreadable"])
def test_plan_cli_outputs_actual_coverage(monkeypatch, tmp_path, mode):
    event_file = tmp_path / "event.json"
    event_file.write_text("not-json" if mode == "unreadable" else json.dumps({}), encoding="utf-8")
    output, summary = tmp_path / "output.txt", tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_file))
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr(ci_plan, "changed_paths", lambda *args: [
        "README.md" if mode == "fast" else "src/mn_land/runs.py",
    ])
    monkeypatch.setattr("sys.argv", ["ci_plan.py"])
    assert ci_plan.main() == 0
    expected_mode = "fast" if mode == "fast" else "full"
    assert f"mode={expected_mode}" in output.read_text()
    matrix_line = output.read_text().splitlines()[0].removeprefix("matrix=")
    assert json.loads(matrix_line) == (
        ci_plan.FAST_MATRIX if mode == "fast" else ci_plan.FULL_MATRIX
    )
    if mode == "fast":
        assert "Windows not run" in summary.read_text()


@pytest.mark.parametrize("result,code", [("success", 0), ("failure", 1), ("skipped", 1)])
def test_gate_cli_exit_status(monkeypatch, result, code):
    monkeypatch.setattr("sys.argv", ["ci_plan.py", "--gate", "success", result])
    assert ci_plan.main() == code


def test_workflow_wires_plan_and_always_running_gate():
    workflow = (Path(__file__).parents[2] / ".github/workflows/ci.yml").read_text()
    assert "fetch-depth: 0" in workflow
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in workflow
    assert "if: ${{ always() }}" in workflow
    assert "needs: [plan, offline-checks]" in workflow
    assert 'scripts/ci_plan.py --gate "$PLAN_RESULT" "$CHECKS_RESULT"' in workflow
    assert "--durations=20" in workflow
    assert "-m integration --collect-only" in workflow
    assert "schedule:" in workflow and "workflow_dispatch:" in workflow
    assert "paths-ignore:" not in workflow and "pull_request_target:" not in workflow


def test_synthetic_git_is_explicit_and_not_shared_between_calls(tmp_path, request):
    from mn_land import provenance
    if request.config.getoption("--real-test-git"):
        pytest.skip("Synthetic Git fixture deliberately disabled for this benchmark")
    first = provenance._git_identity(tmp_path)
    assert first == {"revision": None, "dirty": None, "status": "synthetic_test_fixture"}
    first["status"] = "changed"
    assert provenance._git_identity(tmp_path)["status"] == "synthetic_test_fixture"
