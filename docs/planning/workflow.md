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

1. ML-130: prepare genuinely eligible real county inputs through an agreed
   recovery/reacquisition route; do not retrofit completion evidence into legacy
   files. This is Ready, not started or authorized by the discovery alone.
2. ML-202: implement the thin review service, optional Streamlit selector shell
   and clear validated/legacy/error states. It can proceed against fixtures
   independently of ML-130 when implementation is selected.
3. ML-124: validate refresh/difference behavior without inferring payment from
   disappearance. ML-203/204 then add tables/details, ML-205 exports, ML-206 packaging.

ML-201 is Done: [the UI decision](../ui-plan.md) selects Streamlit and maps U01-U12
workflow/accessibility/data-safety examples to implementation cards. No framework
was installed or app built. ML-130 is a real-data handoff gate for ML-206; a
fixture-only empty shell cannot count as usable actual county review.

ML-123 is Done: [explicit snapshot selection/replay](../replay.md) passed 645
offline tests in all four hosted Windows/Linux jobs. Historical pre-completion
inputs remain unverified and were not reimported. Source-date differences, holds
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
