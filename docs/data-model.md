# Data model

`Parcel` is the county-independent record. Money uses `Decimal`; acreage also uses `Decimal`. Missing values remain `None`, never zero. Geometry is optional because Phase 1 does not perform spatial analysis and avoids transferring large polygons by default.

`previous_taxes_owed` is a cautious source-aligned concept. `past_due_tax_amount` is populated only when authoritative documentation proves the source field represents past-due or delinquent tax. `tax_semantics_verified` records that gate. The Isanti Phase 1 mapping currently leaves `past_due_tax_amount` null.

`SourceMetadata` records agency, dataset, service/layer, retrieval time, field mapping, and source semantics notes. The raw record remains available in immutable run artifacts rather than being embedded in every processed row.

## Delinquency

`DelinquencyRecord` is county-independent and preserves both the original parcel identifier and normalized join key. Optional taxpayer/owner/address, delinquent years, tax, penalty, and combined balance fields remain `None` when absent. Money uses `Decimal`; missing years are `None`, not an empty factual assertion. Source metadata includes publication date, source row, original identifier, and normalized identifier.

`DelinquencyStatus` supports `VERIFIED_DELINQUENT`, `VERIFIED_NOT_DELINQUENT`, `UNVERIFIED`, `UNMATCHED`, and `AMBIGUOUS`. The default source path requires one authoritative row joined to one parcel by an exact normalized key. It does not assign `VERIFIED_NOT_DELINQUENT` from absence, because absence from a dated list does not prove current status.

The county-confirmed mixed-source path additionally supports `OVERDUE_CURRENT_YEAR`.
Each record carries separate `assessment_year`, `taxes_payable_year`,
`report_taxes_payable_year`, and `TaxPeriodStatus`. `delinquent_years` describes
unpaid prior taxes-payable years, not assessment years. Current-year installments
leave delinquent years unknown/null. The convention is tied to the source report
year, so replaying a historical snapshot does not reclassify it using today's year.

When source year/status semantics are confirmed, multiple records may establish
the existence of an unpaid prior-year charge for one uniquely matched parcel.
`ParcelDelinquencyMatch.records` retains every supporting source row. Year sets
are deterministically unioned, while monetary totals and conflicting owner names
are not combined or selected. Candidate JSON includes all source records; the
singular original-row field is null for multiple-row groups. The generic path
continues to hold unresolved duplicate sources as ambiguous.

Duplicate source rows are not summed until the actual source schema establishes that aggregation is semantically valid. They remain visible as ambiguous records.

An optional `verification_hold_reason` propagates from the reviewed source
mapping to each delinquency record. A single exact join with a held record is
`UNVERIFIED`, not `VERIFIED_DELINQUENT`. Exact identity matches remain counted
independently of verified delinquency matches. A hold cannot be released merely
because the source has a positive amount or the parcel meets the acreage threshold.

## Run provenance, schema version 1

New manifest `provenance` objects (or standalone parcel `execution.json`) contain
`code`, `runtime`, `configuration`, `configuration_sha256`, `inputs`, and `outputs`.
The artifact arrays contain absolute `path` and byte-level `sha256`. Configuration
is canonical JSON with sorted keys, compact separators, UTF-8 encoding, and no
NaN; its hash changes when the supplied effective parameters change.

`code.git.revision` and `code.git.dirty` are nullable. Git failures, source archives,
or an unrelated enclosing repository do not create a fictitious revision. An unborn
repository may report dirty state but still has a null revision and unavailable
status. `python_source_files` hashes the loaded package tree's `.py` files, relative
to that tree; `python_sources_sha256` hashes their sorted compact JSON mapping.
This identifies bytes even in an uncommitted tree, but does not archive those bytes.
Installed distributions record actual names/versions, not package-index credentials.
`runtime.constraints_sha256` is null if the development constraints file is absent.
Source dates and tax semantics remain in existing county/source records, not in
these runtime fields. Earlier artifacts without provenance remain valid historical
artifacts with unknown code identity; never backfill an assumed revision.

