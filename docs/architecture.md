# Architecture

The parcel pipeline is deliberately linear: official ArcGIS service → complete raw acquisition → pinned source copy → county adapter/canonical parcel → validation/filtering → completed per-run exports. `ArcGISClient` owns HTTP, retries, metadata, count checks, and pagination. The Isanti county adapter package owns county GIS field names and schema declarations. Core filtering accepts `Parcel` instances and records deterministic rejection reasons.

Phase 1.1 separates source responsibilities. A `DelinquencySource` produces county-independent `DelinquencyRecord` objects from an authoritative delinquency-specific publication. The parcel and delinquency snapshots are normalized independently, joined only by a county-specific deterministic parcel-ID key, and retain independent lineage.

```text
Official parcel GIS -> Parcel -------------------+
                                                   exact normalized-ID join -> status -> candidates
Official delinquency file -> DelinquencyRecord --+
```

Absence from a snapshot does not establish that a parcel is current. Duplicate delinquency rows and duplicate parcel join keys are ambiguous, not silently aggregated. Unmatched source rows are exported for review.

New parcel acquisitions store initial/final metadata and count/ID inventories, ordered parsed pages, and bounded original HTTP bodies with per-attempt evidence/hashes under an exclusively reserved UUID directory. Capability, page, membership and detectable-change checks are described in [retrieval](retrieval.md). New file imports capture exact bounded mapping/source/supporting bytes before normalization. Raw and processed completion are separate; failed/staging directories are not results. See [publication](publication.md). Historical captures remain unchanged.

Additional counties should implement `CountyAdapter` and produce the same canonical model. Future GIS enrichment can attach derived observations after normalization; persistent spatial processing can move to PostGIS only when scale warrants it. None of that is part of Phase 1.

Source-specific review holds are explicit mapping settings. They propagate into
delinquency records and prevent exact joins from becoming verified delinquency.
Identity matching, source-list presence, and confirmed tax status are distinct.
Independent official-record evidence is retained separately from raw imports;
new hold-aware outputs do not overwrite earlier snapshots. Isanti review views
group factual classifications and improvement values without generating scores.

County-confirmed mixed sources classify each record's tax period before joining.
Prior-year unpaid status is existential: one or more confirmed prior-year rows
can establish parcel presence, while repeated fiscal components still cannot
establish an additive total. Multi-row lineage is retained. The source's report
assessment year sets the current/prior boundary, independently of execution date.
Separate exports prevent current overdue installments from entering the prior-year
candidate count; parcels may appear in both views with disjoint supporting rows.

## Execution identity

`mn_land.provenance` records package version, local Git revision/dirty state when
available, the actual Python source-file hashes, Python/platform, installed
distribution versions, effective nonsecret configuration and its SHA-256, and
explicit input/output file hashes. See [reproducibility](reproducibility.md).
This is execution evidence, not a new authority for county facts. A dirty revision
is not a recoverable release on its own; retain the corresponding source changes.
The helper performs no network requests and adds no runtime dependency.

New GIS raw manifests carry request/runtime identity and raw artifact hashes.
`find-candidates` writes `execution.json` in its immutable processed run, linking those
inputs to the derived exports. Join manifests and review summaries carry their own
`provenance` object. Their self-hashes are deliberately excluded. Historical
snapshots and old flat parcel exports are not rewritten. New outputs use per-run
directories and validated completion records/pointers, not flat compatibility files.

## Implemented ingestion hardening

