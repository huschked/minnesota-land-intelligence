# Epics and story backlog

Updated: 2026-10-17. This is the authoritative source for story status, priority, dependencies, acceptance criteria, and completion evidence. The [Kanban board](kanban.md) is generated from this file. The [workflow](workflow.md) explains how to maintain both.

The project has a working local CLI and [read-only viewer](../viewer.md) with explicit snapshot selection, filtered parcel tables and source-evidence details/links (ML-202/203/204). Contextual exports and final browser/accessibility packaging remain ML-205/206; no deployed service or acquisition recommendation is implied. [ML-130 preparation](../reviews/isanti-viewer-preparation-2026-10-16.md) created eligible new runs from October 16 GIS plus the unchanged October 13 listing: 62 large prior-year parcels, 49 outside PILT/exempt and a 15-parcel focused view, with identical historical parcel IDs and unknown canonical balances. The reliability/replay stories themselves did not regenerate those results. ML-123 passed 645 offline tests in each of four hosted Windows/Linux, Python 3.11/3.12 jobs; the live integration test was collected but not executed. Historical pre-completion runs remain legacy/unverified, not deleted, certified or automatically selected. ML-123 implements [explicit replay for completed version-2 inputs](../replay.md). See [validation](../validation.md), [retrieval](../retrieval.md), [publication](../publication.md), and [testing evidence](../testing.md). Historical retained results: [corrected review](../reviews/isanti-prior-year-results-2026-10-14.md).

Completed cards describe implemented workspace behavior. ML-120 establishes the first local Git baseline; a separately authorized follow-up connects the private GitHub code repository described in [reproducibility](../reproducibility.md). Ignored county data is not backed up there, and no deployment is configured. Unknown owners, estimates, and due dates are deliberately unassigned.

All stories inherit the shared Definition of Ready/Done in [workflow.md](workflow.md). Future acceptance criteria are planned requirements, not existing capabilities. Creating this backlog does not authorize starting later phases, contacting people, publishing data, installing future stacks, or deploying services.

## E01 - Phase 1 - County parcel ingestion

<a id="e01"></a>

**Epic state:** Complete

**Goal:** Retrieve and normalize authoritative Isanti parcel data with auditable outputs.

**Exit criteria:** Existing CLI retrieval, raw retention, normalization, guarded filters, CSV/JSON exports, and offline tests remain working.

**Owner:** Unassigned; assign a responsible owner when a story is pulled. Epic state is rolled up from story status, not a separate delivery promise.

### ML-001 - Repository foundation and county adapter boundary

<a id="ml-001"></a>

**Status:** Done

**Priority:** P1

**Kind:** Story

**Depends on:** None

**User outcome:** As a developer, I can extend a county adapter without placing county field names in core business rules.

**Acceptance criteria:**

- [x] Repository configuration, root AGENTS.md, and architecture/roadmap documents exist.
- [x] County adapter and canonical parcel/source models are implemented.

**Validation:** Existing implementation/evidence below supports this historical completion; shared regression requirements continue to apply.

**Notes:** Existing architecture; not a claim that Git commits or CI already exist.

**Evidence / starting points:** [1](../../AGENTS.md), [2](../../src/mn_land/counties/base.py)

### ML-002 - Inspect and document official Isanti schema

<a id="ml-002"></a>

**Status:** Done

**Priority:** P0

**Kind:** Story

**Depends on:** ML-001

**User outcome:** As a researcher, I can trace mappings to authoritative metadata.

**Acceptance criteria:**

- [x] Official service/layer, field aliases, geometry/CRS, and pagination capabilities are recorded.
- [x] TOTPRVTXTOD is retained with cautious semantics and cannot independently verify delinquency.

**Validation:** Existing implementation/evidence below supports this historical completion; shared regression requirements continue to apply.

**Notes:** Re-check this contract on future schema changes.

**Evidence / starting points:** [1](../counties/isanti.md), [2](../../src/mn_land/counties/isanti/mappings.py)

### ML-003 - Retrieve all parcel pages and preserve raw responses

<a id="ml-003"></a>

**Status:** Done

**Priority:** P0

**Kind:** Story

**Depends on:** ML-002

**User outcome:** As an operator, I can retrieve a complete observed parcel count and retain source pages.

**Acceptance criteria:**

- [x] Ordered pagination, duplicate object-ID detection, count reconciliation, and useful errors exist.
- [x] Raw response pages and metadata are retained in unique run directories.

**Validation:** Existing implementation/evidence below supports this historical completion; shared regression requirements continue to apply.

**Notes:** Service mutation, retry policy, and schema-drift hardening remain in ML-119.

**Evidence / starting points:** [1](../../src/mn_land/ingestion/arcgis.py), [2](../../tests/unit/test_pagination.py)

### ML-004 - Normalize parcel attributes and unknown values

<a id="ml-004"></a>

**Status:** Done

**Priority:** P0

**Kind:** Story

**Depends on:** ML-002

**User outcome:** As a researcher, I can compare parcel attributes without silently converting missing values to zero.

**Acceptance criteria:**

- [x] Money and acreage use Decimal, and missing values remain null.
- [x] Owner/address, classifications, legal description, and source lineage have fixture coverage.

**Validation:** Existing implementation/evidence below supports this historical completion; shared regression requirements continue to apply.

**Notes:** Geometry is optional; no spatial analysis is claimed.

**Evidence / starting points:** [1](../../src/mn_land/counties/isanti/adapter.py), [2](../../tests/unit/test_isanti_adapter.py)

### ML-005 - Separate acreage and verified-tax filtering

<a id="ml-005"></a>

**Status:** Done

**Priority:** P0

**Kind:** Story

**Depends on:** ML-004

**User outcome:** As a researcher, I can configure minimum acreage while preserving the tax verification gate.

**Acceptance criteria:**

- [x] Filtering operates on canonical models with explicit rejection reasons.
- [x] Acreage boundaries, missing tax/acreage, and unverified tax semantics are tested.

**Validation:** Existing implementation/evidence below supports this historical completion; shared regression requirements continue to apply.

**Notes:** The independent delinquency path is tracked under E02.

**Evidence / starting points:** [1](../../src/mn_land/filtering/candidate_filter.py), [2](../../tests/unit/test_candidate_filter.py)

### ML-006 - Deliver CLI statistics and CSV/JSON outputs

<a id="ml-006"></a>

**Status:** Done

**Priority:** P1

**Kind:** Story

**Depends on:** ML-003, ML-005

**User outcome:** As an operator, I can run the workflow and locate its results and validation counts.

**Acceptance criteria:**

- [x] CLI commands, output paths, normalization failures, and filter statistics are available.
- [x] CSV/JSON and a deterministic review sample can be generated without fabricated records.

**Validation:** Existing implementation/evidence below supports this historical completion; shared regression requirements continue to apply.

**Notes:** The original Phase 1 compatibility exports are not the corrected prior-year shortlist.

**Evidence / starting points:** [1](../../src/mn_land/cli.py), [2](../../src/mn_land/export/exporters.py)

### ML-007 - Establish tests and operator documentation

<a id="ml-007"></a>

**Status:** Done

**Priority:** P1

**Kind:** Story

**Depends on:** ML-006

**User outcome:** As a maintainer, I can test the foundation and follow setup/run instructions.

**Acceptance criteria:**

- [x] Fixtures cover normalization, nulls, filtering, pagination, duplicates, and HTTP failures.
- [x] An explicit live source-validation command and integration marker exist.

**Validation:** Existing implementation/evidence below supports this historical completion; shared regression requirements continue to apply.

**Notes:** Default offline test selection and hosted CI were subsequently completed in ML-118; this card retains the original live-check boundary.

**Evidence / starting points:** [1](../../tests/unit/test_http.py), [2](../../README.md)

## E02 - Phase 1.1 - Authoritative delinquency integration and reliability

<a id="e02"></a>

**Epic state:** Active

**Goal:** Identify listed prior-year unpaid taxes independently of ambiguous GIS tax fields and preserve financial unknowns.

**Exit criteria:** Current/prior-year classification and lineage are reproducible, hardening stories pass, and county-dependent accounting/identity questions are resolved or explicitly accepted as limitations before closing this epic.

**Owner:** Unassigned; assign a responsible owner when a story is pulled. Epic state is rolled up from story status, not a separate delivery promise.

### ML-110 - Canonical delinquency records and explicit statuses

<a id="ml-110"></a>

**Status:** Done

**Priority:** P0

**Kind:** Story

**Depends on:** ML-004

**User outcome:** As a researcher, I can distinguish source-backed prior-year status, current-year overdue amounts, unknowns, and ambiguous identities.

**Acceptance criteria:**

- [x] Independent DelinquencyRecord/DelinquencySource types and explicit verification statuses exist.
- [x] Missing names, years, and balances remain unknown rather than fabricated defaults.

**Validation:** Existing implementation/evidence below supports this historical completion; shared regression requirements continue to apply.

**Notes:** Does not imply aggregate balances are known.

**Evidence / starting points:** [1](../../src/mn_land/models/delinquency.py), [2](../../src/mn_land/delinquency/base.py)

### ML-111 - Inspect and import CSV/XLSX through reviewed mappings

<a id="ml-111"></a>

**Status:** Done

**Priority:** P0

**Kind:** Story

**Depends on:** ML-110

**User outcome:** As an operator, I can inspect a county file before applying an explicit mapping.

**Acceptance criteria:**

- [x] Inspection reports columns and tentative suggestions without auto-accepting semantics.
- [x] CSV/XLSX ingestion, required-column validation, and useful import errors have tests.

**Validation:** Existing implementation/evidence below supports this historical completion; shared regression requirements continue to apply.

**Notes:** PDF input is not implemented; use a source-discovery spike if needed later.

**Evidence / starting points:** [1](../../src/mn_land/delinquency/file_loader.py), [2](../../tests/unit/test_delinquency_file.py)

### ML-112 - Exact parcel-ID joins and unmatched review

<a id="ml-112"></a>

**Status:** Done

**Priority:** P0

**Kind:** Story

**Depends on:** ML-111

**User outcome:** As a researcher, I can join known Isanti identifier formats without fuzzy matching.

**Acceptance criteria:**

- [x] Original IDs, punctuation-normalized keys, and source rows are preserved.
- [x] Duplicate GIS identities and unmatched source records remain visible.

**Validation:** Existing implementation/evidence below supports this historical completion; shared regression requirements continue to apply.