The proposed distinction between complete raw acquisition and complete processed
publication, manifest version 2, row quarantine accounting, and legacy reader
eligibility is implemented by [ML-127's completion protocol](publication.md),
separately from the version-1 provenance object. ML-125 enforces
finite numeric values and strict input representations at ingestion boundaries;
Python type annotations alone do not supply those checks.

## Input validation lineage (ML-125)

`SourceMetadata` adds nullable `source_sheet`, `source_line_start`, and
`source_line_end`, plus `validation_warnings`. CSV record ordinals preserve blank
records; line ranges preserve multiline locations. XLSX records retain actual
worksheet rows across gaps. Unmapped spreadsheet date/time/duration cells are
typed JSON evidence, not canonical facts; see [validation](validation.md).
Malformed GIS rows retain source ID/location/reason diagnostics while unknown
optional fields remain unknown with warnings. New join manifests record effective
`input_limits` and parcel normalization diagnostics; review summaries retain the
same diagnostics. Historical manifests/outputs are not rewritten or certified.

## Acquisition observations (ML-126)

New parcel manifests add effective `retrieval_policy`, configured/effective page
sizes, actual attempt/wait totals, HTTP-evidence availability, and `source_checks`.
The latter records initial/final counts, schema/capability/edit-token fingerprints,
observed edit tokens, reconciled membership, per-request observation times and
attempt ranges, warnings, and `transactional_snapshot: false`. Retained count/ID
responses and original-body/parsed sidecars are hashed alongside pages. These are
acquisition observations, not a new county fact, proven atomic source version or
ML-127 completion manifest. See [retrieval evidence](retrieval.md).

## Completion manifests, schema version 2 (ML-127)

`completion.json` identifies county, kind, UUID, complete status and raw/processed
stage, timezone-aware time, complete contained relative inventory with size/hash,
pinned source snapshot references/completion hashes and exact output row counts.
`completion.provenance.schema_version` remains 1. A separate immutable operation
`manifest.json` or review `summary.json` retains existing semantic fields.
`reservation.json` records exclusive identity; `failure.json` invalidates failed
runs where diagnostics can be written. `latest.json` atomically references a
complete run and its completion hash. Pending records are not eligible.

GIS accounting explicitly partitions OIDs into normalized/quarantined records;
diagnostics retain raw page and feature identity. Join accounting partitions actual
source-row ordinals into matched/unmatched/ambiguous and disjoint tax-period sets.
Duplicate-review rows overlap, and prior/current parcel views may overlap, without
being added to source totals. Unknown balances and source holds are unchanged.
See [publication and validation boundaries](publication.md).

## Selected inputs and reproducibility (ML-123)

New join operation manifests add `selection` (mode, source run IDs/completion hashes,
date offsets/warnings, optional prior-result reference and comparison outcome) and
`reproducibility` schema version 1 (normalized parcel/record SHA-256, nine export
hashes, sorted candidate IDs). Captured source dates/rows/nulls remain canonical
content; UUIDs, execution identity, paths and quarantine locations are run metadata.
No canonical parcel/tax field or monetary/year meaning changes. Older complete runs
without fingerprints retain unknown historical normalized hashes; legacy inputs do
not gain completion status. See [replay evidence and commands](replay.md).

## Saved snapshot comparison (ML-124)

ML-124's [comparison schema](snapshot-comparison.md) is a separate `comparison`
run, not a mutation of canonical tax status. Its manifest stores explicit as-of
date/age policy and two source contexts; `changes.json` stores the union of listed
IDs, before/after rows/GIS/status/view observations and added/changed/missing/
unchanged categories. Current payment remains unknown and identity relationships
are not inferred. Both complete join graphs are pinned under `before`/`after`.

## Read-only viewer overview (ML-202)

`SnapshotKey` identifies a supported join/review kind and run ID within configured
Isanti result folders. Immutable `SnapshotOverview` is an application projection,
not another parcel/tax source or persisted county model. It carries the selected
completion hash, pinned join/GIS/file run identities, validation/completion times,
listing publication/capture and GIS dates, source agency/dataset/layer, imported
acreage threshold, named counts, unknown-field counts, holds and warnings. Source
run identities are not property parcel IDs. The current overview has no parcel
record array, raw source dictionaries, local filesystem paths or computed debt.

Missing report verification dates remain null: source acquisition, file capture,
result completion and integrity-validation times do not establish report/payment
verification dates. Per-view prior/current counts may overlap and cannot be added
as a unique population. Synthetic provenance/dataset labels are surfaced explicitly.
New disk-backed operations revalidate; an in-memory observation retains the time
it was checked and is not presented as continuously verified. See [the viewer](viewer.md).

ML-203's immutable `ParcelDataset` carries that overview, effective candidate floor
and a tuple of allowlisted `ParcelRow`s: string ID, nullable Decimal deeded acres
and improvement value, nullable classification/GIS owner text, prior/current
membership and existing county review bucket. Period views merge only identical
parcel facts and reject duplicates/conflicts; they never sum tax amounts. No raw
source dictionaries, source URLs, local paths or inferred listing owner are grid
fields. `TableFilters` and `TablePage` describe reproducible in-memory selection,
nonadditive counts, ordering and pagination; `ParcelIdentity` binds county,
snapshot token, completion hash and parcel ID rather than a row offset.

ML-204's frozen `ParcelDetails` adds GIS attributes with source-field labels,
separate prior/current `PeriodEvidence`, and every contributing `ListingRow`.
Rows preserve record ordinal, worksheet or physical CSV lines, literal allowlisted
raw fields (including raw zero/null), independently mapped listing owner text,
charge assessment/payable year, report payable year and recorded category. Source
rows must exactly match captured input bytes and candidate references. Period
year sets must agree with those records. Canonical money remains nullable Decimal;
known values need a reviewed mapping and one matching contributing row, never an
inferred sum across repeated fiscal observations. GIS owner remains independent.

The detail observation includes its integrity-check time, IDs/dates/source hashes,
reviewed year-evidence filename/hash and strictly allowlisted public references.
It is not a persisted county model or current debt/ownership verification. Optional
sample findings are restricted to the selected parcel and pinned review input,
with recorded-year alignment and explicit unknown source-hash/report-date binding.
Local paths, PDFs and correspondence bodies are not DTO fields. Access, buildable
area, zoning, resale value and profit remain not assessed, not zero/low-risk scores.
