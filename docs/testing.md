# Offline tests and CI (ML-118)

## Local commands

With the development dependencies installed in the active environment:

```powershell
python -m pytest -q
python -m ruff check src tests scripts
python scripts/render_kanban.py --check
```

`pyproject.toml` sets `--strict-markers -m "not integration"` as default pytest
options. Unknown markers fail collection, so a misspelled integration marker does
not silently become an ordinary test. Tests use sanitized fixtures and mock HTTP
transports. `tests/conftest.py` blocks standard socket DNS resolution and TCP
connection calls in unmarked tests before contact. This is a testing guardrail,
not an OS-level firewall: subprocesses or custom networking libraries are not
contained by it. Do not use them to bypass the offline policy.

An explicit command-line marker replaces the configured default selection:

```powershell
# Live: contacts the official county service; run intentionally and sparingly.
python -m pytest -m integration -q
# Selection check only: collects the live test, without executing requests.
python -m pytest -m integration --collect-only -q
```

The network guard is disabled for deliberately marked integration tests. Do not
clear the default options to run everything unintentionally. No credentials or
private datasets are needed for the current public-source integration check.
Unavailability of the county service must not block normal fixture tests.
For this workstation's Windows temp/cache permission workaround, see
[recovery](reproducibility.md#clean-environment); always choose an unused temporary
directory, because pytest may clear the selected directory.

## GitHub Actions

[CI workflow](../.github/workflows/ci.yml) runs on push, pull request, or manual
dispatch, with four independent jobs: Ubuntu/Windows times Python 3.11/3.12.
The package declares >=3.11; this matrix checks its minimum and the workstation's
Python minor version, not every later Python or operating-system release.

Each job installs `.[dev]` with `constraints-dev.txt`, checks dependency consistency,
runs Ruff, validates the generated Kanban board, executes default offline tests,
and checks explicit integration selection using collection only. Installation and
action setup require network access; no test execution should query government
services. A failing job does not cancel the other matrix jobs. Runs have a ten-
minute job timeout, and a newer run for the same ref cancels an obsolete one.

Official checkout/setup actions are pinned to verified commit SHAs of their v6
releases. The workflow grants only `contents: read`, does not persist checkout
credentials, uses no custom secrets, and never deploys, runs county ingestion,
uploads county outputs, or changes repository visibility. The pip cache contains
dependency downloads, not the ignored county-data directories.
No branch-protection rule is configured here; automatic checks are not the same
as enforcing them as merge requirements. Private-repository Actions usage may
consume the account's included minutes or existing billable allowance; no billing
settings or spending limits are changed by this task.

## Validation and evidence

`tests/unit/test_test_policy.py` runs two isolated sample suites using the actual
repository configuration. Opposing sentinel assertions prove that ordinary runs
deselect live tests and `-m integration` selects them instead. These checks make
no network calls. Four additional cases confirm DNS and TCP calls fail before
contact. The real live test is collected separately, not executed for this card.

2026-10-14 local verification: default selection passed 72 tests with one live
test deselected. Explicit live-test collection selected the single existing
integration test and deselected the 72 offline cases. Ruff and board validation
passed locally.

The [first hosted CI run](https://github.com/huschked/minnesota-land-intelligence/actions/runs/38673156552)
passed for implementation commit `44114fcd7bc719237be50390da0ee23d1a5febf5`.
All four Windows/Linux x Python 3.11/3.12 jobs passed dependency consistency,
Ruff, board validation, 72 default offline tests (one deselected), and explicit
live-test collection (one selected, 72 deselected). The run completed on
2026-10-15 UTC / 2026-10-14 America/Chicago. No live county test was executed.

Configuration references: [pytest configuration](https://docs.pytest.org/en/stable/reference/customize.html),
[GitHub Python workflows](https://docs.github.com/en/actions/tutorials/build-and-test-code/python),
[checkout](https://github.com/actions/checkout), and
[setup-python](https://github.com/actions/setup-python).
