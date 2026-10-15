# Architecture

The parcel pipeline is deliberately linear: official ArcGIS service → county adapter → canonical parcel → validation/filtering → exports. `ArcGISClient` owns HTTP, retries, metadata, count checks, and pagination. `IsantiAdapter` is the only module that knows Isanti GIS field names. Core filtering accepts `Parcel` instances and records deterministic rejection reasons.

Phase 1.1 separates source responsibilities. A `DelinquencySource` produces county-independent `DelinquencyRecord` objects from an authoritative delinquency-specific publication. The parcel and delinquency snapshots are normalized independently, joined only by a county-specific deterministic parcel-ID key, and retain independent lineage.

```text
Official parcel GIS -> Parcel -------------------+
                                                   exact normalized-ID join -> status -> candidates
Official delinquency file -> DelinquencyRecord --+
```

Absence from a snapshot does not establish that a parcel is current. Duplicate delinquency rows and duplicate parcel join keys are ambiguous, not silently aggregated. Unmatched source rows are exported for review.

Each parcel run stores layer metadata, request parameters, and each unmodified ArcGIS response page under a timestamped raw directory. Each delinquency import copies the original file and reviewed mapping into a new timestamped snapshot with SHA-256 hashes. Processed join results are also timestamped so historical runs are not overwritten.

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
`find-candidates` writes `execution.json` in the raw run directory, linking those
inputs to the derived exports. Join manifests and review summaries carry their own
`provenance` object. Their self-hashes are deliberately excluded. Historical
snapshots are not rewritten, and the compatibility parcel exports can still be
overwritten by subsequent runs; failure/atomic-publication hardening is ML-127.
