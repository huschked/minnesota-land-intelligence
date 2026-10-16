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

## Planned local viewer (ML-201 decision, not implemented)

[The UI plan](ui-plan.md) selects a thin read-only Streamlit interface over a
framework-independent review service using existing completion/source validation.
It specifies explicit loading, canonical view/filter/identity handling, separate
source warnings, escaped details and safe contextual exports. No source normalization,
acquisition/replay, scoring or hidden balance aggregation belongs in widgets.
Session DTOs retain validation time; new disk reads/reload/export revalidate rather
than caching trust by pathname. The actual county data is legacy, so ML-130 supplies
eligible real inputs and ML-206 has a real-data/accessibility release gate. No UI
source, optional dependency, runtime server or data migration is added by discovery.
