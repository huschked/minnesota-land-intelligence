# Kanban workflow

## Where work is tracked

- [Roadmap](../roadmap.md): phase outcomes and intended sequence.
- [Kanban board](kanban.md): generated swimlanes with cards in workflow columns.
- [Backlog](backlog.md): authoritative epic/story definitions and status.

This is a repository-based Markdown board, not a hosted project-management service
or a drag-and-drop application. Files stay with the project and need no external
account. A future migration to GitHub Projects, Linear, or another tracker should
retain the IDs, acceptance criteria, evidence, and dependency graph and choose one
authoritative tracker rather than maintaining two independently edited status lists.

## Status and priority

| Status | Meaning | Exit condition |
|---|---|---|
| Backlog | Captured, but not selected/refined or dependencies remain unfinished. | Meets Definition of Ready and is selected for the near-term queue. |
| Ready | Clear, bounded, and all recorded story dependencies are Done. | Assign an owner and pull into active work. |
| In Progress | Someone is actively implementing, checking, or reviewing it. | Acceptance checks and Definition of Done pass, or an actual blocker is recorded. |
| Blocked | A concrete dependency outside the implementer's current control prevents completion. | Record the resolving evidence, reassess dependencies, and move to Ready or In Progress. |
| Done | The stated behavior or discovery outcome is completed with evidence. | Reopen only for a regression or incomplete acceptance criterion; new scope gets a new card. |

Ready does not authorize all future implementation. This task creates the plan.
Future work is selected within the user's requested milestone and AGENTS.md scope;
especially Phase 2, external outreach, and deployment must not begin merely because
a card exists. Do not add an extra approval step for routine work already authorized.

Priority is independent of status and is not a deadline:

- **P0:** could misstate facts, lose provenance, corrupt results, or double-count money.
- **P1:** required for reliable delivery or the next usable milestone.
- **P2:** subsequent capability or refinement after its prerequisites.

Epic state is rolled up: Complete when every story is Done; Active when some
delivery has occurred or a story is In Progress; otherwise Backlog. A Ready
discovery card alone does not mean its future epic has started implementation.

## Pull policy and work-in-progress limits

Default for this small project: **one implementation/discovery story In Progress**.
One additional story may be undergoing final verification/review, for a maximum of
two active stories when that genuinely helps delivery. Record an exception and
owner before exceeding that limit. Blocked stories are visible in their own column
and do not consume implementation WIP, but are reviewed before another pull.

Assign one accountable owner when pulling a story; contributors can be listed in
notes. Unassigned is deliberate until someone takes responsibility. No estimates,
dates, staff assignments, or sprints are invented for the long-term backlog.

Suggested near-term order:

1. ML-305 is Ready and recommended next: define the explicit preliminary mapped-
   constraint union/remaining-acre policy, preserving compatible geometry, source
   dates and null/held results. Not automatically started. ML-303/304 screens are
   Done; ML-306 retains official-map validation/integration and review of the
   neighboring not-printed panel holds and numerical residual. No scope extends
   to legal buildability, source-data redistribution, UI changes or scoring.
   County accounting/identity blockers ML-117/121/122 remain separate; no verified
   financial ranking, legal buildability or owner outreach is authorized here.

