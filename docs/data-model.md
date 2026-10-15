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
eligibility is specified in [ML-119's contract](ingestion-contracts.md). It is not
the current manifest implementation; ML-127 owns that change. ML-125 now enforces
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
