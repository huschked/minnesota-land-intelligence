# Strict input validation (ML-125)

ML-125 implements the F01-F09 input/schema portion of the
[ingestion contract](ingestion-contracts.md), not ML-126's HTTP hardening or
ML-127's complete-run publication. No runtime dependency or county interpretation
was added. Retained county inputs/results were not reimported or rewritten.

## Accepted input

- Mapping JSON must be an object with unique keys, known controls, correctly typed
  nonblank metadata, supported assertions, explicit canonical columns, ISO dates,
  and optional HTTP(S) URLs without embedded credentials. Duplicate source-column
  assignments/misspelled controls fail. An Isanti publisher label alone is not proof
  of source authority. Any active year convention requires a declared retained
  reference; mixed assertions also require the existing supported convention.
- CSV is comma-delimited UTF-8 with optional BOM, nonblank unique trimmed headers,
  and exact record widths. Quoted commas/multiline fields and trailing empty cells
  are supported. Physically blank records are skipped but their ordinal positions
  and scan budget are retained. Explicit empty cells still require a parcel ID.
  No delimiter guessing, width repair, encoding fallback, or dropped bad rows.
- XLSX requires one nonempty data worksheet and a row-1 header. Empty active sheets
  do not hide data sheets. Multiple populated sheets (including hidden ones),
  formulas with/without caches, error cells, macros, corrupt ZIPs, and XML DTD/entity
  declarations fail. Workbooks close on failure. Worksheet dimensions are reset
  so underreported dimensions cannot hide bad cells. Omitted trailing spreadsheet
  cells are null within the header's grid; nonempty extra columns fail.
- Parcel IDs must be text. Numeric/scientific cells fail even with a leading-zero
  display format. Only documented county separators are removed; no padding,
  truncation, fuzzy join, new nine-digit rule, or ownership reconciliation.
- Years are four ASCII digits or exact finite integral cells (1000-9999).
  Booleans, dates, fractions, missing/malformed required years, and ASMTYR after
  TAXYR fail. County payable-year conversion and prior/current separation are
  unchanged and do not use execution date.
- Numbers must be finite, non-boolean, and unambiguous. Monetary parsing accepts
  properly grouped thousands, optional currency prefix, and parenthesized negative
  accounting values. Malformed grouping, embedded currency characters, objects,
  NaN/Infinity fail. Null/blank stays unknown; finite negative money is preserved.
  CLI and callable minimum acreage must be finite/nonnegative; negative parcel
  acreage is a row error, not zero. Unknown abbreviated balances remain unmapped
  and are never summed.

The mapping template now has distinct placeholder columns; human replacement is
still required. Actual reviewed mappings and their source bytes are unchanged.

## Evidence and lineage

Supporting references must be unique portable relative `/` paths. Absolute,
drive/UNC, traversal, reserved-device/ambiguous, and symlink-escape paths fail.
References resolve to regular files under the reviewed mapping directory; aliases
and case-folded destination collisions fail. Nested evidence is retained under
`snapshot/supporting/<relative path>`, not flattened by basename.

`DelinquencyMapping.from_json` can explicitly receive
`supporting_root=snapshot / "supporting"` to validate retained copies. That is not
a new portable replay CLI. Containment assumes stable filesystem paths. Source
copying and complete-run publication now use [ML-127's pinned-input protocol](publication.md).
This validates captured bytes before use; it is not a universal filesystem sandbox
or distributed transaction.

`SourceMetadata` adds `source_sheet`, `source_line_start`, and `source_line_end`.
CSV row numbers are logical record ordinals (including header/blank records),
with physical line ranges for multiline records. XLSX keeps real sheet/row
positions across blank gaps. Reviews use the same reader rather than compacting
source-row numbers and now handle retained CSV or XLSX inputs.

Unmapped spreadsheet dates/times retain typed JSON-safe evidence using
`{source_cell_type, iso8601}`; durations retain days/seconds/microseconds. They are
not canonical years/names/amounts; incompatible mapped date cells fail. Ordinary
CSV strings and valid typed years are unchanged. Original workbook bytes remain
the primary raw evidence.

## GIS validation and quarantine

The [Isanti schema module](../src/mn_land/counties/isanti/schema.py) owns requested
field types/nullability. Its callback runs after metadata retention but before
count/page queries; the generic client has no county field names. Missing,
renamed, duplicate or type-changed mapped declarations fail. Added unrequested
fields are recorded. Changed aliases warn, never enable GIS delinquency claims.

Optional nulls remain null. Missing optional attributes carry
`SourceMetadata.validation_warnings`; malformed non-null values or identity
become explicit row errors. New parcel runs write `normalization_diagnostics.json`
with severity/field/reason, source record ID and retrieval ordinal. Retained
snapshot loads identify raw page/feature position. New join manifests/review
summaries retain the diagnostics and counts. File import rows instead fail the
whole import. Legacy snapshots without metadata get an explicit warning, not an
assumed schema pass. Shared complete-run eligibility is implemented by [ML-127](publication.md).

## Engineering resource limits

The immutable [InputLimits](../src/mn_land/config/input_limits.py) defaults are not
county service limits:

| Budget | Default |
|---|---:|
| Local input/mapping file | 25 MiB |
| Expanded XLSX content | 100 MiB |
| Scanned data records/worksheet rows, including blank gaps | 100,000 |
| Columns | 256 |
| UTF-8 bytes per field/cell | 1 MiB |
| XLSX archive members | 4,096 |

Actual reads are bounded, not just the initial file-size stat. ZIP declared and
actual decompressed sizes/member counts are checked before workbook loading;
nothing is extracted. Exceeding a budget fails, never truncates. Callable readers
and importers accept positive-integer `InputLimits` overrides; new join manifests
and provenance record effective values. CLI uses defaults. HTTP response limits
are implemented separately by [ML-126](retrieval.md). This is not an OS sandbox or universal malware scanner.

## Verification

| Groups | Regression tests |
|---|---|
| F01, F08 | [Mappings and evidence paths](../tests/unit/test_mapping_validation.py) |
| F02 | [Schema, rows and quarantines](../tests/unit/test_schema_validation.py) |
| F03, F05, F06 | [Numbers, IDs and years](../tests/unit/test_numeric_validation.py) |
| F04-F09 | [CSV/XLSX and resources](../tests/unit/test_tabular_validation.py) |
| F04, F06, F08 | [Import/review/copy integration](../tests/unit/test_validation_pipeline.py) |

Use the [offline suite](testing.md), Ruff and board validation. The synthetic probe
reports D01-D05 rejection (and valid typed years). ML-126 subsequently fixes
D06/D07; ML-127 subsequently fixes D08's publication/reader gap as well.
The probe does not assert that bugs must persist.
Tests use sanitized fixtures and owned temporary files, not actual county rows.
Windows strict path resolution may need unsandboxed filesystem access; do not
weaken containment when resolution fails. The real symlink fixture is skipped
when an account cannot create links; Linux CI exercises it. Live government tests
are collected only, not executed for this card.

Library references: [read-only mode/dimensions](https://openpyxl.readthedocs.io/en/stable/optimized.html)
and [workbook loading](https://openpyxl.readthedocs.io/en/stable/tutorial.html#loading-from-a-file).

Verified implementation: [CI run 38678405055](https://github.com/huschked/minnesota-land-intelligence/actions/runs/38678405055)
passed 283 tests on all four Windows/Linux x Python 3.11/3.12 jobs, including the
real symlink case. Local verification passed 282 with one privilege-related
symlink skip; the live test was deselected everywhere. See [testing](testing.md).
