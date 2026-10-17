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

## Fast feedback (ML-129)

Use affected modules while editing and one full offline regression at the
implementation boundary; documentation-only follow-ups receive proportional board,
link and diff checks. [Test performance](test-performance.md) gives exact commands,
baseline/after timings, the synthetic Git fixture boundary and full-run fallback.
Dedicated provenance tests always retain real Git identity collection; production
hash/path/completion/accounting checks are unchanged. Live tests stay opt-in.

## GitHub Actions

[CI workflow](../.github/workflows/ci.yml) runs on push, pull request, manual
dispatch, published release, or a weekly schedule. A conservative complete-diff
plan selects one Linux/Python 3.12 job for an explicit documentation/board-only
allowlist, otherwise four independent jobs: Ubuntu/Windows times Python 3.11/3.12.
Tag/milestone, manual and scheduled runs request the full matrix. Fast runs state
that Windows was not run. The fixed `CI gate` fails on a failed, cancelled or
skipped required plan/matrix job. See [coverage and fallback](test-performance.md#hosted-coverage-and-fallback)
for triggers, limitations and required-check configuration; no branch protection
settings are changed.
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

## ML-125 regression coverage

[Validation](validation.md) maps F01-F09 to the new fixture groups. They exercise
strict metadata, evidence containment, text IDs/typed years, CSV/XLSX shapes and
lineage, formulas/caches/errors, resource budgets, schema drift, GIS quarantines,
and import/review preservation. The live-source test remains opt-in; it is only
collected during this task. Windows accounts without symlink privileges skip one
real symlink test; Linux CI must exercise that path. Strict path resolution can
require unsandboxed filesystem permissions on this workstation; a permission
error must not be handled by disabling the containment check.

Local ML-125 verification on 2026-10-14 passed 282 tests, skipped the real symlink
fixture because this Windows account lacks the required privilege, and deselected
the one live integration test. Ruff passed. Explicit integration collection selected
one test and deselected 283 offline cases, without executing a request.

[Hosted ML-125 run 38678405055](https://github.com/huschked/minnesota-land-intelligence/actions/runs/38678405055)
passed for implementation commit `c359a9271f5d18c5e02e8640814f2cb24cf9e830`.
All four Windows/Linux x Python 3.11/3.12 jobs passed 283 tests with no skips and
one live deselection, plus dependency consistency, Ruff, board validation, and
explicit live collection. The real symlink fixture ran successfully on both
hosted platforms. The run completed on 2026-10-15 UTC / 2026-10-14 America/Chicago.
No live government requests were executed by the tests.

## ML-127 regression coverage

[Publication](publication.md) traces R01-R07 to
[publication tests](../tests/unit/test_run_publication.py). They cover exact
retained originals, input changes during validation/pinning, every parcel/join/
review export failure, normalization/hash/manifest/completion/pointer failures,
malformed inputs, failed/staging/legacy and malicious manifests, pointer fallback,
available legacy hashes, symlinks, concurrent identity reservation, actual output
inventories, empty candidates, quarantine locations, disjoint source partitions,
overlapping prior/current parcel views and preserved source holds.

Fixtures create actual synthetic raw-complete sources through the retrieval and
completion code; historical fixture directories are not certified. Optional
report-script tests stub PDF dependencies and verify input validation happens
before work; they do not parse PDFs or contact the county. Core dependencies and
the existing CI matrix are unchanged. Windows accounts without symlink privileges
skip two real symlink tests; hosted Windows/Linux jobs must exercise them.

Local verification on 2026-10-16: the release suite passed 536 tests with two
Windows symlink-privilege skips and one live deselection. The final added boolean
counter fixture passed separately. Explicit integration collection selected one
test and deselected all 539 offline cases, without executing a request. Ruff,
13-epic/84-story board validation and 291 relative documentation links/anchors
passed. The updated synthetic probe rejects D08's manifest-only empty snapshot;
no original county rows were imported or live government APIs called.

[Hosted ML-127 run 38943524762](https://github.com/huschked/minnesota-land-intelligence/actions/runs/38943524762)
passed for implementation commit `1ac55f3c0e33257bef7128683aeb00077f0a5c6b`.
Each Windows/Linux x Python 3.11/3.12 job passed 539 offline tests with no skips
and one live deselection, plus dependency consistency, Ruff, board validation and
explicit live collection. Both real symlink fixtures ran on both hosted platforms.
The run completed 2026-10-16 UTC / America/Chicago. The final bounded failure-location
field was checked by a targeted local fixture before the completion commit.
No original county inputs/results were changed or live government requests made.

## ML-126 regression coverage

[Retrieval](retrieval.md) traces H01-H05 to synthetic capability/count/inventory/
page/drift fixtures and H06-H08 to the real urllib transport using fake responses
and clocks. Tests assert exact attempts/timeouts/waits, Retry-After delta/date
behavior, permanent/transient classification, capped/incomplete original bodies,
parsed/body hashes, request associations, failure evidence and successful end-to-end
acquisition provenance. CLI failure exits, effective Settings, valid zero records,
short pages and existing normalization/join/review behavior are also covered.

Local verification on 2026-10-15: 467 passed, one Windows symlink-privilege skip,
and one live test deselected. Explicit integration collection selected one test
and deselected 468 offline tests; no requests executed. Ruff and the generated
13-epic/84-story board check passed. The updated synthetic discovery probe rejects
D06, clamps page size to one, makes one HTTP 404 attempt, and honors two 30-second
mocked waits for three HTTP 429 attempts. At ML-126 completion D08 was still a
deferred ML-127 reader-eligibility gap; ML-127 subsequently fixed it. Documentation
relative links/anchors passed a read-only check before completion edits.

[Hosted ML-126 run 38834485822](https://github.com/huschked/minnesota-land-intelligence/actions/runs/38834485822)
passed for implementation commit `92e7c687a78ec66c199ff9b31c9e7d1951c31eb2`.
All four Windows/Linux x Python 3.11/3.12 jobs passed 468 offline tests with no
skips and one live deselection, plus dependency consistency, Ruff, board checks,
and explicit live collection. Both hosted platforms exercised the real symlink
fixture. The run completed on 2026-10-16 UTC / 2026-10-15 America/Chicago.
No live government requests were executed by the tests.

## ML-129 test feedback verification

[Performance evidence and commands](test-performance.md) record the measured
bounded-read bottleneck, test-only synthetic Git identity, unchanged validation
safety, and conservative fast/full CI policy. Local identical-population runs
passed the same 537 cases with two symlink-privilege skips and one live deselection
in 344.68 seconds before and 75.36 seconds after. The new safety/selection tests
and dedicated provenance/test-policy cases passed 92 targeted checks after the
phase-timing reporter was added. No development/runtime dependency was added.

[Full hosted run 38952761645](https://github.com/huschked/minnesota-land-intelligence/actions/runs/38952761645)
passed at `93f8dd7d0cfc3e0a2708f393954dc35228d1ad5c`. All four Windows/Linux x
Python 3.11/3.12 jobs passed 616 offline tests with no skips, dependency consistency,
Ruff, board checks and explicit live-test collection (one selected, 616 deselected).
Linux tests took 9.85/12.27 seconds; Windows 50.71/57.83 seconds. Full workflow
including plan and final gate completed in 122 seconds. Phase maxima are recorded
in the performance document and logs. The plan selected full coverage for code
changes, and the gate passed only after all four jobs succeeded. Fixture checks
also cover fast diff classification and failure/cancellation/skip gate outcomes.
No government API tests were executed and historical county data remains unchanged.

## ML-123 selected snapshots and replay

[Replay commands and boundaries](replay.md) describe explicit raw parcel/import
selection, moved self-contained completed joins, captured source dates/limits,
canonical fingerprints, export comparisons and intentional threshold overrides.
[S01-S07 fixtures](../tests/unit/test_snapshot_replay.py) cover CSV/XLSX, later
execution dates, unavailable old roots, no latest/acquisition/raw writes, source
compatibility, date offsets/unknowns, source holds, mixed years, drift failures,
prior-success preservation, nested destinations and older complete runs without
historical normalization fingerprints. Pre-completion legacy inputs are rejected,
not recertified; no original county rows are reimported.

Local verification on 2026-10-16 passed 643 offline tests, skipped the two real
symlink fixtures because this Windows account lacks privileges, and deselected
one live test in 147.17 seconds. Ruff and the 13-epic/85-story board check passed.
Explicit live collection selected one test and deselected 645 offline cases,
without making requests. CLI replay help was checked; 325 relative document targets
passed. The actual read-only county status check still reports only legacy data;
it did not manufacture completed runs.

[Hosted ML-123 run 38955519528](https://github.com/huschked/minnesota-land-intelligence/actions/runs/38955519528)
passed at implementation commit `7a53fdbec6a902e770e926b4cbe9447533d69b38` on
2026-10-16 UTC / America/Chicago. All four Windows/Linux x Python 3.11/3.12 jobs
passed 645 offline tests with no skips and one live deselection, plus dependency
consistency, Ruff, board and explicit live collection (one selected, 645 deselected).
The final CI gate passed. Hosted Linux test execution took 13.33/14.94 seconds;
Windows took 60.60/96.99 seconds. Both real symlink fixtures executed successfully.
Completion-documentation/board-only updates use fast Linux CI, not a repeated
Windows run or a claim of additional Windows coverage. No live tests were executed.

## ML-201 discovery verification

[The UI decision](ui-plan.md) was reviewed against the historical 15/49/62 view
definitions, canonical/review fields, completion/replay source boundaries and
official Streamlit/FastAPI/WCAG documentation on 2026-10-16. It records the chosen
framework, local workflow/wireframe, access/unknown-data states, U01-U12 acceptance
examples, bounded implementation cards and the actual-data gap addressed by ML-130.
The skill's discovery script found no Streamlit in the active venv; no dependency
was installed to perform this documentation-only spike. The read-only county
status check still found no eligible completed new-protocol data.

Validate this change with board generation/checks, relative-link/anchor review,
diff checks and lint on the edited board renderer, not new unit tests for prose.
Core/UI runtime tests, a live app, keyboard accessibility and framework compatibility
were not newly exercised by this discovery and are not claimed to pass. Existing
automatic fast CI may run the unchanged offline suite; that is regression evidence,
not a UI test or an installed-framework check. No Windows matrix rerun is needed
for these documentation/board-only changes under ML-129's policy.
Local verification passed board generation/validation for 13 epics and 86 stories,
352 relative document targets with no broken paths, renderer Ruff and diff checks.

## ML-130 actual-data preparation verification

[Dated preparation evidence](reviews/isanti-viewer-preparation-2026-10-16.md)
records the user-agreed fresh official GIS plus exact October 13 CSV route.
This was an operational run of unchanged runtime code on Windows / Python 3.12.14,
not a new synthetic feature test. Existing paced acquisition retained 18 HTTP
attempts, 12 pages and reconciled count/ID/schema evidence for 23,890 features;
23,888 normalized and two missing-ID features stayed quarantined. The new raw file,
join and review completed with their actual pinned inputs and validated inventories.

The shared validator passed all five run kinds and an isolated offline replay.
Replay matched both normalized fingerprints, candidate IDs and all nine export
hashes. All 190 baseline historical raw/processed/evidence files retained identical
size/SHA-256. New prior/current/land/focused/special parcel-ID sets matched the
historical exports without imposing their counts. All 62 candidates retained null
canonical delinquent tax, penalty and combined amounts; the new review's manual
verification remains pending without reusing historical report comparisons.

No production Python/configuration/dependency change required new fixture tests or
an unchanged Windows regression rerun. Documentation changes receive board, links,
diff and lint checks plus automatic fast Linux CI under ML-129's policy. This real
county operation is separately dated live evidence, not execution of the pytest
integration test, and does not establish any UI or accessibility test pass. Only
the three data placeholders remain tracked; private datasets/audit files stay ignored.
Local board generation/check passed for 13 epics and 86 stories; all 362 relative
document targets resolved, Ruff passed and `git diff --check` found no whitespace
errors. Read-only CLI status selected the five documented new COMPLETE runs while
still reporting the old two parcel and five file/join snapshots as legacy.

## ML-202 selector/service verification

[The implemented selector](viewer.md) adds 42 offline cases: immutable allowlisted
metadata, explicit join/review identities, holds/nulls, valid-empty versus missing,
legacy/failed/unsupported/corrupt states, changed artifacts/completion/pinned-child
identity, bounded catalogs, self-contained graphs, no latest/acquisition/replay,
and CLI/service loads with Streamlit imports blocked. Supported AppTest controls
cover explicit load/reload/rerun and stable identity despite newer snapshots,
changed-source invalidation, synthetic labels and literal source text. Launcher
checks verify all installed configuration names and CLI precedence over unsafe
environment values; its project defaults match the forced flags.

Windows AppTest uses asyncio's socketpair wake-up mechanism. Its UI-only test
fixture permits a factory-created internal loopback pair, not general localhost
networking. DNS and direct public/arbitrary-loopback connects remain blocked and
have regression assertions. No pytest government integration test was executed.

The implementation-boundary local Windows / Python 3.12.14 run passed **685
offline tests**, skipped the two existing symlink-privilege cases and deselected
one live test in **425.97 seconds**. An unexplained 235.21-second delay occurred
in one service case; the targeted 39-case run passed in 55.05 seconds. These are
observed elapsed times, not a claimed performance improvement or reason to rerun
the unchanged full local suite. Current suite size is 687 offline cases plus one
live case; explicit live collection selected one and deselected 687. Sandbox-only
collection cleanup reported a temporary-directory permission error; collection
outside that sandbox completed cleanly. No source/test assertion was weakened.

Manual actual-data checks loaded ML-130 review
`4e2ebe46423d4f56aab999d7d9eb3a37` through both the service and AppTest: seven
catalog entries, no UI exceptions, actual 62/49/15 prior/land/focused counts,
291 current-year parcels, all 62 combined balances null, October 13 listing and
October 16 GIS dates, manual report verification pending, not synthetic. The first
restricted manual AppTest process stalled on Windows loopback setup; only its
verified helper processes were stopped, then the permitted retry passed in 6.18
seconds. That is an environment retry, not a claim the first attempt passed.

The user approved starting the local server. Windows listener inspection showed
only `127.0.0.1:8501`; the local health endpoint returned `ok`, and dependency
consistency passed. All **658** baseline saved county files retained the same
sizes/SHA-256 after the real-data UI checks; snapshots/latest pointers were not
rewritten. New private check/log artifacts live outside completed runs and stay
ignored. AppTest/server health are not browser keyboard/focus/200%-zoom or screen-
reader conformance tests; those remain ML-206, along with the later full workflow.

[Hosted run 38983351802](https://github.com/huschked/minnesota-land-intelligence/actions/runs/38983351802)
passed at implementation revision `3b430e75b8eecbc346f3493b7ef65bb495d0b7c8`:
**687 passed, one live deselected, no skips** in every Windows/Linux x Python
3.11/3.12 job. All jobs installed `.[dev,ui]`, verified Streamlit 1.66.0 and passed
dependency consistency, lint, board and explicit live collection (one selected,
687 deselected). The final CI gate passed. Test execution took Linux 35.34/45.02
seconds and Windows 168.00/124.18 seconds for Python 3.11/3.12 respectively; whole
check jobs took 1m09s/1m17s and 4m08s/3m41s. The real symlink cases ran in hosted
jobs. These version/platform passes establish the optional framework compatibility
for this shell, not browser accessibility or a transitive dependency lock.
Completion documentation/board-only changes use fast Linux CI under ML-129;
no repeated unchanged local or hosted Windows suite is required.

## ML-124 saved snapshot differences

[Comparison commands and boundaries](snapshot-comparison.md) describe the new
offline report; [fixtures](../tests/unit/test_snapshot_diff.py) cover its acceptance
cases and failure/integrity boundaries. Local Windows Python 3.12 verification:
25 comparison cases passed in 120.66 seconds, followed by the newly added older-
fingerprint rejection case (1 passed in 2.10 seconds). The affected replay,
publication and bounded-reader suites passed 115 tests with one privilege-dependent
symlink skip in 134.72 seconds. Ruff, board consistency and `git diff --check`
passed. Default collection found 713 offline tests plus one excluded live case.
Sandbox collection emitted a temporary-directory cleanup permission error; the
permitted outside-sandbox retry collected cleanly. No test assertion was weakened.
These local targeted runs are not themselves a full-suite or all-platform pass;
the final hosted gate below supplies that coverage.

Actual-data control report `54ae3d5c6fd144959b599bab1b2d20b5` compares ML-130 join
`ce541e7ad88e4a52826a90c9ff5a2139` with its exact offline replay
`f04a7c3e60014ab784cf7f46b64b7a65`. It completed with **871 unchanged listing IDs,
zero added/changed/missing**, from 1,783 source rows. Both sides retain October 13
publication and October 16 capture dates, 23,888 normalized GIS records, two GIS
quarantines, 62 prior-year and 291 current-year large-parcel view IDs. At explicit
as-of October 17 and 30-day policy, publication age is four days and capture ages
one day. These are policy ages, not payment verification. The same-listing-bytes
warning is present; all current payment statuses remain unknown and no identity
replacement links are inferred. This is a reproducibility control, **not two
independent tax observations or a fresh balance update**.

All **660** pre-control files in the private baseline retained their sizes/SHA-256.
Only the active viewer's two server logs were excluded (they remain live/locked);
no server restart or UI change occurred. The ignored baseline is under
`data/processed/isanti/preparation/ml-124-2026-10-17/before.json`, outside completed
runs. New report inputs/results remain ignored and are not uploaded. No live
county test, acquisition, reimport, county message or monetary resolution occurred.

Committed-code validation of the actual report passed in 21.62 seconds and a
second baseline hash check again found all 660 files unchanged. Comparison document
targets exist, the regenerated board passes, and whitespace/lint checks pass.

[Hosted run 39041344103](https://github.com/huschked/minnesota-land-intelligence/actions/runs/39041344103)
passed at implementation revision `1fe57b9ff3c549471dd6c664beaafe273358b971`:
**713 passed, one live deselected, no skips** in each Windows/Linux x Python
3.11/3.12 job. All jobs passed dependency consistency, lint, board and explicit live
collection (one selected, 713 deselected); the final CI gate passed. Test execution
took Linux 46.75/62.05 seconds and Windows 209.24/172.73 seconds for Python
3.11/3.12 respectively. The real symlink cases ran in hosted jobs. No repeated full
local Windows run was needed; completion documentation uses fast Linux-only CI
under ML-129, not another claim of Windows coverage.

## ML-203 saved parcel tables and filters

[Viewer behavior](viewer.md) describes the service/UI boundary and controls.
The 45 new cases cover dynamic nested/overlapping views, inclusive Decimal bounds,
literal/normalized-ID search, nullable classification/improvement/owner values,
known-zero versus unknown, special-class review, numeric null-last sorts and ID
ties, bounded pagination/selectors, immutable allowlists, conflicts/duplicates,
review/import floors, active source and comparison holds, completion revalidation,
selection through sort/page/back/reset/reload/new snapshots, source markup and
installed export/sort controls. The app overrides a deliberately disabled export
guard; the launcher also forces it over an unsafe environment value.

Local Windows Python 3.12 targeted verification passed **87 tests in 156.62s**.
The affected UI check passed again in 7.78s after grouping metadata panels and
adding the explicit unsafe-export-setting assertion. Pure filter/identity tests
take under one second. An earlier sandbox run passed 32 pure cases, then Windows
blocked AppTest's internal loopback wakeup socket (WinError 10013) and temp cleanup.
The permitted outside-sandbox targeted retry passed; the suite's DNS/external/
arbitrary-loopback network block was retained. No test assertion was weakened.
Ruff and board/whitespace checks pass. The full hosted regression gate is pending;
targeted verification is not a full-suite/all-platform pass.

Actual ML-130 review `4e2ebe46423d4f56aab999d7d9eb3a37` loaded through both the
service and AppTest. Dynamic views are **15 focused, 49 outside PILT/exempt,
62 prior-year, 13 special-review, 291 current-year, 311 distinct union, 42 overlap**.
The floor is ten acres; 11 union parcels have unknown improvement values. Listing
publication remains October 13 and GIS capture October 16, not a new tax update.
It is not synthetic and no active hold is recorded. The actual UI test exercised
keyboard selector/summary, exact service sort, pagination, current view and stable
snapshot/parcel identity. Acquisition/replay/reimport/latest calls were prohibited.
It passed in **10.41s**; it is AppTest, not a browser/clipboard/zoom/screen-reader
audit. Full evidence links/details and contextual exports remain ML-204/205;
actual browser accessibility release checks remain ML-206.

All **856** baseline saved county/audit/comparison files retained sizes/SHA-256
after the checks. Only the existing viewer's active `server.log`/`server-error.log`
were excluded. The new private baseline/check helper live outside completed runs
under `data/processed/isanti/preparation/ml-203-2026-10-17/` and stay ignored. No
county request, raw/source/result rewrite, correspondence upload, canonical tax
meaning change or monetary resolution occurred. The user approved restarting the
identified local viewer after verification; restart/health evidence is pending.