ML-304 is Done, owner Codex, 2026-10-19. [Effective FEMA observations](../floods.md)
pin the same 15-parcel geometry into a separate dated run. Native geographic
datum alignment, AOI rather than county filtering, exact memberships, independent
study/panel/zone coverage and raw/spatial dates are verified. Nine parcels have
numeric results (eight SFHA-positive, one mapped zero); six remain conservatively
held for neighboring not-printed panel contexts, one also with a tiny processing
residue. They do not establish absent Isanti coverage or a physical gap; ML-306
tracks review. No unknown is turned into zero. All 2,323 baseline files and the
old wetland results are unchanged/reproducible. Final Linux 3.11/3.12 jobs passed
all 1,125 offline cases; new/affected Windows cases passed locally. Slow hosted
Windows jobs were cancelled under the user's established preference after Linux
success; the workflow is cancelled and unchanged gate failed, not a four-platform
pass. No remaining acres, tax refresh, UI/server or legal/insurance conclusion.
See [dated evidence](../testing.md#ml-304-effective-floodplain-overlap).

ML-303 is Done, owner Codex, 2026-10-19, with the explicit user-approved hosted
Windows cancellation exception. The [wetland screen](../wetlands.md) covers all
15 focused parcels using 80 DNR NWI features and independent ECMN coverage;
2010 imagery/2013 delivery is not 2026 imagery. The audited county bridge uses
an actual pinned NOAA grid and visually checked historical MnDOT controls;
unknown/partial coverage or classifications remain held/null. Both saved policy
versions reproduce offline and all 1,177 baseline files are unchanged. All 1,020
offline tests passed on Linux 3.11/3.12 and all 77 new cases locally on Windows.
After Linux success, hosted Windows jobs were cancelled as requested; the
implementation workflow is cancelled and the unchanged gate failed. This is
not a full Windows pass. No UI/server, tax balance, flood, usable acres or score
change is included. See [dated evidence](../testing.md#ml-303-mapped-wetland-overlap).

ML-302's geometry operation is isolated from saved tax/attribute runs and viewer
processes. It preserves native true-curve responses, holds unsupported/invalid
geometry without repairs, checks exact parcel/OID membership and produces
same-adjusted-datum local equal-area observations separately from deeded acres.
No ordinary NAD83/UTM relabeling or ballpark datum substitution is approved.
The actual service lacks an edit token: matched inventories are not an atomic
snapshot guarantee. All 871 retained baseline files are unchanged. ML-303/304
must resolve their actual datum operations and data coverage before any overlay
result; inability to do so is a hold, never zero overlap.

ML-302 is Done, owner Codex, 2026-10-18. All 943 offline tests passed on Linux
3.11/3.12 and Windows 3.11; Windows 3.12 reached the existing ten-minute job
limit after 911 passes, leaving 32 cases uncompleted and the CI gate red. The
user explicitly accepted this disclosed coverage limitation and asked to skip
more Windows runs. New geometry cases passed locally on Windows 3.12. This is
an explicit verification exception, not a fourth full-matrix pass or weakened gate.
See [dated evidence](../testing.md#ml-302-parcel-polygon-foundation).

ML-301 is Done: [the source comparison/contract](../suitability-sources.md) selects
DNR NWI/project footprints and FEMA effective NFHL with coverage/panel/revision
context. Bounded live metadata/samples and an offline raw-hash audit establish a
retrieval contract, not actual parcel enrichment. County flood polygons are
comparison-only; dates, classifications, coverage and use/redistribution uncertainties
remain explicit. A year-8888 FEMA date is retained as invalid, not repaired to today.
All 871 retained baseline files are unchanged. No dependencies, runtime/tests,
viewer, overlays or tax-data updates were introduced. E04 is Active, not complete.

ML-206 is Done and E03 is Complete as a bounded local release. The
[dated browser checklist](../reviews/local-viewer-release-2026-10-17.md) records
fresh short-path installation, actual-data counts/keyboard/native downloads,
clipboard guard, isolated held/empty/refusal states and user-confirmed 200% zoom.
It distinguishes browser evidence from AppTest, records untested screen-reader/
conformance behavior and tool/session limitations, and preserves all 871 baseline
saved files. Runtime/tests/pins are unchanged; documentation-only fast CI is not
a new Windows full-matrix claim. The main approved viewer remains loopback-only.

ML-205 is Done: [contextual CSV/JSON worklists](../worklist-exports.md) include explicit
filtered/selected previews, all-page distinct ordering, source/year/filter context,
unknown balances and separate snapshot-wide issues. Downloads revalidate on click
and reject changed/revoked/oversized evidence. CSV text protection and its re-save
limitations are disclosed; JSON keeps canonical values/nulls. All 840 offline tests
passed in each hosted Windows/Linux x Python 3.11/3.12 job after fixing an existing
date-dependent fixture clock (production rules unchanged). Actual-data exports and
862-file preservation passed; the approved project-only viewer restart is healthy
and loopback-only. ML-206 subsequently completed the bounded browser release
checks described above, with user-confirmed zoom and explicit accessibility limits.

ML-204 is Done: [parcel source evidence](../viewer.md#inspect-source-evidence-ml-204)
adds revalidated immutable details, every contributing listing row, confirmed year
distinctions, separate owners, unknown balances and strictly validated county links.
All 803 offline cases passed in each hosted Windows/Linux x Python 3.11/3.12 job.
Actual-data detail/back/reload passed; 859 baseline saved files remain unchanged.
Only the verified project viewer was restarted after approval and is loopback-only
and healthy. No county/report request, debt calculation, suitability score, source
edit or historical sample substitution occurred. ML-205 was subsequently completed,
as recorded above.

ML-203 is Done: [the viewer](../viewer.md) now has saved candidate tables, exact
service filters/sorts, dynamic distinct counts, pagination and a labelled keyboard
parcel-summary path. All 758 offline tests passed in each of four hosted platform/
Python jobs. Actual-data AppTest computed the existing 15/49/62 views and the
311-parcel distinct prior/current union, preserving all 856 baseline saved files
checked. The user-approved viewer restart is loopback-only and healthy. Full
source-evidence details, contextual exports and browser/a11y release QA remain
ML-204/205/206, not completed by this card.

ML-124 is Done: [saved snapshot comparisons](../snapshot-comparison.md) preserve
added/changed/missing observations, source dates, holds and explicit freshness
policy without payment or split/retirement inference. All 713 offline tests passed
on four hosted platform/Python combinations. The actual-data identical-replay
control reports 871 unchanged IDs; no fresh tax balance or county request occurred.

ML-201 is Done: [the UI decision](../ui-plan.md) selects Streamlit and maps U01-U12
workflow/accessibility/data-safety examples to implementation cards. No framework
was installed or app built by that discovery. ML-202 is now Done: [the selector](../viewer.md)
loads explicit validated snapshots through an independent service, with optional
Streamlit 1.66.0, read-only overview/error states and loopback-only startup. All
687 offline tests passed on four hosted platform/Python combinations; actual
ML-130 inputs also loaded through AppTest without modifying saved data. This is
not yet the table/detail/export or browser accessibility release. ML-130 is Done: [actual preparation evidence](../reviews/isanti-viewer-preparation-2026-10-16.md)
records new eligible GIS/file/join/review inputs, an identical offline replay and
190 unchanged historical files. The 62/49/15 views match historical parcel IDs,
but tax amounts and new manual verification remain unresolved. ML-206 subsequently
checked that actual-data workflow; a fixture-only empty shell did not count as usability.

ML-123 is Done: [explicit snapshot selection/replay](../replay.md) passed 645
offline tests in all four hosted Windows/Linux jobs. Historical pre-completion
inputs remain unverified and were not reimported by that implementation. ML-130
subsequently recaptured exact listing bytes into separate new runs. Source-date differences, holds
and missing historical fingerprints are disclosed; no completion evidence is
manufactured. The viewer discovery should explicitly account for that data boundary.

ML-117, ML-121, and ML-122 wait for actual county information. They do not block
basic exploration of the existing factual shortlist, but verified financial
comparisons remain dependent on their acceptance criteria. No unsolicited county
messages or reminders are created by this board.

ML-129 is Done: [test performance](../test-performance.md) records the measured
speedup, targeted development commands, conservative fast/full CI selection and
passing 616-test full Windows/Linux matrix. No repeated full Windows run is needed
for documentation-only completion evidence; fast coverage is disclosed as Linux-only.

## Definition of Ready

Before a card moves to Ready:

- Its user outcome and scope are clear, with at least two observable acceptance checks.
- It is small enough for a focused change; split large stories and preserve links
  to the parent outcome instead of pulling an entire future epic at once.
- Required authoritative sources and access constraints are identified. If source
  availability/meaning is unknown, use a bounded discovery spike first.
- Every recorded story dependency is Done; there is no unrecorded blocker.
- Data/model changes have a validation plan, including nulls, duplicates, failure
  cases, dates, and numerical tolerances where relevant.
- External services, dependencies, migration effects, and user-facing limitations
  are understood enough to avoid accidental scope expansion.

Spikes finish with findings, source references, a decision or explicit unresolved
question, and bounded follow-up stories. A failed source-discovery outcome can
still finish a spike if its acceptance criteria required investigation, not a
guaranteed source; do not mark an unimplemented feature Done as a result.

## Definition of Done

Every applicable item must hold:

- Acceptance criteria are checked and the user outcome works on representative inputs.
- County-specific meaning stays in adapters. Monetary calculations use verified
  inputs and Decimal; unknowns remain unknown; AI does not become a fact source.
- Raw responses, source dates, mapping/version references, and important derived
  values remain traceable. Existing snapshots and unrelated user edits are preserved.
- Relevant tests/checks pass, including required ingestion/normalization fixtures.
  Normal tests do not need live government APIs; live checks are explicit and dated.
- Run affected tests during development, then a full regression at the implementation
  boundary. Rerun affected checks for later code edits; do not repeat unchanged full
  suites for documentation-only completion commits. Record actual revision/platform
  coverage, not a Windows pass for Linux-only fast CI. Follow [test performance](../test-performance.md).
- Source/algorithm changes include boundary, missing, duplicate, and malformed-data
  checks. Spatial/financial results state their units and tolerances.
- User-visible changes have relevant workflow/accessibility checks; a discovery
  document is reviewed against its requested outcome instead of receiving artificial
  unit tests.
- Documentation and the board are updated. Evidence links identify code, sources,
  outputs, and test/validation results without claiming unperformed checks.
- New runtime dependencies have a reason, and any publication/data exposure or
  external write is within the user's authorization.
- The feature does not claim legal buildability, seller motivation, sensitive
  personal characteristics, or current paid status unsupported by evidence.

Historical Done cards are based on current implementation and recorded evidence,
not a claim of independent review or deployment. ML-120 establishes the first local
Git baseline. ML-118 subsequently passed 72 default offline tests locally and in
four hosted Windows/Linux x Python 3.11/3.12 jobs, with lint and board validation.
ML-125 then passed 283 offline tests on each of the same four hosted jobs,
including real symlink containment checks; its local account skipped that one
privilege-dependent case. ML-126 subsequently passed 468 offline tests with no
skips in each hosted matrix job. ML-127 passed 539 offline tests with no skips in
each of the four hosted jobs. The live government-service test was collected
but not executed. See
[testing evidence](../testing.md) and [reproducibility](../reproducibility.md) for
verification and the separate backup requirements for ignored county data.

## Updating the board

Edit story fields in `backlog.md`, retain stable IDs, and update its `Updated:`
date. Add links to any new child cards. Update the epic state if its rollup changes.
Keep dependencies explicit and acyclic. For a blocked card, record the concrete
missing input and how it will be resolved, not simply "waiting".

Generate the view with the local project interpreter:

```powershell
.\.venv\Scripts\python.exe scripts/render_kanban.py
.\.venv\Scripts\python.exe scripts/render_kanban.py --check
```

The renderer checks unique IDs, required fields, acceptance checks, legal
statuses/priorities, evidence on Done cards, explicit blockers, dependency existence,
dependency cycles, Ready/Done prerequisites, epic rollups, and generated-board drift.
It does not certify source semantics or actually execute story acceptance tests.

Review Ready order and blockers at each work session; reconcile completed work
before selecting the next card. Keep canceled/replaced IDs as historical references
or explicit links rather than silently reusing them for different work. Append a
new story for a defect or scope change and revise dependent criteria as needed.