**Notes:** Resolving the five unmatched IDs is ML-121.

**Evidence / starting points:** [1](../../src/mn_land/counties/isanti/delinquency.py), [2](../../src/mn_land/delinquency/join.py)

### ML-113 - Apply county-confirmed assessment/payable-year rules

<a id="ml-113"></a>

**Status:** Done

**Priority:** P0

**Kind:** Story

**Depends on:** ML-111

**User outcome:** As a researcher, I can separate unpaid prior years from overdue first-half 2026 installments.

**Acceptance criteria:**

- [x] TAXYR is the report assessment year; ASMTYR is each charge assessment year; payable year is assessment year plus one.
- [x] Missing/malformed/future row years fail validation and replay uses the report year, not today's date.

**Validation:** Existing implementation/evidence below supports this historical completion; shared regression requirements continue to apply.

**Notes:** The earlier comparison to the wrong payable-year column is superseded.

**Evidence / starting points:** [1](../counties/isanti-tax-year-confirmation.md), [2](../../tests/unit/test_isanti_tax_periods.py)

### ML-114 - Preserve immutable imports and county evidence

<a id="ml-114"></a>

**Status:** Done

**Priority:** P0

**Kind:** Story

**Depends on:** ML-111, ML-113

**User outcome:** As an auditor, I can identify which file, mapping, and county explanation produced a result.

**Acceptance criteria:**

- [x] Timestamped original imports, mappings, supporting documents, and hashes are retained.
- [x] Important normalized values retain source fields and original row references.

**Validation:** Existing implementation/evidence below supports this historical completion; shared regression requirements continue to apply.

**Notes:** Exact code/config version pinning and replay are ML-120 and ML-123.

**Evidence / starting points:** [1](../../src/mn_land/delinquency/pipeline.py), [2](../counties/isanti-tax-year-confirmation.md)

### ML-115 - Export separate tax-period views with multi-row lineage

<a id="ml-115"></a>

**Status:** Done

**Priority:** P0

**Kind:** Story

**Depends on:** ML-112, ML-113, ML-114

**User outcome:** As a researcher, I can examine prior-year candidates without mixing current-year installments into their count.

**Acceptance criteria:**

- [x] Corrected snapshot exports 62 large prior-year parcels and 291 large current-year parcels, with 42 overlapping IDs.
- [x] Multiple authoritative prior-year rows establish presence; every row is retained and no unverified amounts are summed.

**Validation:** Existing implementation/evidence below supports this historical completion; shared regression requirements continue to apply.

**Notes:** These are October 2026 snapshot counts, not permanent county facts.

**Evidence / starting points:** [1](../../src/mn_land/delinquency/exporters.py), [2](../reviews/isanti-prior-year-results-2026-10-14.md)

### ML-116 - Create land-review subsets and corroborate a report sample

<a id="ml-116"></a>

**Status:** Done

**Priority:** P1

**Kind:** Story

**Depends on:** ML-115

**User outcome:** As a researcher, I can review land-focused records with visible evidence and limitations.

**Acceptance criteria:**

- [x] 49 parcels outside PILT/exempt classifications and a 15-parcel land-focused view are exported.
- [x] Ten sampled official reports corroborate acreage and an outstanding listed prior payable year; older years outside the report window remain unknown.

**Validation:** Existing implementation/evidence below supports this historical completion; shared regression requirements continue to apply.

**Notes:** The check does not verify all balances, all 62 parcels, or legal buildability.

**Evidence / starting points:** [1](../reviews/isanti-prior-year-results-2026-10-14.md), [2](../../src/mn_land/counties/isanti/review.py)

### ML-117 - Obtain and document county monetary-field definitions

<a id="ml-117"></a>

**Status:** Blocked

**Priority:** P0

**Kind:** Story

**Depends on:** ML-113

**User outcome:** As a researcher, I need verified accounting definitions before using balances in financial analysis.

**Acceptance criteria:**

- [ ] County evidence defines TAXAMT, TAXONLYAMT, SPAAMT, PENAMT, INTAMT, FEEAMT, TOTAMT, and the *2 fields, including payment treatment and effective dates.
- [ ] A reviewed mapping separates tax, penalty, interest, fees, assessments, and unknown components without guessing.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Blocker:** Blocker: awaiting county accounting clarification. Owner unassigned; user provides correspondence. No outbound message is authorized by this card.

**Evidence / starting points:** [1](../reviews/isanti-county-questions-2026-10-14.md)

### ML-118 - Make normal tests offline by default and add CI

<a id="ml-118"></a>

**Status:** Done

**Owner:** Codex

**Priority:** P1

**Kind:** Chore

**Depends on:** ML-007

**User outcome:** As a maintainer, I can run normal tests without contacting government services.

**Acceptance criteria:**

- [x] Default pytest selection excludes live integration tests; an explicit integration command still works.
- [x] A CI configuration for the selected repository host runs lint and offline tests on supported Python with sanitized fixtures.

**Validation:** 72 default offline tests passed locally and in all four Windows/Linux x Python 3.11/3.12 jobs. Hosted dependency, Ruff, and Kanban checks passed. Isolated sentinel suites prove default/explicit selection; real integration collection selected one live test without running it. Hosted run 38673156552 succeeded for implementation commit 44114fc.

**Notes:** Default options exclude integration and enforce registered markers. Unmarked tests block standard DNS/TCP calls. GitHub Actions runs on push/PR/manual dispatch with read-only token permissions and SHA-pinned official actions. No custom secrets, county-data upload, deployment, live-source test execution, branch-protection changes, or billing-setting changes.

