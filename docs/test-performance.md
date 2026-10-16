# Test feedback and performance (ML-129)

## Decision and limits

Use targeted offline tests while editing, one full offline regression at the
implementation boundary, then proportionate checks for follow-up changes.
Do not repeat full local Windows and hosted Windows suites for unchanged code.
Any code/test/configuration change still gets the full hosted matrix. Only a
small explicit documentation/board allowlist gets the Linux-only fast path.
Fast mode means **Windows was not run**, not that Windows passed.

No assertions were removed. Live government tests remain opt-in. No new runtime
or development dependency, deployment, county ingestion, or data migration was
introduced. Historical county inputs/results are unchanged.

## Measured bottlenecks and changes

On Windows, the old bounded JSON reader requested up to 128 MiB for every tiny
evidence file. A profiled synthetic review failure test spent 13.14 seconds in
440 `_read_bytes` calls (18.76 seconds total profiler time). After replacing the
large request with at-most-64-KiB chunks, those same 440 calls took 0.22 seconds
(8.39 seconds total profiler time, real Git still enabled). These diagnostic
profiles overlapped another test run; they locate a hotspot, not a controlled
end-to-end speed guarantee. A separate 100-read microcheck on the same parcel
fixture measured 3.14 seconds before versus 0.017 seconds after; it is illustrative,
not representative of the entire application.

The reader still reads actual bytes up to **limit + 1** and rejects overflow;
it never trusts an initial file size. Exact limits, empty files, multiple chunks,
short reads, growing/over-budget streams, duplicate JSON keys, malformed JSON and
encoding failures have regression coverage. Hashing, containment, provenance,
completion and row reconciliation are unchanged and never cached/bypassed.

Provenance generation also launches three Git commands per record. Ten synthetic
records took 2.62 seconds, including 1.80 seconds in Git identity collection.
The default synthetic test fixture now mocks **only** that external Git identity,
with null revision/dirty and status `synthetic_test_fixture`. Every call gets a
new dictionary. Actual source/configuration/artifact hashes and runtime inspection
still execute. All dedicated provenance tests use `real_git` and retain real Git
collection and existing missing-Git/dirty/unborn/unrelated-repository cases.
Live integration tests also bypass the mock. Production Git identity is unchanged.

Serial execution is retained. The measured large-read overhead and repeated Git
processes could be reduced directly without introducing worker isolation issues
or another dependency. Parallel workers have **not** been benchmarked or claimed
as a speedup; reconsider only if remaining measured latency justifies the overhead.
OneDrive and antivirus were not established as causes and were not reconfigured.

## Dated evidence: 2026-10-16 (America/Chicago)

Original baseline code: `3375562344845e5513e091d19b55e07106409771`.
The local baseline began with planning-only edits and loaded pre-optimization
tests/reader/fixtures; ML-129 edits were made while it ran. After measurements use
the ML-129 implementation working tree, with the same original 539 offline cases,
fixture files, Python 3.12.14, Windows 11 build 26300, active `.venv`, workstation
and project-local temporary-storage location. This is a single-run comparison,
not a clean-room or statistically repeated benchmark. Hosted evidence below pins
the final implementation revision independently.

| Measurement | Before | After |
|---|---:|---:|
| Original local offline suite (537 passed, 2 privilege skips, 1 live deselected) | 344.68 s | 75.36 s |
| Recorded-snapshot review test, call | 14.71 s | 3.53 s |
| Land-focused export failure test, call | 16.00 s | 2.23 s |
| Largest remaining test call in that run | 16.00 s | 3.53 s |

The whole-suite observation is approximately 78% less test time, or 4.6 times as
fast; future stories and machines may differ. The after run excludes only the two
new ML-129 test modules to hold the original comparison population constant.
Those modules and dedicated provenance tests separately passed 86 targeted cases.
Two local real-symlink cases remain privilege skips, not passes; hosted runners
must exercise them. New reader tests initially exposed overly long generated
parameter IDs on Windows; short explicit IDs fixed that test-only setup failure.