[ML-119's contracts and fixture matrix](ingestion-contracts.md) distinguish
observed behavior from proposed validation/retrieval/publication guarantees.
ML-125 implements [strict validation](validation.md): bounded CSV/XLSX readers,
mapping/evidence checks, finite numeric representations, an adapter-owned metadata
callback, and explicit normalization diagnostics. ML-126 now implements
[respectful HTTP and source completeness](retrieval.md), using that callback before
queries and again at the end. Policy is shared between Settings, client and transport;
sequential pacing/retry budgets and original response capture use fake clocks in tests.
ML-127 implements [staged completion publication and shared reader eligibility](publication.md).
Producers pin validated source graphs and reconcile actual artifacts/rows before
installing version-2 completion records and latest pointers. Legacy manifests and
recorded hashes alone are not new-protocol eligibility. No migration is performed.

ML-123 adds [explicit snapshot selection and offline replay](replay.md). File capture
and joining retained inputs share one processing path; replay never calls acquisition
or latest selection. It reuses captured input limits and dates, checks the selected
county/service/layer/query, pins exact inputs, records normalized/export fingerprints
and rejects unexpected drift before completion. Moved join graphs remain self-contained.
Historical pre-completion runs are not migrated or certified; current code/runtime
identity is recorded rather than pretending to restore historical software.

## Saved snapshot differences

ML-124 adds [offline saved-join comparison](snapshot-comparison.md) through
`snapshot_diff`, using existing county normalization/join semantics and recorded
fingerprints. A new immutable `comparison` run pins two join graphs; its content
validator recomputes the report from contained evidence and explicit date policy.
No acquisition, reimport, latest-input selection or UI refresh is involved.

## Local viewer shell and planned research workflow

[The UI plan](ui-plan.md) defines the eventual basic review workflow. ML-202's
[implemented shell](viewer.md) uses a framework-independent `ReviewService` and
existing graph validation, with explicit join/review loading and local catalog
states. A frozen allowlisted overview carries IDs, hashes, dates, counts, holds,
unknowns and validation time; raw source dictionaries/paths are not browser DTOs.
Streamlit is an optional extra, imported only by the app/launcher invocation.
No source normalization, acquisition/replay, scoring or balance aggregation belongs
in widgets. Exact inventoried-byte JSON reads reject changes after validation and
pinned-child completion identities are checked between reads. New loads/reload
revalidate; pure reruns keep the per-session in-memory observation and its original
timestamp, not a pathname/mtime trust cache. New disk-backed details/exports must
use the same revalidation gate. [ML-130 supplied eligible real inputs](reviews/isanti-viewer-preparation-2026-10-16.md)
in new runs while historical files remain legacy. ML-206 still has a
real-data/accessibility release gate. The launcher enforces loopback, telemetry off,
CORS/XSRF on, static serving off and literal source-text rendering. Tables/filters
are added by ML-203 below; ML-204 adds parcel evidence links/details and ML-205
adds contextual/formula-protected exports;
no data migration or county acquisition is performed by the shell.

ML-203 adds a separate immutable `ParcelDataset` projection from the selected
join's two exact inventoried candidate exports. The loader revalidates the graph
and completion identity, applies the selected review floor and withholds browsing
under active holds. `parcel_table` reuses county classification and ID normalization
while owning exact Decimal filters, distinct view counts, null-last stable ordering,
pagination and county/snapshot/hash/parcel selection identities. Cheap reruns use
only per-session immutable observations, not shared pickle caches or new disk reads.
The UI sends only allowlisted current-page fields, disables grid export/copy and
client column sorting, and uses an independent labelled keyboard detail-summary
path. ML-205 adds contextual exports below; browser release QA remains ML-206. No ingestion
or canonical monetary meaning changes.

ML-204 adds frozen `ParcelDetails`/`ListingRow`/`PeriodEvidence` projections and a
literal-text renderer. Explicit Open revalidates the selected graph and identity,
reads exact inventoried CSV/XLSX bytes through the existing bounded table parser,
matches every contributing record/location to the candidate exports, checks year
sets and the reviewed county convention, then revalidates before returning. Raw
monetary observations are never summed or promoted to unmapped canonical balances.
Ten-row source pagination and ordinary reruns reuse the immutable per-session DTO;
Reload clears details and requires another explicit Open. A failed new disk action
clears stale table/details rather than retaining them underneath an error.

County-specific display fields and strict HTTPS host/path/query/parcel link rules
live in the Isanti adapter. Fixed-label links open only on user clicks, never
through embeds, automatic report requests or local file routes. Lineage contains
run IDs, fields, dates and hashes, not operation paths or correspondence contents.
Only the explicitly selected review's inventoried comparison can supply parcel-
specific sampled findings; missing source-hash/date binding is disclosed and no
historical sample discovery or general/current verification is implied.

ML-205 adds pure immutable [worklist projection/serialization](worklist-exports.md)
and county-isolated saved issue-table allowlists. The service revalidates on Preview
and on each native deferred download, checks the semantic preview fingerprint,
reuses exact parcel source-row/year/money validation, and returns only bounded
in-memory bytes. Filters/scope changes revoke old jobs via per-session events;
thread errors use a queue and clear stale views on the next interaction. Download
threads do not touch session state. Candidate rows are distinct filtered/selected
IDs across pages; snapshot-wide issue/accounting entries remain separate. CSV text
protection is disclosed; JSON retains canonical exact-decimal strings/nulls. Saved
outputs, raw inputs and latest pointers are never modified. ML-206 still owns
browser/clipboard/accessibility release checks, not claimed by AppTest.