**Evidence / starting points:** [Testing and hosted evidence](../testing.md), [workflow](../../.github/workflows/ci.yml), [pytest defaults](../../pyproject.toml), [selection/guard regression tests](../../tests/unit/test_test_policy.py), [network guard](../../tests/conftest.py), [successful hosted run](https://github.com/huschked/minnesota-land-intelligence/actions/runs/38673156552)

### ML-119 - Specify ingestion contracts and a bounded hardening plan

<a id="ml-119"></a>

**Status:** Done

**Owner:** Codex

**Priority:** P0

**Kind:** Spike

**Depends on:** ML-003, ML-111

**User outcome:** As a maintainer, I can identify precise source and import failure cases before changing working ingestion.

**Acceptance criteria:**

- [x] Document required fields/types, known schema drift, file-format constraints, retry/page-limit expectations, and failure/partial-run behavior against current code.
- [x] Produce a prioritized fixture matrix and concrete changes for ML-125, ML-126, and ML-127, with no new county semantics inferred.

**Validation:** Inspected source modules and existing tests; compared retained August/October metadata (identical hashes, no observed field drift); reproduced D01-D08 using synthetic offline probes. Existing 72 offline tests, Ruff, board validation, and 213 local documentation links/anchors passed; one live test was deselected. Reviewed the contract, evidence inventory, and 24 F/H/R fixture groups against both acceptance criteria; no production ingestion changes or new county meanings. Hosted verification is linked to the completion commit's GitHub checks.

**Notes:** Discovery complete. Follow-up chain is ML-125 validation, then ML-126 retrieval/completeness, then ML-127 publication/read eligibility. Only ML-125 is Ready; future target guarantees are explicitly not existing capabilities. Monetary definitions and unmatched identities remain blocked on county evidence. No live government calls or original-input changes.

**Evidence / starting points:** [Contract and prioritized fixture matrix](../ingestion-contracts.md), [repeatable synthetic probe](../../scripts/probe_ingestion_contracts.py), [HTTP](../../src/mn_land/utils/http.py), [ArcGIS](../../src/mn_land/ingestion/arcgis.py), [file loader](../../src/mn_land/delinquency/file_loader.py)

### ML-120 - Establish version-control baseline and reproducible release identity

<a id="ml-120"></a>

**Status:** Done

**Owner:** Codex

**Priority:** P1

**Kind:** Chore

**Depends on:** ML-001

**User outcome:** As a maintainer, I can associate generated results with recoverable code and dependency versions.

**Acceptance criteria:**

- [x] Review ignore rules and create the first tracked baseline without raw data, emails, secrets, or virtual environments.
- [x] Record code revision/version, dependency resolution, configuration, and artifact hashes for future runs; document clean-environment installation and recovery.

**Validation:** 66 offline tests passed in existing and fresh constrained environments, including provenance and mocked end-to-end ingestion; Ruff, dependency consistency, and CLI startup passed. See the reproducibility verification record. Live county tests were not rerun.

**Notes:** Initial baseline was local-only. The user subsequently authorized a private GitHub repository and code push; see the reproducibility guide. Actual runtime/source/configuration/input/output identity is recorded for future runs, not retroactively applied to historical snapshots. Constraints reproduce observed runtime/dev versions but do not hash-lock isolated build dependencies. Ignored county data still needs its own private backup.

**Evidence / starting points:** [Recovery and verification](../reproducibility.md), [identity helper](../../src/mn_land/provenance.py), [tests](../../tests/unit/test_provenance.py), [constraints](../../constraints-dev.txt), [ignore rules](../../.gitignore)

### ML-121 - Resolve unmatched account IDs and missing GIS identities

<a id="ml-121"></a>

**Status:** Blocked

**Priority:** P1

**Kind:** Story

**Depends on:** ML-112

**User outcome:** As a researcher, I need unmatched records reviewed without inventing acreage or identity.

**Acceptance criteria:**

- [ ] Document county/GIS explanations for five unmatched IDs, including prior-year ID 050080500, and the two features lacking parcel IDs.
- [ ] Apply only authoritative crosswalks with validity dates; retain unresolved records, row counts, and reasons in exports and tests.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Blocker:** Blocker: county/GIS identity information. TaxDistribution presence alone does not establish parcel geometry or acres.

**Evidence / starting points:** [1](../reviews/isanti-review-2026-10-14.md), [2](../reviews/isanti-prior-year-results-2026-10-14.md)

### ML-122 - Resolve repeated charge rows and calculate verified balances

<a id="ml-122"></a>

**Status:** Blocked

**Priority:** P0

**Kind:** Story

**Depends on:** ML-117

**User outcome:** As a researcher, I need a defensible parcel balance without counting an ownership join as multiple debts.

**Acceptance criteria:**

- [ ] County documentation establishes charge keys, owner-history behavior, separate years/components, and valid aggregation rules.
- [ ] Preserve every contributing row, distinguish identical repeats from distinct charges, and test reconciliation to official examples with Decimal arithmetic.
- [ ] Prior-year/current-year balances stay separate; conflicting or unsupported totals remain null with a reason.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Blocker:** Blocker: monetary and repeated-row specification from the county. Status presence can remain usable while balance aggregation is blocked.

**Evidence / starting points:** [1](../../src/mn_land/delinquency/join.py), [2](../../src/mn_land/delinquency/exporters.py)

### ML-123 - Add explicit snapshot selection and deterministic offline replay

<a id="ml-123"></a>

**Status:** Done

**Priority:** P1

**Kind:** Story

**Depends on:** ML-120, ML-125, ML-126, ML-127

**User outcome:** As an operator, I can reproduce a chosen result without silently selecting newer GIS data.

**Acceptance criteria:**

- [x] CLI accepts explicit parcel/import snapshots, validates hashes and county/source compatibility, and records date differences.
- [x] Replaying retained inputs yields identical normalized content and candidate IDs apart from declared run metadata.
- [x] Failed or partial runs cannot become the latest usable snapshot; incompatible input dates are surfaced.

**Validation:** S01-S07 fixtures cover explicit input selection, moved folders with unavailable old roots, CSV/XLSX/captured limits, later execution dates, normalized fingerprints and all nine export byte comparisons, mixed periods/holds/unknowns, threshold overrides, source/date mismatches, failed/corrupt/legacy inputs and prior-success preservation. Local full suite: 643 passed, two Windows symlink-privilege skips, one live deselection. Hosted implementation `7a53fdbec6a902e770e926b4cbe9447533d69b38` passed 645 tests with no skips in each of four Windows/Linux x Python 3.11/3.12 jobs, plus dependency consistency, Ruff, board, live collection and CI gate. All 325 relative document targets passed. No government calls or original-data replay occurred.

**Notes:** Owner: Codex. Completed 2026-10-16 after local and full hosted verification. New imports can select an explicit completed parcel acquisition; replay accepts a completed join or raw parcel/import pair without acquisition/latest lookup/new raw writes. Captured dates/limits and holds remain effective; source differences are surfaced and unexpected content/export drift blocks publication. Same-platform moved-folder portability is verified; cross-OS replay is not claimed. Older complete version-2 joins can compare existing exports while missing historical normalized fingerprints remain unknown. Pre-completion legacy data remains read-only/unverified, with no completion backfill, invented inventories, migration, current-payment claim or original-data reimport. The actual retained county datasets still have no eligible new-protocol runs; a recovery/reacquisition choice remains separate work. ML-201 and ML-124 are Ready, not started.

**Evidence / starting points:** [Full hosted run 38955519528](https://github.com/huschked/minnesota-land-intelligence/actions/runs/38955519528), [commands and limits](../replay.md), [S01-S07 fixtures](../../tests/unit/test_snapshot_replay.py), [shared join/replay pipeline](../../src/mn_land/delinquency/pipeline.py), [reproducibility/date evidence](../../src/mn_land/replay.py), [testing](../testing.md)

### ML-124 - Validate refresh, stale-data, and changed-parcel behavior

<a id="ml-124"></a>

**Status:** Done

**Priority:** P1

**Kind:** Story

**Depends on:** ML-116, ML-123

**User outcome:** As a researcher, I can compare snapshots without treating disappearance from a list as proof of payment.

**Acceptance criteria:**

- [x] Tests cover report-year rollover, parcel splits/retired IDs, source holds, mixed prior/current rows, and stale evidence.
- [x] Refresh reports added/changed/missing records with source dates and preserves earlier results and unresolved statuses.

**Validation:** All 713 offline tests passed with no skips in every hosted Windows/Linux x Python 3.11/3.12 job at `1fe57b9ff3c549471dd6c664beaafe273358b971`; the live case was collected, not executed. The 26 new comparison cases and affected replay/publication/reader checks also passed locally. Actual-data control reports 871 unchanged IDs, validates under committed code, and preserves all 660 baseline files, excluding only active viewer logs. See [comparison behavior](../snapshot-comparison.md), [testing evidence](../testing.md) and [full CI](https://github.com/huschked/minnesota-land-intelligence/actions/runs/39041344103).

**Notes:** Owner: Codex. Completed 2026-10-17. Explicit offline comparison of compatible completed join graphs retains both evidence sets in a new immutable report. Listing/GIS/view changes stay separate; missing IDs do not imply payment, split/retirement relationships or availability. Freshness is a disclosed operator policy applied to source dates, not recapture time. No live acquisition, reimport, UI refresh button, historical certification, motivation score or scheduled job is included. The actual-data comparison is an identical-replay control, not independent tax observations. ML-203 is next recommended; later-phase cards do not start automatically and county accounting blockers remain unresolved.

**Evidence / starting points:** [1](../counties/isanti.md), [Comparison](../snapshot-comparison.md), [Fixtures](../../tests/unit/test_snapshot_diff.py), [Verification](../testing.md)

### ML-125 - Implement strict file and schema validation

<a id="ml-125"></a>

**Status:** Done

**Owner:** Codex

**Priority:** P0

**Kind:** Chore

**Depends on:** ML-119

**User outcome:** As an operator, I need malformed or incompatible inputs to fail before normalization can misstate facts.

**Acceptance criteria:**

- [x] Implement the adapter-owned GIS field/type gate and strict reviewed-mapping object/type/date/assertion checks in contract section 2; malformed metadata fails clearly and added unrequested fields remain permissible.
- [x] Enforce finite numeric/acreage inputs in parsers, CLI, and callable pipelines; reject numeric parcel-ID cells rather than coercing/padding, preserve nulls and finite negative accounting values, and retain explicit GIS row quarantines.
- [x] Validate CSV encoding/unique nonblank headers/exact widths/quoted multiline records and XLSX one-data-sheet/value-only rules; support exact typed year representations and preserve actual source row/sheet references across blank rows.
- [x] Enforce contained relative supporting-document paths without symlink escape or destination collision, clear malformed-file errors and workbook closure, and the documented input/expanded-archive/row/column/cell budgets.
- [x] Complete F01-F09 sanitized fixtures and valid-output regression checks without changing mixed-year status, holds, duplicate/monetary semantics, or production source bytes. Failed-input evidence/publication is integrated by ML-127, not silently claimed here.

**Validation:** F01-F09 and existing suite passed locally: 282 passed, one symlink-privilege skip, one live deselection. Hosted run 38678405055 for implementation commit c359a92 passed all four Windows/Linux x Python 3.11/3.12 jobs: 283 passed, no skips, one live deselection each, including real symlink coverage. Ruff, dependency/board checks and live collection passed. The reviewed mappings remain valid, new copies/hashes and source locations are tested, and 243 local documentation links/anchors were checked. No original county inputs were changed or live government tests executed.

**Notes:** Strict-input/schema work is implemented and documented. No HTTP retry/paging policy changes (ML-126), atomic publication/failure archiving (ML-127), portable replay (ML-123), or accounting inference. The existing discovery probe now reports corrected validation behavior while continuing to expose deferred D06-D08 gaps; those are not desired regression assertions. Windows local path checks required unsandboxed filesystem access, without weakening containment.

**Evidence / starting points:** [Implemented rules and F01-F09 test links](../validation.md), [contract](../ingestion-contracts.md), [strict loader](../../src/mn_land/delinquency/file_loader.py), [mapping/evidence](../../src/mn_land/delinquency/mapping.py), [tabular reader](../../src/mn_land/delinquency/tabular.py), [schema gate](../../src/mn_land/counties/isanti/schema.py), [successful hosted run](https://github.com/huschked/minnesota-land-intelligence/actions/runs/38678405055)

### ML-126 - Harden respectful HTTP retrieval and source completeness

<a id="ml-126"></a>

**Status:** Done

**Priority:** P0

**Kind:** Chore

**Depends on:** ML-119, ML-125

**User outcome:** As an operator, I can respect source capabilities and detect incomplete or changing data.

**Acceptance criteria:**

- [x] Call ML-125's schema gate, validate Query/OID/pagination/order capabilities and non-boolean counts, and clamp requested page size to valid advertised limits without guessing unsupported fallbacks.
- [x] Implement contract section 3's explicit transient/permanent retry classification, total-attempt/socket-timeout/wait budgets, sequential pacing, and delta/date Retry-After handling; stop rather than retry before an excessive server delay.
- [x] Reconcile initial/final count, OID inventories, fetched membership/order and page/transfer-limit behavior; reject detectable count/ID/schema/capability changes and disclose unknown same-ID attribute consistency when no edit token exists.
- [x] Retain bounded original HTTP bodies and parsed JSON evidence with hashes, wire effective Settings into transport, and complete H01-H08 fixtures with fake transport/clocks and no government calls or real sleeps.

**Validation:** H01-H08 implemented, including exact requests/waits/attempt/timeouts, body sizes/hashes, valid zero, short/multiple pages, drift and failure evidence. Local suite: 467 passed, one symlink-privilege skip, one live deselection. All four hosted Windows/Linux x Python 3.11/3.12 jobs passed 468 tests with no skips and one live deselection for implementation commit `92e7c687a78ec66c199ff9b31c9e7d1951c31eb2`. Dependency checks, Ruff, board and explicit live collection passed. No government requests; see [testing evidence](../testing.md).

**Notes:** Owner: Codex. Completed 2026-10-15 after local and hosted verification. ML-125's schema gate, effective Settings, bounded HTTP evidence/retries/pacing, start/end inventories and detectable source-change checks are wired together. No automatic cache substitution, alternate source, scraping, concurrency, scheduled refresh, point-in-time source guarantee, or new county semantics. Original county inputs/results remain unchanged. ML-127 owns completion/read eligibility and is now Ready.

**Evidence / starting points:** [Implemented retrieval rules and limitations](../retrieval.md), [Contract section 3 and H01-H08 matrix](../ingestion-contracts.md), [source fixtures H01-H05](../../tests/unit/test_retrieval_contract.py), [HTTP fixtures H06-H08](../../tests/unit/test_http_contract.py), [ArcGIS client](../../src/mn_land/ingestion/arcgis.py), [HTTP transport](../../src/mn_land/utils/http.py), [settings](../../src/mn_land/config/settings.py)

### ML-127 - Publish only complete processed runs

<a id="ml-127"></a>

**Status:** Done

**Priority:** P0

**Kind:** Chore

**Depends on:** ML-119, ML-125, ML-126

**User outcome:** As an operator, I can distinguish successful outputs from partially written or failed runs.

**Acceptance criteria:**

- [x] Implement contract section 4's distinct raw-complete/processed-complete stages and new versioned completion manifests; normalize exact retained input copies, use exclusive run identities, stage on the destination filesystem, and publish completion atomically only after inventory/hash/count checks.
- [x] Make status/latest/explicit parcel loads/imports/reviews share manifest kind/county/status/path/count/hash eligibility checks; staging, failures, tampered/missing files, and invalid newest directories cannot become usable results.
- [x] Preserve bounded failure diagnostics/raw evidence and exact source-row/quarantine accounting; do not double-count overlapping duplicate reviews or prior/current parcel views, aggregate unknown balances, or overwrite prior success.
- [x] Publish immutable per-run parcel outputs; any legacy flat compatibility files are non-authoritative. Preserve historical manifests unchanged, disclose legacy eligibility limitations, and leave portable replay/data backup to ML-123/ML-128.
- [x] Complete R01-R07 failure-injection, interruption, collision, legacy, reader, and successful empty-result fixtures across parcel/import/review paths, including the nine join exports and seven review CSVs.

**Validation:** R01-R07 implemented. Local release suite: 536 passed, two Windows symlink-privilege skips, one live deselection, plus the final boolean-counter fixture and bounded failure-location check passed separately. All four hosted Windows/Linux x Python 3.11/3.12 jobs passed 539 tests with no skips and one live deselection for implementation commit `1ac55f3c0e33257bef7128683aeb00077f0a5c6b`. Dependency checks, Ruff, board and explicit integration collection passed. No government requests. See [testing evidence](../testing.md).

**Notes:** Owner: Codex. Completed 2026-10-16 after local and hosted verification. Version-2 completion records/pointers, exact pinned sources, required artifact/hash/row reconciliation, bounded failure evidence and shared reader checks are implemented. Old flat exports and all historical county files remain unchanged; legacy inputs are not auto-certified. No new database, UI, remote backup, migration or power-loss guarantee. A complete raw acquisition is not automatically a successful processed run. ML-123 is now Ready.

**Evidence / starting points:** [Implemented publication protocol](../publication.md), [R01-R07 fixtures](../../tests/unit/test_run_publication.py), [shared validator/publisher](../../src/mn_land/runs.py), [content accounting](../../src/mn_land/run_checks.py), [contract section 4](../ingestion-contracts.md), [parcel pipeline](../../src/mn_land/ingestion/pipeline.py), [join pipeline](../../src/mn_land/delinquency/pipeline.py), [review](../../src/mn_land/counties/isanti/review.py), [CLI status](../../src/mn_land/cli.py)

### ML-128 - Back up and restore ignored raw data and correspondence

<a id="ml-128"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Chore

**Depends on:** ML-120

**User outcome:** As an operator, I can recover the authoritative inputs that Git intentionally excludes.

**Acceptance criteria:**

- [ ] Inventory raw snapshots, mappings, evidence, and correspondence; document retention, private backup location, access permissions, and checksum verification.
- [ ] Restore a representative snapshot into an isolated directory and reproduce its lineage checks without overwriting current data.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** Selecting a backup policy is part of this story; transmitting files to an external service requires separate user authorization.

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-129 - Shorten test feedback loops without weakening safety coverage

<a id="ml-129"></a>

**Status:** Done

**Priority:** P1

**Kind:** Chore

**Depends on:** ML-118, ML-127

**User outcome:** As a project owner, I get faster story delivery without silently losing data-integrity or Windows compatibility checks.

**Acceptance criteria:**

- [x] Capture a dated, commit-specific timing baseline separating setup, test execution, and CI waiting; report slowest test setup/call/teardown durations on Windows and Linux. Investigate repeated filesystem validation/fixture construction before attributing the slowdown to OneDrive, antivirus, or a particular function.
- [x] Document targeted development commands and a final full-regression gate, avoiding redundant full-suite runs on unchanged code while rerunning affected checks after follow-up edits. Documentation/board-only verification must be proportional to the change.
- [x] Implement a fast Linux routine CI path and explicit Windows/full-matrix triggers for filesystem-sensitive changes, milestone completion, scheduled runs, and manual dispatch. Document the reduced routine cross-platform coverage and ensure conditional/skipped jobs cannot be reported as executed passes or bypass configured required checks.
- [x] Optimize measured fixture overhead and bounded file-read bottlenecks without weakening production hash, path-containment, completion, provenance, or accounting validation. Benchmark a small parallel-worker configuration if justified; retain serial execution if isolation, reliability, or timing regresses, and justify any added development dependency.
- [x] Compare before/after timings on equivalent inputs and environments, report actual improvement and remaining bottlenecks without promising an unmeasured speed target, and verify the full offline suite on both Windows and Linux with intentional privilege-based skips disclosed. Keep live government tests opt-in and verify their selection by collection only.
- [x] Update testing/workflow documentation with exact fast/full commands, CI triggers, fallback instructions, and dated evidence. Preserve all historical county data and existing regression assertions; no blanket test deletion, permanent Windows removal, government calls, or deployment.

**Validation:** Identical 539-case local population: 537 passed, two symlink-privilege skips, one live deselection, 344.68 seconds before versus 75.36 seconds after; new reader/CI/provenance/test-policy targeted checks passed 92 cases. Hosted implementation revision `93f8dd7d0cfc3e0a2708f393954dc35228d1ad5c` passed 616 tests with no skips in each of four Windows/Linux x Python 3.11/3.12 jobs, plus dependency consistency, lint, board, explicit live collection and final CI gate. Hosted test times: Linux 9.85/12.27 seconds, Windows 50.71/57.83 seconds; whole workflow 122 seconds. Fast/full and failing/skipped/cancelled gate selection have fixture coverage. See [dated timing evidence](../test-performance.md).

**Notes:** Owner: Codex. Completed 2026-10-16 after local profiling and full hosted verification. Measured repeated oversized JSON read requests led to a production bounded-chunk reader optimization, with the same byte cap and safety checks, plus a test-only synthetic Git identity fixture; dedicated provenance/live tests retain real Git. Serial execution retained; no worker/dependency added. Documentation/board-only diffs use Linux-only CI; code/unknown changes, milestones, manual and scheduled events retain full coverage. No assertions deleted, validation cache/bypass, county calls, historical-data edits, repository-protection changes or deployment. Old Linux per-phase baseline timings were not recorded and are explicitly unknown; new phase reports cover both platforms. ML-123 remains Ready and not started.

**Evidence / starting points:** [ML-129 full CI](https://github.com/huschked/minnesota-land-intelligence/actions/runs/38952761645), [timing evidence and commands](../test-performance.md), [ML-127 CI baseline](https://github.com/huschked/minnesota-land-intelligence/actions/runs/38943524762), [testing policy](../testing.md), [CI selection/gate fixtures](../../tests/unit/test_ci_plan.py), [bounded-reader safety fixtures](../../tests/unit/test_bounded_run_reads.py), [CI workflow](../../.github/workflows/ci.yml), [shared fixtures](../../tests/conftest.py)

### ML-130 - Prepare actual eligible data for the local viewer

<a id="ml-130"></a>

**Status:** Done

**Priority:** P1

**Kind:** Chore

**Depends on:** ML-123, ML-201

**User outcome:** As a researcher, I can use actual county results in the validated viewer rather than only synthetic fixtures or an empty eligibility screen.

**Acceptance criteria:**

- [x] Inventory the actual retained inputs, dates, hashes and missing protocol evidence read-only; agree and record the recovery/reacquisition route before live requests or production reimports. Keep historical bytes/manifests and tax-year evidence unchanged; do not invent inventories or backfill completion records.
- [x] Produce genuinely eligible version-2 parcel/file/join/review inputs through the current pipeline using the reviewed county source/mapping and actual captured evidence. Use new immutable runs; government requests remain bounded/paced and require selection of this production preparation work, not a viewer click.
- [x] Record resulting source dates, counts, holds, unknown balances and differences from the historical examples without forcing 15/49/62 counts or inferring payment from disappearance. Confirm the full source graph validates and original retained-file hashes remain unchanged.
- [x] Document the real snapshot IDs/selection path and a handoff usable by ML-202/206 without committing raw data/correspondence, uploading datasets, claiming current balances or weakening legacy exclusion. Record actual failures/access blockers honestly if a usable result cannot be obtained.

**Validation:** All five actual run kinds and full pinned source graph validate. Fresh GIS reconciled 23,890 records across 12 pages and 18 retained HTTP attempts; 23,888 normalized, two quarantined. Exact 1,783-row listing recapture produced 62 prior-year candidates, 49 land/15 focused/13 special and 291 current-year parcels, with unchanged historical ID sets. All 62 canonical balances remain null. Isolated offline replay matched normalized fingerprints and all nine export hashes. Before/after SHA-256 checks confirmed all 190 historical files unchanged. Only data placeholders are Git-tracked; raw data, correspondence and private audit evidence remain ignored. See [dated actual handoff](../reviews/isanti-viewer-preparation-2026-10-16.md).

**Notes:** Owner: Codex. Completed 2026-10-16 after the user explicitly agreed to fresh official GIS plus the unchanged October 13 CSV and reviewed year mapping. New join `ce541e7ad88e4a52826a90c9ff5a2139`; review `4e2ebe46423d4f56aab999d7d9eb3a37`. Source capture dates remain separate from publication/current payment status. New manual report verification is pending; historical PDF checks were not relabeled fresh. No runtime code/dependency/UI change, historical certification, county email or dataset upload. ML-202 is next; ML-206 still must prove actual-data usability. County accounting questions stay blocked; general refresh-difference analysis remains ML-124.

**Evidence / starting points:** [UI data gate](../ui-plan.md#data-readiness-is-a-separate-gate), [replay boundaries](../replay.md), [historical results](../reviews/isanti-prior-year-results-2026-10-14.md), [county year evidence](../counties/isanti-tax-year-confirmation.md), [publication](../publication.md)

## E03 - Phase 1.2 - Basic local review UI

<a id="e03"></a>

**Epic state:** Active

**Goal:** Make existing results usable through a small local viewer before advanced GIS features.

**Exit criteria:** A local, tested table/detail workflow can inspect current snapshots and export results with provenance and unknowns intact.

**Owner:** Unassigned; assign a responsible owner when a story is pulled. Epic state is rolled up from story status, not a separate delivery promise.

### ML-201 - Refine review workflow and select the UI approach

<a id="ml-201"></a>

**Status:** Done

**Priority:** P1

**Kind:** Spike

**Depends on:** ML-116

**User outcome:** As the user, I can review the 15-, 49-, and 62-parcel views without running individual analysis commands.

**Acceptance criteria:**

- [x] Document the primary table-to-detail workflow, users, local execution model, and accessibility needs.
- [x] Choose a proportionate UI technology with rationale and acceptance examples; full mapping, scoring, and public hosting stay outside this milestone.

**Validation:** Reviewed the UI decision against current CLI/review schemas, historical view definitions, completion/replay boundaries, a fresh read-only eligibility check and official framework/accessibility documentation. The plan maps U01-U12 acceptance examples to ML-202/203/204/205/206 and new actual-data preparation ML-130. Discovery is documentation-only: no installed framework, browser runtime, keyboard conformance or UI test pass is claimed.

**Notes:** Owner: Codex. Completed 2026-10-16. Selected Streamlit for a read-only, single-user loopback viewer, with a framework-independent validation/review service, explicit snapshot load, factual view filters, keyboard parcel selector, evidence details and safe contextual exports. Official references informed the decision because the skill discovery script found no installed Streamlit; version resolution and runtime/a11y validation remain implementation gates. Actual county data remains legacy, so ML-130 explicitly owns preparing usable real inputs. No framework installed, UI built, county request/reimport, data mutation, scoring or hosting occurred. ML-202 and ML-130 are Ready, not started.

**Evidence / starting points:** [UI decision, wireframe and U01-U12 examples](../ui-plan.md), [historical views](../reviews/isanti-prior-year-results-2026-10-14.md), [replay](../replay.md), [Streamlit dataframe reference](https://docs.streamlit.io/develop/api-reference/data/st.dataframe), [AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest), [configuration](https://docs.streamlit.io/develop/api-reference/configuration/config.toml)

### ML-202 - Load and select verified result snapshots

<a id="ml-202"></a>

**Status:** Done

**Priority:** P1

**Kind:** Story

**Depends on:** ML-201, ML-123

**User outcome:** As a user, I can choose a result snapshot and understand its age and source.

**Acceptance criteria:**

- [x] Load validated outputs through an application service rather than reimplementing Isanti mappings in the UI.
- [x] Show listing/report/GIS dates, row counts, active holds, unknown fields, and helpful missing/corrupt-file states.
- [x] Add a minimal read-only Streamlit selector/error-state shell and optional tested UI dependency without making the CLI depend on it; resolve/pin a compatible version and verify loopback/telemetry/security configuration. Explicitly label synthetic fixtures and legacy/no-eligible states, never silently recertify or fall back.
- [x] Implement U01-U03/U08/U11 service boundaries: validate selected graphs and expose allowlisted DTOs, preserve selected identity across reruns, revalidate new disk reads/export, and prohibit acquisition/replay/network calls on UI interactions. Keep service tests independent of UI dependencies; use supported AppTest controls for the shell.

**Validation:** Implementation revision `3b430e75b8eecbc346f3493b7ef65bb495d0b7c8` passed 687 offline tests without skips in all four hosted Windows/Linux x Python 3.11/3.12 jobs, dependency/version/lint/board checks, explicit live collection and final CI gate. Local regression passed 685 with two existing symlink-privilege skips and one live deselection. Actual ML-130 review loaded through service and AppTest with 62/49/15 views, null balances and pending report verification. All 658 baseline saved county files unchanged; loopback listener/health/configuration verified. No live pytest government test or browser accessibility pass claimed. See [testing evidence](../testing.md#ml-202-selectorservice-verification).

**Notes:** Owner: Codex. Completed 2026-10-16. Framework-independent overview loader, explicit selector/error shell, optional pinned Streamlit 1.66.0 and constrained loopback launcher are implemented. User approved local startup. Source/report/capture dates stay distinct, report date is unknown where not established, synthetic and held states remain visible, new disk actions revalidate and no latest/acquisition/replay fallback exists. Tables/details/exports and final browser/accessibility workflow remain later cards; no county request, reimport, source edit or hosting occurred. Completion docs use fast Linux CI, not another unchanged Windows rerun.

**Evidence / starting points:** [viewer/startup](../viewer.md), [service](../../src/mn_land/review_service.py), [shell](../../src/mn_land/ui/app.py), [launcher](../../src/mn_land/ui/launcher.py), [service fixtures](../../tests/unit/test_review_service.py), [AppTest fixtures](../../tests/unit/test_viewer_shell.py), [configuration fixtures](../../tests/unit/test_viewer_launcher.py), [full CI](https://github.com/huschked/minnesota-land-intelligence/actions/runs/38983351802), [UI plan](../ui-plan.md)

### ML-203 - Build searchable and filterable parcel tables

<a id="ml-203"></a>

**Status:** Done

**Priority:** P1

**Kind:** Story

**Depends on:** ML-202

**User outcome:** As a user, I can narrow the existing candidate views and inspect a parcel.

**Acceptance criteria:**

- [x] Support acreage, prior/current tax category, classification, improvement-known/zero, and PILT/exempt review filters.
- [x] Counts handle overlapping period views correctly; sorting/pagination preserves parcel IDs and nulls; filtered results are testable.
- [x] Provide the labelled keyboard parcel selector/detail action as well as any grid shortcut; stable snapshot/parcel identity must survive filtering, sorting and reruns (U04/U10). Compute view counts dynamically, retain unknowns/leading zeros, and prevent UI filters below the imported threshold from pretending missing records were loaded.

**Validation:** All 758 offline tests passed without skips in each hosted Windows/Linux x Python 3.11/3.12 job at `8e79a2eeb4492d9f7fb385a3773c1ca269124f96`; the live case was collected, not run. 87 targeted service/UI tests also passed locally, including 45 new cases. Actual-data service and AppTest checks compute 15/49/62/13/291 views, 311 distinct union and 42 overlap without acquisition; committed-code AppTest passed in 12.03s. All 856 baseline files remain unchanged (active server logs excluded). Approved viewer restart binds only 127.0.0.1:8501 with health ok. See [viewer behavior](../viewer.md), [testing evidence](../testing.md) and [full CI](https://github.com/huschked/minnesota-land-intelligence/actions/runs/39044032811).

**Notes:** Owner: Codex. Completed 2026-10-17. Saved candidate tables, deterministic service filtering/sorting/pagination, dynamic distinct view counts and a labelled keyboard parcel selection/detail-summary action are implemented. Snapshot identity, source holds, unknowns and the imported/review acreage floor remain effective. Grid export/copy and client column sorting are disabled; no grid row index drives selection. Large parcel selectors are bounded without losing a still-filtered ID. Follow [the UI plan](../ui-plan.md): historical counts are not constants. ML-204 full source-evidence details/links is next recommended; contextual exports remain ML-205 and browser/accessibility release checks remain ML-206. No source acquisition, reimport, opportunity ranking or implied buildability. Only this project's verified local viewer was restarted after user approval; original logs/data were preserved. Later cards do not start automatically.

**Evidence / starting points:** [Viewer](../viewer.md), [Table service](../../src/mn_land/parcel_table.py), [Validated loader](../../src/mn_land/review_service.py), [UI](../../src/mn_land/ui/app.py), [Filter/identity tests](../../tests/unit/test_parcel_table.py), [Load tests](../../tests/unit/test_parcel_table_load.py), [AppTest](../../tests/unit/test_parcel_browser.py), [Verification](../testing.md)

### ML-204 - Add parcel details and source evidence links

<a id="ml-204"></a>

**Status:** Done

**Priority:** P1

**Kind:** Story

**Depends on:** ML-202, ML-203

**User outcome:** As a user, I can see why a parcel appears and inspect its official evidence.

**Acceptance criteria:**

- [x] Display parcel attributes, assessment versus payable years, all source rows, unknown monetary totals, and independent GIS/source owner text.
- [x] Link validated county references and evidence without exposing local secrets or treating field-name guesses as facts.
- [x] Implement U05-U07 with escaped source text and allowlisted external URL validation; no embedded/background county fetch or arbitrary local-file serving. Clearly distinguish raw unaggregated amounts, unknown resale/suitability facts, owner-text sources and parcel-specific sampled corroboration.

**Validation:** 45 new fixture/service/AppTest cases plus affected regressions passed locally; all 803 offline tests passed without skips in all four hosted Windows/Linux x Python 3.11/3.12 jobs at revision 80e669f66cadf31d58c5818eebc98fbfb19432c9. Lint, dependency consistency, board, explicit live collection and CI gate passed. Actual-data detail/back/reload checks passed again on committed code; all 859 baseline saved files are unchanged. Approved project-only restart is loopback-only and healthy. Browser accessibility release QA remains ML-206.

**Notes:** Owner: Codex. Completed 2026-10-17. Explicitly loaded, revalidated, immutable parcel-evidence details are implemented in the keyboard selection flow. All contributing rows, period/year distinctions, independent GIS/listing owners and unknown balances are preserved. County-specific strict link rules permit explicit clicks only; no embedded/background fetch, local-file serving, new report retrieval or legacy/sample substitution. Samples disclose unknown source-hash/date binding and do not establish current payment status. Suitability/economics remain not assessed. ML-203 is recorded as a prerequisite because the shipped details use its table identity flow. Only the verified project viewer was restarted after approval; old logs/data are preserved. ML-205 is next recommended, not automatically started; accounting blockers remain unresolved.

**Evidence / starting points:** [Viewer](../viewer.md), [evidence DTO/projection](../../src/mn_land/parcel_details.py), [validated service](../../src/mn_land/review_service.py), [county link policy](../../src/mn_land/counties/isanti/evidence.py), [literal renderer](../../src/mn_land/ui/details.py), [pure tests](../../tests/unit/test_parcel_evidence.py), [load tests](../../tests/unit/test_parcel_detail_load.py), [UI tests](../../tests/unit/test_parcel_detail_ui.py), [dated checks](../testing.md#ml-204-parcel-source-evidence), [full CI run 39079534737](https://github.com/huschked/minnesota-land-intelligence/actions/runs/39079534737), implementation revision `80e669f66cadf31d58c5818eebc98fbfb19432c9`.

### ML-205 - Export filtered worklists and visible validation issues

<a id="ml-205"></a>

**Status:** In Progress

**Priority:** P2

**Kind:** Story

**Depends on:** ML-203, ML-204

**User outcome:** As a user, I can take my selected review results into a spreadsheet with their context.

**Acceptance criteria:**

- [ ] CSV/JSON exports include filters, snapshot references, source years, unknown markers, and deterministic record ordering.
- [ ] Keep unmatched and source-accounting issues accessible; protect spreadsheet consumers from executable formula content while preserving raw inputs.
- [ ] Implement U07/U08/U10: preview filters/counts/snapshot references and deterministic export order, revalidate before export, prevent built-in grid download/copy from bypassing safe contextual exports, and never mutate retained outputs or latest pointers. CSV neutralization must be disclosed; JSON preserves canonical values/nulls.

**Validation:** Planned: fixture/service/AppTest checks for exact filtered distinct IDs, deterministic Decimal/null ordering, source/year/snapshot/filter context, explicit preview counts, empty/held/issue-only outputs, unknown versus zero, CSV formula neutralization (including whitespace/control-leading payloads), JSON preservation, changed evidence rejection, and no source/latest mutation or built-in export bypass. Run affected checks and the full implementation-boundary matrix; actual-data export checks must not claim browser clipboard/accessibility conformance.

**Notes:** Owner: Codex. Selected 2026-10-17. Implement explicit preview and filtered/selected exports with source/year/filter context, click-time evidence revalidation, disclosed CSV text protection and canonical JSON fidelity. Snapshot-wide issues remain separate from filtered candidates. No source acquisition, financial totals, editing, contact enrichment or owner outreach; county accounting blockers remain unresolved.

**Evidence / starting points:** [Export guide](../worklist-exports.md), [pure projection/serialization](../../src/mn_land/worklists.py), [county issue allowlists](../../src/mn_land/counties/isanti/worklists.py), [validated service](../../src/mn_land/review_service.py), [deferred-download UI](../../src/mn_land/ui/worklists.py), [pure tests](../../tests/unit/test_worklists.py), [service tests](../../tests/unit/test_worklist_service.py), [UI tests](../../tests/unit/test_worklist_ui.py), [dated checks](../testing.md#ml-205-contextual-worklists). Local affected checks and actual saved-data previews/downloads pass; final hosted matrix and approved project-only viewer restart remain completion gates.

### ML-206 - Package and validate the local UI

<a id="ml-206"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-203, ML-204, ML-205, ML-130

**User outcome:** As a user, I can start and use the viewer reliably on this Windows workspace.

**Acceptance criteria:**

- [ ] Document one clean startup/install path; verify keyboard operation, readable layouts, empty/error states, and representative workflows.
- [ ] Keep unit/UI checks offline and confirm the UI reuses pipeline results; any future network exposure requires its own design and release review.
- [ ] Verify U09/U11/U12 on the actual Windows/browser workflow with ML-130's eligible real inputs: keyboard parcel selection/focus, readable 200% zoom, no hidden row-identity changes, correct computed counts/source warnings, loopback-only startup and no automatic county requests. Distinguish AppTest coverage from browser/accessibility checks; do not claim usability from synthetic fixtures alone.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** Local viewer only; hosted web application remains E11. Follow [the UI plan](../ui-plan.md). ML-130 is a real-data handoff gate; no new scoring, maps, source edits, owner outreach, user accounts or persistent research-notes system is included. Accessibility is a release check, not an assumed property of the selected framework.

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

## E04 - Phase 2 - GIS land suitability

<a id="e04"></a>

**Epic state:** Backlog

**Goal:** Estimate spatial constraints and usable upland acreage from authoritative layers.

**Exit criteria:** Wetland/floodplain screening is reproducible, validated, dated, and clearly distinguished from legal buildability.

**Owner:** Unassigned; assign a responsible owner when a story is pulled. Epic state is rolled up from story status, not a separate delivery promise.

### ML-301 - Inspect authoritative suitability layers and usage terms

<a id="ml-301"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Spike

**Depends on:** ML-116, ML-119, ML-124

**User outcome:** As a researcher, I need the correct wetlands/floodplain coverage and source versions before overlay analysis.

**Acceptance criteria:**

- [ ] Compare official county/state/federal layers for coverage, dates, licensing/access terms, resolution, and limitations.
- [ ] Record selected sources and a sample retrieval contract; missing coverage is unknown, not zero constraint.

**Validation:** Review the documented findings, source evidence, decision, and bounded follow-up tasks against the acceptance criteria.

**Notes:** Discovery first; do not assume statewide layers have equal accuracy.

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-302 - Implement geometry retrieval, CRS handling, and validation

<a id="ml-302"></a>

**Status:** Backlog

**Priority:** P0

**Kind:** Story

**Depends on:** ML-301

**User outcome:** As a GIS analyst, I can trust polygon identity and area calculations.

**Acceptance criteria:**

- [ ] Preserve original geometry/CRS and record the analysis CRS, units, precision, multipart handling, and topology checks.
- [ ] Test invalid/empty polygons, holes, duplicate geometry, geometry-versus-deeded area discrepancies, and supported repair with audit logs.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** Deeded acreage remains distinct from computed geometry acreage.

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-303 - Calculate wetland overlap

<a id="ml-303"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-301, ML-302

**User outcome:** As a researcher, I can see estimated wetland acreage and percent with source limitations.

**Acceptance criteria:**

- [ ] Clip/dissolve appropriate wetland features and prevent duplicate/overlapping feature area from being counted twice.
- [ ] Test no overlap, full overlap, boundaries, multipart parcels, and missing source coverage; retain source/algorithm versions.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-304 - Calculate floodplain overlap by mapped category

<a id="ml-304"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-301, ML-302

**User outcome:** As a researcher, I can distinguish mapped flood constraints rather than assume all mapped areas are equivalent.

**Acceptance criteria:**

- [ ] Retain official flood categories, effective map dates, and coverage status.
- [ ] Test category overlap, revised/unmapped areas, geometry boundaries, and null coverage; avoid regulatory determinations.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-305 - Estimate usable upland acres without double subtraction

<a id="ml-305"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-303, ML-304

**User outcome:** As a researcher, I can distinguish gross acres and estimated land remaining after mapped constraints.

**Acceptance criteria:**

- [ ] Define the screening formula using the union of constraint geometry so wetland/floodplain overlap is subtracted once.
- [ ] Bound estimates by measured parcel area, quantify incomplete coverage, and label results as estimated usable acres rather than legally buildable acres.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-306 - Validate and publish suitability results

<a id="ml-306"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-305

**User outcome:** As a user, I can inspect how each suitability figure was produced.

**Acceptance criteria:**

- [ ] Compare representative parcels to official maps and document tolerances, errors, and unavailable results.
- [ ] Publish canonical enrichment CSV/JSON and integrate with existing views where available; keep fixtures offline and document reruns.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** No zoning or dwelling-count conclusions in this epic.

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

## E05 - Phase 3 - Access and terrain

<a id="e05"></a>

**Epic state:** Backlog

**Goal:** Add physical road and terrain observations without claiming legal access.

**Exit criteria:** Access/frontage, slope, and shape observations have documented algorithms, units, sources, and verification limits.

**Owner:** Unassigned; assign a responsible owner when a story is pulled. Epic state is rolled up from story status, not a separate delivery promise.

### ML-401 - Inspect road and elevation sources

<a id="ml-401"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Spike

**Depends on:** ML-302

**User outcome:** As a GIS analyst, I can select road/elevation data appropriate to rural parcels.

**Acceptance criteria:**

- [ ] Document official road ownership/classification, right-of-way availability, DEM coverage, dates, CRS, resolution, and vertical units.
- [ ] Plan for private roads, trails, easements absent from GIS, and missing elevation coverage.

**Validation:** Review the documented findings, source evidence, decision, and bounded follow-up tasks against the acceptance criteria.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-402 - Screen road proximity and frontage

<a id="ml-402"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-401

**User outcome:** As a researcher, I can separate mapped adjacency, estimated frontage, and unverified legal access.

**Acceptance criteria:**

- [ ] Use documented boundary/road geometry and tolerances; distinguish centerline proximity from actual right-of-way frontage.
- [ ] Test corner contacts, separated carriageways, nearby-but-not-touching roads, and private roads; flag title/easement verification.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-403 - Calculate elevation and slope observations

<a id="ml-403"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-401, ML-302

**User outcome:** As a researcher, I can screen steep or variable terrain.

**Acceptance criteria:**

- [ ] Document DEM sampling, slope formula, horizontal/vertical units, nodata handling, and resolution limitations.
- [ ] Export elevation/slope summaries with fixtures covering flat, steep, partial-coverage, and edge parcels.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-404 - Calculate parcel shape metrics

<a id="ml-404"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-302

**User outcome:** As a researcher, I can identify geometry that may complicate land use.

**Acceptance criteria:**

- [ ] Define explainable compactness/width or related metrics with units and multipart behavior.
- [ ] Test long/narrow, irregular, donut, and disjoint parcels; do not infer development approval.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-405 - Validate access and terrain screening outputs

<a id="ml-405"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-402, ML-403, ML-404

**User outcome:** As a user, I can review these observations with their limitations.

**Acceptance criteria:**

- [ ] Compare representative results against authoritative maps and document tolerances.
- [ ] Publish source-linked enrichments with unknowns intact and distinguish estimated physical characteristics from legal rights.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

## E06 - Phase 4 - Planning and development screening

<a id="e06"></a>

**Epic state:** Backlog

**Goal:** Attach jurisdiction-specific rules and preliminary development constraints.

**Exit criteria:** Every rule has jurisdiction/date/source evidence and conclusions remain preliminary pending governing-authority confirmation.

**Owner:** Unassigned; assign a responsible owner when a story is pulled. Epic state is rolled up from story status, not a separate delivery promise.

### ML-501 - Inventory jurisdictions and authoritative planning rules

<a id="ml-501"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Spike

**Depends on:** ML-302

**User outcome:** As a researcher, I can identify which authority and ordinance apply to a parcel.

**Acceptance criteria:**

- [ ] Capture county/city/township boundaries, ordinance versions, amendments, effective dates, and official citations.
- [ ] Identify overlays and ambiguous jurisdiction cases; do not substitute generalized statewide rules.

**Validation:** Review the documented findings, source evidence, decision, and bounded follow-up tasks against the acceptance criteria.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-502 - Join zoning districts and overlays

<a id="ml-502"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-501

**User outcome:** As a researcher, I can see mapped zoning and its source.

**Acceptance criteria:**

- [ ] Support split-zoned parcels, overlays, conflicting layers, and missing/unmapped districts.
- [ ] Retain raw district codes and official meanings with spatial/date lineage and boundary-case tests.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-503 - Represent lot-size, subdivision, and dwelling rules

<a id="ml-503"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-502

**User outcome:** As a researcher, I can compare documented planning constraints without assuming approval.

**Acceptance criteria:**

- [ ] Model minimum lots, frontage, density, setbacks, exceptions, and conditional approvals as sourced rules with effective dates.
- [ ] Evaluate only rules supported by inputs; expose missing exceptions/interpretations and produce preliminary, explainable screening.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-504 - Screen soils and septic-related constraints

<a id="ml-504"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-301, ML-501

**User outcome:** As a researcher, I can identify mapped soil limitations requiring field verification.

**Acceptance criteria:**

- [ ] Document official soil data, capability/limitation definitions, coverage, and scale.
- [ ] Report screening observations and required site investigations without claiming septic approval or replacing licensed assessment.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-505 - Create preliminary family-compound due-diligence view

<a id="ml-505"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-305, ML-405, ML-503, ML-504

**User outcome:** As a user, I can inspect relevant constraints together for multi-home research.

**Acceptance criteria:**

- [ ] Show gross/estimated usable acreage, access, terrain, zoning, and septic unknowns separately.
- [ ] Any hypothetical lot/dwelling scenario states assumptions and unresolved approvals; never label GIS acreage as legally buildable.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

## E07 - Phase 5 - Objective ownership intelligence

<a id="e07"></a>

**Epic state:** Backlog

**Goal:** Use traceable public property records for ownership and parcel-assemblage research.

**Exit criteria:** Ownership observations and assemblages are deterministic, independently sourced, and avoid sensitive personal inference.

**Owner:** Unassigned; assign a responsible owner when a story is pulled. Epic state is rolled up from story status, not a separate delivery promise.

### ML-601 - Normalize ownership text with conservative identity handling

<a id="ml-601"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-124

**User outcome:** As a researcher, I can compare public owner records without merging unrelated people.

**Acceptance criteria:**

- [ ] Preserve original names/addresses and document exact normalization/verified identifier rules.
- [ ] Separate name similarity from verified common ownership; manual crosswalks retain evidence and dates.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-602 - Establish ownership duration from authoritative records

<a id="ml-602"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-601

**User outcome:** As a researcher, I can see documented acquisition dates and their limitations.

**Acceptance criteria:**

- [ ] Inspect official transfer/deed sources, date meaning, coverage, and access restrictions.
- [ ] Distinguish title changes, entity changes, and missing history; never infer duration from a current owner name alone.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-603 - Derive objective mailing-location observations

<a id="ml-603"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-601

**User outcome:** As a researcher, I can compare parcel location with recorded mailing location.

**Acceptance criteria:**

- [ ] Preserve mailing-source dates, distinguish missing/PO-box/care-of records, and document geographic comparison rules.
- [ ] Describe in/out-of-state or non-site mailing only; do not infer residency, hardship, willingness to sell, or personal circumstances.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-604 - Identify contiguous common-owner parcel groups

<a id="ml-604"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-302, ML-601

**User outcome:** As a researcher, I can inspect possible land assemblages supported by geometry and ownership evidence.

**Acceptance criteria:**

- [ ] Distinguish shared edges, corner touches, road-separated, and near-adjacent parcels using explicit rules.
- [ ] Avoid counting duplicate parcels twice; export member IDs, gross/usable area basis, uncertain ownership, and geometry evidence.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-605 - Integrate authoritative tax-forfeiture stage separately

<a id="ml-605"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-113, ML-601

**User outcome:** As a researcher, I can distinguish delinquency from a separately documented forfeiture event.

**Acceptance criteria:**

- [ ] Inspect an official forfeiture-specific source and define stage/effective-date semantics.
- [ ] Retain independent lineage and unresolved status; neither delinquency nor list absence implies forfeiture or a completed sale.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

## E08 - Phase 6 - Comparable sales and economics

<a id="e08"></a>

**Epic state:** Backlog

**Goal:** Support explainable land-sale comparisons using verified transactions and accounting inputs.

**Exit criteria:** Comparable selection and calculations reconcile to authoritative data and explicitly dated assumptions.

**Owner:** Unassigned; assign a responsible owner when a story is pulled. Epic state is rolled up from story status, not a separate delivery promise.

### ML-701 - Inspect official sales/eCRV sources and terms

<a id="ml-701"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Spike

**Depends on:** ML-119

**User outcome:** As a researcher, I can determine which recorded sales are usable for land comparison.

**Acceptance criteria:**

- [ ] Document official access method, licensing, fields, date definitions, update frequency, and coverage.
- [ ] Identify multi-parcel, partial-interest, non-arm's-length, and correction records before mapping prices.

**Validation:** Review the documented findings, source evidence, decision, and bounded follow-up tasks against the acceptance criteria.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-702 - Normalize sales and parcel associations

<a id="ml-702"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-701, ML-112

**User outcome:** As a researcher, I can trace each transaction to its actual parcel set.

**Acceptance criteria:**

- [ ] Preserve transaction IDs, original amounts, sale/recording dates, corrections, and exact parcel links.
- [ ] Do not allocate a multi-parcel sale price arbitrarily; flag ambiguous allocations and deduplicate source versions.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-703 - Select transparent comparable-sale sets

<a id="ml-703"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-702, ML-306

**User outcome:** As a researcher, I can understand why each comparable was included.

**Acceptance criteria:**

- [ ] Define configurable time, distance, acreage, improvement, and land-use filters with inclusion/exclusion explanations.
- [ ] Show insufficient comparables and differences in land constraints; validate against a documented sample instead of implying an appraisal.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-704 - Calculate dated per-acre and valuation comparisons

<a id="ml-704"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-703

**User outcome:** As a researcher, I can compare consistent price and acreage measures.

**Acceptance criteria:**

- [ ] Keep gross-acre and usable-acre denominators distinct; handle zero/missing acreage and unknown allocations.
- [ ] Label assessed versus estimated market values, valuation year, sale dates, and currency/rounding rules; test every calculation.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-705 - Model financial scenarios and verified tax ratios

<a id="ml-705"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-704, ML-122

**User outcome:** As a user, I can inspect transparent financial scenarios using known inputs.

**Acceptance criteria:**

- [ ] Use verified prior-year balances and correctly dated valuations for any balance/value ratio; never use ambiguous GIS tax fields.
- [ ] Expose user-supplied price/cost assumptions, unknowns, and sensitivity ranges; do not present estimates as purchase offers or guaranteed outcomes.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

## E09 - Phase 7 - Deterministic opportunity scoring

<a id="e09"></a>

**Epic state:** Backlog

**Goal:** Provide explainable, versioned prioritization from objective property evidence.

**Exit criteria:** Every score can be reproduced from versioned inputs, formulas, weights, and visible missing-data treatment.

**Owner:** Unassigned; assign a responsible owner when a story is pulled. Epic state is rolled up from story status, not a separate delivery promise.

### ML-801 - Specify scoring rules, weights, and missing-data policy

<a id="ml-801"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Spike

**Depends on:** ML-306, ML-405, ML-503, ML-604, ML-704

**User outcome:** As a user, I can understand and challenge the ranking rules before they affect results.

**Acceptance criteria:**

- [ ] Document score purposes, weights, units, thresholds, source requirements, and versioning.
- [ ] Keep missingness/confidence separate from bad property conditions; agree on evaluation examples and prohibit sensitive owner proxies.

**Validation:** Review the documented findings, source evidence, decision, and bounded follow-up tasks against the acceptance criteria.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-802 - Implement land-suitability component scoring

<a id="ml-802"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-801, ML-505

**User outcome:** As a researcher, I can trace land-related prioritization to measured constraints.

**Acceptance criteria:**

- [ ] Calculate deterministic components from supported suitability/access/planning observations.
- [ ] Expose contributions, unknowns, thresholds, and boundary tests; avoid claiming legal buildability.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-803 - Implement objective ownership-opportunity component

<a id="ml-803"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-801, ML-602, ML-603, ML-604, ML-605

**User outcome:** As a researcher, I can inspect property-record factors without personal predictions.

**Acceptance criteria:**

- [ ] Use documented public-record factors only, with dates and contribution explanations.
- [ ] Exclude hardship/health/age/family and similar sensitive inferences; do not claim seller intent.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-804 - Implement financial component scoring

<a id="ml-804"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-801, ML-705

**User outcome:** As a researcher, I can inspect financially relevant factors calculated from verified data.

**Acceptance criteria:**

- [ ] Version and test formulas, limits, missing inputs, and extreme/zero values.
- [ ] Keep scenario assumptions separate from authoritative facts and display unavailable components.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-805 - Combine and validate overall ranking

<a id="ml-805"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-802, ML-803, ML-804

**User outcome:** As a user, I can understand why a parcel ranks where it does.

**Acceptance criteria:**

- [ ] Show component contributions, input dates, formula version, and deterministic tie-breaking.
- [ ] Evaluate sensitivity to weights and missing data, retain earlier score snapshots, and export a complete explanation per result.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

## E10 - Phase 8 - PostGIS when justified

<a id="e10"></a>

**Epic state:** Backlog

**Goal:** Introduce persistent spatial storage only when measured workloads justify the operational cost.

**Exit criteria:** A justified database migration preserves source history and passes reconciliation, performance, and restore checks.

**Owner:** Unassigned; assign a responsible owner when a story is pulled. Epic state is rolled up from story status, not a separate delivery promise.

### ML-901 - Measure storage/query needs and record a database decision

<a id="ml-901"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Spike

**Depends on:** ML-306, ML-604

**User outcome:** As a maintainer, I can justify adopting or deferring PostGIS using actual workload evidence.

**Acceptance criteria:**

- [ ] Benchmark dataset sizes, spatial operations, repeated queries, and concurrency needs.
- [ ] Document decision thresholds, alternatives, operating cost, and deferral criteria; migration stories stay unselected if unjustified.

**Validation:** Review the documented findings, source evidence, decision, and bounded follow-up tasks against the acceptance criteria.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-902 - Design versioned parcel and spatial-enrichment storage

<a id="ml-902"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-901

**User outcome:** As a maintainer, I can store canonical observations without losing snapshots or county identity.

**Acceptance criteria:**

- [ ] Define county+parcel+snapshot keys, geometry/CRS constraints, source records, field lineage, and temporal validity.
- [ ] Specify indexes, migrations, retention, and unknown-value semantics; avoid using normalized owner text as an identity key.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-903 - Migrate and reconcile preserved datasets

<a id="ml-903"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-902

**User outcome:** As an operator, I can migrate data without changing results.

**Acceptance criteria:**

- [ ] Retain immutable raw files and compare counts, IDs, money, geometry areas, and candidate sets before/after migration.
- [ ] Provide repeatable imports, failure recovery, rollback, and representative fixtures.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-904 - Implement and benchmark spatial query paths

<a id="ml-904"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-903

**User outcome:** As a user, I can query larger spatial datasets accurately and responsively.

**Acceptance criteria:**

- [ ] Implement required intersections, adjacency, and filters with query plans and spatial indexes.
- [ ] Compare results with the established analysis path and document performance targets and numerical tolerances.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-905 - Verify database operations and recovery

<a id="ml-905"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Chore

**Depends on:** ML-903

**User outcome:** As an operator, I can protect and restore the project's data.

**Acceptance criteria:**

- [ ] Document scoped credentials, secret handling, backup/retention, schema upgrades, and access boundaries.
- [ ] Exercise an actual restore and rollback rehearsal; prevent raw correspondence or sensitive local configuration from unintended publication.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

## E11 - Phase 9 - Full web application

<a id="e11"></a>

**Epic state:** Backlog

**Goal:** Expand the basic viewer into a map-based research application with reliable operations.

**Exit criteria:** Source-aware map/search/detail workflows meet accessibility, data freshness, security, and deployment checks.

**Owner:** Unassigned; assign a responsible owner when a story is pulled. Epic state is rolled up from story status, not a separate delivery promise.

### ML-1001 - Design application boundaries and delivery model

<a id="ml-1001"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Spike

**Depends on:** ML-206, ML-306

**User outcome:** As a maintainer, I can evolve the local UI without duplicating business rules.

**Acceptance criteria:**

- [ ] Decide local/private/public deployment, service/API boundaries, data access, and database need with rationale.
- [ ] Define authentication/authorization only where required by the chosen exposure model; document API versioning and unknown/source semantics.

**Validation:** Review the documented findings, source evidence, decision, and bounded follow-up tasks against the acceptance criteria.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-1002 - Add parcel map and constraint layers

<a id="ml-1002"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-1001, ML-302, ML-306

**User outcome:** As a user, I can inspect parcels and mapped constraints together.

**Acceptance criteria:**

- [ ] Keep source CRS/attribution/date information and geometry identity intact across map transformations.
- [ ] Use appropriate geometry simplification/tiling and accessible table alternatives; selection works for multipart/overlapping parcels.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-1003 - Add advanced search and explainable ranking views

<a id="ml-1003"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-1001, ML-805

**User outcome:** As a user, I can search across supported facts and understand ranking.

**Acceptance criteria:**

- [ ] Combine spatial, tax-period, acreage, suitability, and score filters with explicit unknown handling.
- [ ] Counts, sort order, URLs/bookmarks, and exports consistently reflect the same query and snapshot.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-1004 - Build complete parcel research and evidence pages

<a id="ml-1004"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-1001, ML-204, ML-505, ML-705

**User outcome:** As a user, I can review one parcel's evidence and limitations in context.

**Acceptance criteria:**

- [ ] Show independent parcel/tax/GIS/planning/sales sources, dates, overrides, and conflicts.
- [ ] Link evidence and due-diligence items; distinguish preliminary calculations from verified governmental decisions.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-1005 - Persist user worklists and research annotations

<a id="ml-1005"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-1003, ML-1004

**User outcome:** As a user, I can save review progress without modifying authoritative records.

**Acceptance criteria:**

- [ ] Store notes/selections separately from raw facts, keyed by stable parcel and snapshot identifiers.
- [ ] Define export/restore and access behavior; refreshing data preserves annotations and flags changed or retired parcel identities.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-1006 - Validate and release the chosen web deployment

<a id="ml-1006"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-1002, ML-1003, ML-1004, ML-1005

**User outcome:** As an operator, I can deploy and maintain the application safely.

**Acceptance criteria:**

- [ ] Verify accessibility, responsive layout, performance, dependency/security checks, backups, health diagnostics, and rollback.
- [ ] Review data exposure/retention and secret handling, document operations, and obtain the required explicit deployment authorization before external publication.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

## E12 - Phase 10 - Advisory AI research

<a id="e12"></a>

**Epic state:** Backlog

**Goal:** Use AI for source-grounded research assistance while preserving authoritative property facts.

**Exit criteria:** AI outputs are cited, evaluated, explicitly advisory, and isolated from canonical facts and deterministic calculations.

**Owner:** Unassigned; assign a responsible owner when a story is pulled. Epic state is rolled up from story status, not a separate delivery promise.

### ML-1101 - Specify AI boundaries, evidence retrieval, and evaluations

<a id="ml-1101"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Spike

**Depends on:** ML-1004

**User outcome:** As a user, I can assess an AI feature's reliability before relying on it for research.

**Acceptance criteria:**

- [ ] Define allowed tasks, source restrictions, data handling, prompt/model versioning, cost limits, and evaluation cases.
- [ ] Treat retrieved documents as untrusted data, test unsupported claims/prompt injection, and prevent AI writes to authoritative parcel facts.

**Validation:** Review the documented findings, source evidence, decision, and bounded follow-up tasks against the acceptance criteria.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-1102 - Summarize ordinances with citations and effective dates

<a id="ml-1102"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-1101, ML-501

**User outcome:** As a researcher, I can find relevant ordinance provisions with traceable summaries.

**Acceptance criteria:**

- [ ] Cite exact official sections and version dates; preserve exceptions and jurisdiction ambiguity.
- [ ] Evaluate citation support and omissions; distinguish summaries from legal interpretations or development approvals.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-1103 - Generate source-grounded parcel research summaries

<a id="ml-1103"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-1101, ML-1004

**User outcome:** As a user, I can read a concise account of supported parcel observations.

**Acceptance criteria:**

- [ ] Summaries cite the exact snapshots and evidence and explicitly retain unknowns/conflicts.
- [ ] Use deterministic services for calculations and never infer personal circumstances, seller intent, or undisclosed property facts.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-1104 - Surface anomalies for human review

<a id="ml-1104"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-1101, ML-124

**User outcome:** As a maintainer, I can inspect possible data inconsistencies without silently changing records.

**Acceptance criteria:**

- [ ] Produce review proposals with source references, reasons, and reproducible input context.
- [ ] Evaluate false positives and require explicit reviewed corrections; no AI-generated value overwrites raw or canonical facts.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-1105 - Generate due-diligence checklists and opportunity explanations

<a id="ml-1105"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-1102, ML-1103, ML-805

**User outcome:** As a researcher, I can identify unanswered questions and understand an existing score.

**Acceptance criteria:**

- [ ] Explain the deterministic score using recorded contributions, not newly invented weights or facts.
- [ ] Create cited verification tasks for governing authorities and professionals; track model/prompt versions and evaluation results.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

## E13 - Phase 11 - Multi-county expansion

<a id="e13"></a>

**Epic state:** Backlog

**Goal:** Add counties through tested adapters while retaining county-specific meaning and source quality.

**Exit criteria:** At least one selected additional county passes common contracts, semantic review, and human source checks without changing core business rules.

**Owner:** Unassigned; assign a responsible owner when a story is pulled. Epic state is rolled up from story status, not a separate delivery promise.

### ML-1201 - Prioritize counties by authoritative data accessibility

<a id="ml-1201"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Spike

**Depends on:** ML-119, ML-124

**User outcome:** As a product owner, I can select the next county using explicit evidence.

**Acceptance criteria:**

- [ ] Compare Sherburne, Chisago, Wright, Anoka, Pine, Kanabec, and Mille Lacs for official parcel/tax/GIS availability and access terms.
- [ ] Record semantic clarity, currency, effort, and research fit; select the next county explicitly rather than creating empty adapters.

**Validation:** Review the documented findings, source evidence, decision, and bounded follow-up tasks against the acceptance criteria.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-1202 - Create reusable adapter contract and fixture checks

<a id="ml-1202"></a>

**Status:** Backlog

**Priority:** P1

**Kind:** Story

**Depends on:** ML-1201

**User outcome:** As a maintainer, I can enforce consistent outputs without forcing Isanti schemas on other counties.

**Acceptance criteria:**

- [ ] Define contract tests for canonical fields, nulls, money, IDs, geometry, pagination, source holds, and independent source lineage.
- [ ] Retain county-specific year/status rules; test that core filters/exports do not depend on Isanti field names.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-1203 - Implement the first selected county parcel adapter

<a id="ml-1203"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-1202

**User outcome:** As a researcher, I can retrieve one additional county through the existing workflow.

**Acceptance criteria:**

- [ ] Inspect and document official layer/schema and implement respectful, complete, raw-preserving retrieval.
- [ ] Normalize with county fixtures and compare representative records against official sources; no silent fallback to unofficial datasets.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-1204 - Implement the selected county delinquency source

<a id="ml-1204"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-1203, ML-1202

**User outcome:** As a researcher, I can distinguish verified prior-year delinquency under that county's conventions.

**Acceptance criteria:**

- [ ] Obtain authoritative year/balance/duplicate definitions and implement deterministic ID matching with visible unknowns.
- [ ] Preserve all source rows and dates, distinguish current overdue installments, and manually check a representative sample.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.

### ML-1205 - Validate cross-county views and release documentation

<a id="ml-1205"></a>

**Status:** Backlog

**Priority:** P2

**Kind:** Story

**Depends on:** ML-1204, ML-1004

**User outcome:** As a user, I can compare counties without losing differences in evidence or date basis.

**Acceptance criteria:**

- [ ] Show county-qualified IDs, snapshot dates, units, coverage, supported fields, and tax-status limitations.
- [ ] Reconcile counts and filters per county; test unknown capabilities, document onboarding, and avoid accidental cross-county identity merges.

**Validation:** Add the relevant fixture, calculation, UI, source-sample, or recovery checks from the acceptance criteria; follow the shared Definition of Done.

**Notes:** undefined

**Evidence / starting points:** To be attached when work starts; add dated source/code/test evidence before Done.