Original complete hosted baseline:
[ML-127 run 38943524762](https://github.com/huschked/minnesota-land-intelligence/actions/runs/38943524762),
revision `1ac55f3c0e33257bef7128683aeb00077f0a5c6b`, 539 passed per job.
All jobs started about three seconds after run creation. Times below are distinct
setup/test phases, not four serial waits:

| Platform/Python | Before-test setup, approximately | Test execution | Entire job |
|---|---:|---:|---:|
| Linux / 3.11 | 9 s | 13.49 s | 25 s |
| Linux / 3.12 | 12 s | 16.60 s | 33 s |
| Windows / 3.11 | 70 s | 339.14 s | 419 s |
| Windows / 3.12 | 40 s | 358.37 s | 405 s |

That older workflow did not report individual Linux test durations; they cannot
be recovered from its summary. New full and fast jobs print the slowest 20
setup/call/teardown durations and produce a local runner JUnit report. Reports
contain synthetic tests, are ignored locally, and are not uploaded as artifacts.
Setup, runner queues and the final gate still add latency beyond pytest time.

[Hosted ML-129 run 38952761645](https://github.com/huschked/minnesota-land-intelligence/actions/runs/38952761645)
passed for implementation revision `93f8dd7d0cfc3e0a2708f393954dc35228d1ad5c`.
Each of the four jobs passed **616 offline tests with no skips**, plus lint,
dependency consistency, board and explicit live collection (one selected, 616
deselected; no live execution). The plan selected full coverage and the final
`CI gate` passed. Both real symlink fixtures ran on hosted Windows/Linux. The
complete workflow took 122 seconds including plan/setup/gate, versus 423 seconds
in the historical ML-127 run; runner conditions and test counts differ, so the
same-population local comparison above is the stronger controlled comparison.

| Platform/Python | ML-129 tests | Entire job | Slowest setup | Slowest call | Slowest teardown |
|---|---:|---:|---:|---:|---:|
| Linux / 3.11 | 9.85 s | 26 s | 0.0023 s | 0.3176 s | 0.0006 s |
| Linux / 3.12 | 12.27 s | 33 s | 0.0045 s | 0.3992 s | 0.0008 s |
| Windows / 3.11 | 50.71 s | 100 s | 0.1136 s | 2.6723 s | 0.0006 s |
| Windows / 3.12 | 57.83 s | 100 s | 0.1747 s | 2.8115 s | 0.0020 s |

The log identifies the test for each phase maximum. Largest Linux call:
recorded-snapshot review; Windows 3.11: ambiguous-join export failure; Windows 3.12:
candidate-review export failure. These remain genuine pipeline/validation tests,
not reduced assertions. Later documentation-only completion commits do not alter
the tested runtime/test/CI code and deliberately use the Linux-only fast path.

## Exact local commands

Run from the project root with the existing environment. Use a **new, unused**
`--basetemp` every time on this Windows workstation; pytest can clear its target.
Never select a source/data/backup directory. Examples:

```powershell
# During an edit: choose the affected modules, not every test.
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_bounded_run_reads.py tests/unit/test_ci_plan.py --basetemp=.test-tmp-dev-NEW -p no:cacheprovider
# Ready for implementation verification: full offline suite, with timings.
.\.venv\Scripts\python.exe -m pytest -q --durations=20 --durations-min=0.1 --basetemp=.test-tmp-full-NEW -p no:cacheprovider
# Independent provenance coverage always uses real Git, including in the full suite.
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_provenance.py --basetemp=.test-tmp-provenance-NEW -p no:cacheprovider
# Fallback/benchmark: disable the synthetic Git fixture for all selected tests.
.\.venv\Scripts\python.exe -m pytest -q --real-test-git --durations=20 --basetemp=.test-tmp-real-git-NEW -p no:cacheprovider
# Selection only: never executes the government-service test.
.\.venv\Scripts\python.exe -m pytest -m integration --collect-only -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe scripts/render_kanban.py --check
```

The synthetic-fixture-specific assertion intentionally skips under
`--real-test-git`; the dedicated real provenance assertions do not. If mocking is
suspect, use that flag and the provenance module, not a disabled validator.

For the original-suite before/after comparison command, add
`--ignore=tests/unit/test_ci_plan.py --ignore=tests/unit/test_bounded_run_reads.py`
and `--junitxml=.test-ml129-COMPARISON.xml` to the full timing command. Baseline
used `.test-tmp-ml129-baseline`; after used `.test-tmp-ml129-after-original`.
Do not reuse these now-existing directories. Timings are pytest elapsed times;
installation was not repeated during local comparisons.

For documentation/board-only follow-ups, regenerate/check the board, check links
and the diff, and lint an edited Python renderer. Do not invent unit tests for
prose or repeat unchanged full suites merely to record their result in docs.
If tests/code change after a full pass, rerun affected tests locally; require the
full hosted matrix for that updated code revision. Completion evidence clearly
distinguishes the tested implementation revision from later documentation commits.

## Hosted coverage and fallback

[ci_plan.py](../scripts/ci_plan.py) classifies complete Git diffs, including deletions
and both sides of renames. Pull requests use the merge base; pushes use the full
before/after range, not only the last commit. Missing history, initial pushes,
empty diffs, unknown paths, code, tests, dependencies, config, and workflow changes
fail closed to the full four-job matrix.

- Fast allowlist: `docs/**/*.md`, `README.md`, `AGENTS.md`, `LICENSE`, `.gitignore`,
  and `scripts/render_kanban.py`. Runs the **entire** offline suite, lint, dependency
  consistency, board and live-test collection on Linux/Python 3.12 only.
- Full: all other changes; tag pushes; published releases; push commit messages
  or PR titles containing `[full-ci]`; manual dispatch; weekly Monday 11:23 UTC
  (06:23 CDT / 05:23 CST, scheduler delays possible). Full means Windows/Linux
  crossed with Python 3.11/3.12. Put `[full-ci]` in the milestone commit/PR title
  if its diff would otherwise be documentation-only. No live tests execute.
- Manual fallback: `gh workflow run ci.yml --repo huschked/minnesota-land-intelligence --ref master`.
  This always requests full coverage. Follow its **actual** result; cancellation
  or a skip is not a platform pass. There is no fast-mode override for code changes.

The fixed **CI gate** runs even after failure/cancellation/skips and fails unless
both the plan and all selected matrix checks succeeded. The plan summary lists
actual platform coverage; the gate is not a claim that excluded platforms ran.
Matrix job names are retained. The workflow itself is never path-filtered away.

On 2026-10-16 the branch API reported `master.protected=false`. Separate protection
and ruleset APIs returned an account-plan limitation (403); their contents were
not verified. No repository security, billing, permissions or protection settings
were changed. If required checks are configured later, require **CI gate**, not a
Windows matrix name absent from fast runs; otherwise documentation-only merges
will wait for that missing check. Never remove existing required checks to make a
run look green. Keep full coverage until that policy is reconciled if protection
changes; conditional skips must not be substituted for required platform passes.

Selection fixtures cover fast/full events, missing/invalid diffs, complete push/PR
ranges, sensitive/unknown paths, explicit milestone requests, gate failure/skip/
cancellation combinations and workflow wiring. Schedule/manual/event selection
is fixture-tested; that does not claim a future scheduled run already executed.

References: [pytest timing reports](https://docs.pytest.org/en/stable/how-to/usage.html#profiling-test-execution-duration),
[GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
[testing policy](testing.md), [publication](publication.md).
