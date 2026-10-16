# Ingestion contracts and hardening plan (ML-119)

Status: discovery complete; ML-125 subsequently implements section 2 and F01-F09
as described in [validation](validation.md). ML-126 implements section 3 and H01-H08
as described in [retrieval](retrieval.md). ML-127 implements section 4 and R01-R07,
as described in [publication](publication.md). Historical discovery behavior was inspected at baseline commit
`4374e65b5bda9d15ab2f3aaf4b4110060f85ffa0`. ML-125, ML-126, and ML-127 own
implementation and regression fixtures. Scope is existing Isanti ingestion,
normalization boundaries, and safe output publication, not new county semantics,
UI, GIS analysis, scoring, financial aggregation, or a new storage stack.

## 1. Evidence and current behavior

| Evidence | Inspected material | What it establishes |
|---|---|---|
| E01 | Retained `data/raw/isanti/2026-08-23T233353Z/layer_metadata.json` and `2026-10-14T142655494922Z/layer_metadata.json` | Both have SHA-256 `276a4adbfe4099785d68e89e0edd1650a72f8cc788404c95b1204fbee8d4cd39`: no metadata-byte or field/type/alias/nullability drift between these two captures. Not a fresh live-service check. |
| E02 | [County mapping](counties/isanti.md), [confirmed year convention](counties/isanti-tax-year-confirmation.md), [reviewed import mapping](counties/isanti-delinquency-2026-10-13.mapping.json) | Authoritative year interpretation already accepted for this export; balance components/repeated charge semantics remain unresolved. Historical notes must not override the corrected current convention. |
| E03 | [HTTP transport](../src/mn_land/utils/http.py), [ArcGIS client](../src/mn_land/ingestion/arcgis.py), [adapter](../src/mn_land/counties/isanti/adapter.py), [field map](../src/mn_land/counties/isanti/mappings.py) | Actual retrieval, retry, page, field, and normalization behavior. |
| E04 | [File loader](../src/mn_land/delinquency/file_loader.py), [county identifiers/years](../src/mn_land/counties/isanti/delinquency.py), [CLI](../src/mn_land/cli.py) | Actual CSV/XLSX, mapping, value-conversion, and parameter behavior. |
| E05 | [Parcel pipeline](../src/mn_land/ingestion/pipeline.py), [join pipeline](../src/mn_land/delinquency/pipeline.py), [exports](../src/mn_land/delinquency/exporters.py), [review](../src/mn_land/counties/isanti/review.py), [provenance](../src/mn_land/provenance.py) | Preservation/publication ordering and current reader eligibility checks. |
| E06 | [Existing test suite](../tests/unit), [repeatable synthetic probe](../scripts/probe_ingestion_contracts.py) | Existing coverage versus reproduced edge cases; no live government calls or original county rows are needed to reproduce the gaps. |

E01 metadata reports `TaxParcels_Public`, layer 0, `OBJECTID` as a non-null OID,
`maxRecordCount=24000`, and pagination/order-by support. `editingInfo` is absent
(read as null); there is no proven layer-wide edit-version token in these captures.
The configured page size is 2000. These are **retained observations**, not permanent
service limits or a claim that 23,890 records must always exist.

### Reproduced gaps, not fixes

Run `python scripts/probe_ingestion_contracts.py` from an installed checkout.
The script reports current behavior using only synthetic inputs in a uniquely
owned, ignored temporary directory, then removes that directory. It is a discovery
probe, not a permanent test asserting that these bugs should persist.

| Finding | Observed at the inspected baseline | Owner |
|---|---|---|
| D01 | `parse_money("NaN")` and GIS `parse_decimal("Infinity")` return non-finite Decimal values; CLI acreage accepts Infinity. NaN can later raise outside the intended error handling. | ML-125 |
| D02 | Mapping JSON `[]` raises `AttributeError`, rather than the domain file error; some metadata types are stringified instead of validated. | ML-125 |
| D03 | A CSV row wider than its header survives under key `"None"`; a short row's missing trailing value becomes null. Header uniqueness is already checked. | ML-125 |
| D04 | XLSX formula `=100+25` without a cache becomes an unknown monetary value under `data_only=True`; numeric mixed-source years 2024/2025 fail because the county classifier expects strings. | ML-125 |
| D05 | Identifier normalizer accepts numeric `123.5` as `"1235"`; the file loader also stringifies numeric identifier cells before joining. This contradicts the intended no-numeric-coercion boundary. | ML-125 |
| D06 | One feature with no OBJECTID is accepted; two missing IDs would eventually look like a duplicate null ID. Advertised page limit 1 does not reduce a configured request of 2. | ML-126 |
| D07 | HTTP 404 and HTTP 429 with `Retry-After: 30` each make three attempts, sleeping only 0.5 and 1 second. | ML-126 |
| D08 | A directory containing only a manifest with `retrieved_at` can be selected and loaded as an empty GIS snapshot: no required count/page/hash contract is enforced. | ML-127 |

Additional code-inspection findings:

- CSV requires UTF-8/UTF-8-BOM and unique nonblank trimmed headers. It does not
  validate record width or impose an explicit input size/row budget.
- XLSX silently chooses the active sheet; formulas/cached values are not
  distinguished, blank rows are skipped, and the resulting enumerated source-row
  references can differ from real sheet rows. Workbook closure is not in a
  `finally` block. Corrupt archives and several I/O/encoding errors escape the
  user-facing domain error boundary.
- Supporting documents are checked for existence, not resolved-path containment;
  absolute/traversal/symlink escape paths can be followed. Copying by basename can
  overwrite two different supporting files with the same name.
- The ArcGIS client already sorts requests by OID, rejects duplicate seen IDs,
  rejects premature empty pages, and checks final count. It does not validate
  metadata field types/capabilities, exclude boolean counts, reject the first
  null/invalid OID, honor transfer-limit contradictions, or recheck source identity
  and membership at the end. A boolean is an `int` in Python, so current count
  validation is weaker than it appears.
- HTTP defaults are 30-second socket timeout and three **total attempts**; JSON
  decode errors, HTTP errors, URL errors, and timeouts share the same retry path.
  ArcGIS error envelopes/non-object JSON instead raise directly. Successful
  requests have no explicit pacing or bounded response-body read. Settings with
  the same defaults do not automatically wire custom timeout/retry values into
  the adapter's default transport.
- Raw GIS pages preserve parsed JSON values through reserialization, not the
  original HTTP body bytes. Official-file copies preserve original bytes, but
  they occur **after** the file has been parsed/normalized; rejected imports have
  no pipeline-managed raw snapshot. Inputs are reread/copied later, so an edit
  between normalization and copying can make the preserved evidence differ.
- GIS raw `manifest.json` is written after retrieval but before normalization and
  processed exports finish. Root parcel exports use `open("w")` and can replace
  prior results one file at a time. The parcel run ID has only second precision.
- Delinquency/review outputs are uniquely timestamped and mostly exclusive-write,
  which protects prior directories, but can leave partial new directories.
  Join manifest writes and review summary writes are not atomic success markers.
  `status`, latest selection, and explicit loaders do not validate a shared
  success/schema/hash contract. Existing provenance records hashes; readers do
  not generally enforce them before use.
- Individual GIS normalization `ValueError`s are counted/skipped (including the
  two already documented missing parcel IDs); other exception types can abort.
  File-import invalid rows fail the import. Neither is a reason to invent values.

## 2. Input and schema contract — implemented by ML-125

### 2.1 GIS fields and canonical values

The Isanti adapter owns a declared schema contract, rather than hardcoding county
fields into the generic client. ML-125's callback checks declarations before
queries/normalization. ML-126 adds capability, OID, paging and completeness policy.

| Source fields | Expected declared type | Value policy |
|---|---|---|
| `OBJECTID` | `esriFieldTypeOID`, not nullable | Non-boolean integer, non-null, unique during transport (ML-126). No fallback to a guessed OID field. |
| `PARCELID` | `esriFieldTypeString` | Text identity. Trim/remove only the documented county separators for join keys; no padding, numeric coercion, fuzzy matching, or new nine-digit rule. Null/blank/invalid row identity is quarantined with its OID and reason. |
| `DEEDEDACRES` | `esriFieldTypeDouble` | Null stays unknown; non-null must be finite, non-boolean numeric; negative acreage is a row error, not zero. |
| `TOTPRVTXTOD`, `TOTCNTTXOD`, `LNDVALUE`, `IMPRVALUE`, `CNTASSDVAL` | `esriFieldTypeDouble` | Null stays unknown; otherwise finite Decimal conversion. Do not globally reject finite negative accounting adjustments or infer their meaning. |
| `OWNERNME1`, all six `MAILING_FIELDS`, `PRIMARYCLASS`, `LEGALDESCRIPT`, `PARCEL_REPORT` | `esriFieldTypeString` | Text or null; do not stringify arbitrary objects, arrays, or booleans into facts. |

Missing requested field declarations or incompatible declared types fail the run;
added, unrequested fields are allowed and recorded. A renamed field is not
automatically mapped by alias. Changes to mapped aliases are reported for review,
never treated as new tax definitions. Numeric type substitutions require an
explicit adapter allowlist/review, not an unexamined automatic conversion.
For an individual feature, a missing optional attribute remains unknown with a
diagnostic, distinct from a schema-wide missing field. Missing identity or invalid
non-null values yield quarantined GIS rows; preserve raw evidence, OID/source
location, and error counts. Do not silently turn malformed values into null.
These row diagnostics do not excuse malformed transport structures or OIDs.

`--min-acres` must be finite and nonnegative in CLI **and** callable pipeline
entry points; reject booleans and NaN/Infinity with a clear error. Boundary zero
and equality to the threshold remain supported. Keep Decimal calculations.

### 2.2 Reviewed mapping

| Mapping member | Required contract |
|---|---|
| Root | JSON object; malformed JSON/duplicate object keys/non-object roots fail with a domain error. |
| `source_agency`, `dataset` | Nonblank strings; keep the existing Isanti source restriction. A publisher label is not independent proof of origin; human source review remains required. |
| `delinquency_assertion` | Exactly one of the two existing supported assertions; no truthy strings/objects or inferred assertion. |
| `columns` | Nonempty object, `parcel_id` required, known canonical keys only, nonblank string source-header names, no conflicting duplicate source-column assignments. Exact reviewed header matching after existing whitespace trimming. |
| `source_url`, `publication_date`, `verification_hold_reason` | Null or strings; URL must be HTTP(S) when provided, date must be valid ISO `YYYY-MM-DD`, hold must be nonblank when present. No file retrieval is triggered by metadata URLs. |
| `tax_year_convention`, `year_semantics_reference` | Null or existing supported convention/nonblank reference. Every active convention requires a declared retained reference; a mixed assertion also requires the convention. Do not broaden county interpretation. |
| `supporting_documents` | Array of unique, nonblank relative path strings; resolve under mapping directory, forbid absolute/drive/UNC/traversal or symlink escape, require regular files, preserve relative layout and reject destination collisions. Never flatten or overwrite evidence. |
| `review_notes` | Existing optional array of strings; retain the source mapping bytes. Other unknown top-level keys fail clearly so misspelled controls cannot be ignored. |

Preserve existing valid mappings without silently rewriting them. Runtime mapping
version/contract identity can be recorded in new manifests; adding a mandatory
new property to historical mapping files is not required. Invalid metadata and
path errors stop before any referenced external supporting file is copied.

### 2.3 CSV/XLSX and row identity

- Accept only `.csv` and `.xlsx` case-insensitively. Reject legacy `.xls`, macro
  files, corrupt/nonmatching formats, invalid UTF-8, and unavailable dependencies
  clearly. No OCR, delimiter guessing, or spreadsheet recalculation.
- CSV is comma-delimited UTF-8 with optional BOM. Allow proper quotes, embedded
  commas, and multiline fields; require nonblank unique trimmed headers and exact
  record width. Trailing empty **cells** are valid nulls; missing/extra cells are
  not. Skip entirely empty records only under a documented policy and keep their
  positions accounted for. A nonempty file with no usable data rows fails.
- XLSX initially supports one nonempty data worksheet. If multiple sheets contain
  data, fail and request an explicit reviewed selection; do not trust the active
  sheet. An explicit multi-sheet selector is a later scope decision if needed.
  Reject formula/error cells in the selected input sheet, with or without caches;
  request an authoritative values-only export. Close workbooks on every path.
- Parcel identifiers must be stored as text. Reject numeric identifier cells even
  when a number format displays leading zeros; never reconstruct missing digits.
  Accept exact, finite four-digit integral year cells in XLSX as a documented
  representation conversion (including the current mixed convention); reject
  booleans, dates, fractions, missing/invalid/future years. CSV year text follows
  the existing convention. Monetary non-finite values always fail.
- Preserve original rows/cells and source locations before normalization. CSV
  `source_row_number` is its logical record ordinal including the header, not
  the physical line count for quoted multiline text; keep an additional physical
  line range where useful. XLSX references must use actual worksheet name/row
  number, without compacting across blank rows.
- Reject malformed file rows as an import-wide failure with format, source
  location, field, and reason. Do not silently drop them or reinterpret repeated
  rows as duplicates to remove. ML-127 retains failed-input evidence privately.

Implemented local-input engineering budgets: 25 MiB input file, 100 MiB total
expanded XLSX members, 100,000 data records, 256 columns, and 1 MiB per field/cell.
ML-125 additionally bounds archive members to 4096. The proposed 25 MiB HTTP
response cap is now implemented by ML-126's transport, not the local file reader.
Check ZIP expansion before workbook parsing; never extract archive member paths.
Exceeding a budget fails with a diagnostic; it does not truncate data. These are
configurable resource protections, **not county limits**. The retained
CSV is 608,656 bytes and the documented report has 1,783 records, so this fixture
fits comfortably. Record effective budgets; revising them does not authorize
bypassing a public service's smaller limits.

## 3. Retrieval/completeness contract — implemented by ML-126

1. Validate metadata as an object with expected layer identity, Query capability,
   declared OID, requested fields/types, positive non-boolean `maxRecordCount`,
   and explicit pagination/order-by support. Call ML-125's schema gate. Reject
   unsupported capabilities rather than silently switching methods or scraping.
2. Effective page size is `min(configured_positive_page_size, advertised_limit)`.
   Counts are nonnegative integers, never booleans. Request only mapped fields
   and no geometry; continue using an ordered OID query.
3. Capture initial count and `returnIdsOnly` membership for the same predicate;
   require unique valid IDs and matching count. Retain these raw responses. If
   the inventory exceeds service/response budgets, fail explicitly; no assumption
   that ID responses are unlimited and no new batching strategy in this card.
4. Each page is an object containing a feature list; each feature has an attribute
   object and valid expected OID. Enforce membership, uniqueness, ascending order,
   response size, and requested effective page length. Advance by records actually
   returned. Short nonempty pages can continue if the continuation state is not
   contradictory. Fail premature empty pages, duplicate/missing/extra IDs,
   malformed arrays, and transfer-limit flags contradicting final completeness.
5. At the end, reread count, ID inventory, and metadata fingerprint. Reject changed
   count/membership/requested schema/capabilities, and reconcile the fetched OID
   set and raw page counts exactly. A consistent zero-record source is valid with
   an explicit empty-source warning; it is not proof that parcels became current.
6. Record start/end observations and consistency limitations. Same IDs/counts do
   **not** prove unchanged attribute values. Use a service edit token when actually
   available and retain its evidence; absent `editingInfo` remains unknown, not a
   fabricated version. No point-in-time/transactional source guarantee is claimed.
7. Preserve bounded original HTTP body bytes alongside the existing parsed JSON
   artifacts and hash both, without changing their county values. Keep failures'
   relevant response evidence privately, avoiding credentials in diagnostics.

Retry/pacing policy is an engineering default, not a promise from the county:

| Case | Required handling |
|---|---|
| HTTP 400/401/403/404, invalid query/schema/auth error | Fail without retry; no bypassing controls or credential discovery. |
| HTTP 408/429/500/502/503/504, transient timeout/connection failures | At most three total attempts, finite 30-second socket timeout per attempt, sequential requests. |
| JSON decode failure | Bounded retry within the same attempt budget; preserve diagnostic body. An object of the wrong schema is a validation failure, not an endless retry. |
| ArcGIS JSON error object | Classify explicit documented transient codes only; otherwise fail clearly. Do not retry every application error or infer success from HTTP 200. |
| `Retry-After` | Parse both delta-seconds and HTTP-date. Wait at least the server delay plus applicable pacing/backoff requirements; never clamp and retry earlier. Invalid/past dates use bounded fallback. |
| Local wait budgets | One-second minimum request spacing, exponential backoff starting at one second; at most 60 seconds for a single wait and 120 seconds cumulative wait. If a server asks longer than remaining budget, stop respectfully with a retry-later diagnostic rather than retry early. |

Inject clocks/sleep into tests; do not actually wait or call government APIs.
Record effective attempts, timeouts, waits, page limits, and source checks in run
metadata. Validate configuration and wire it into the actual transport instead of
assuming similarly named Settings fields are applied. No automatic cached-source
substitution is introduced. Retained snapshots are dated inputs, not a live cache.

Protocol references, not county accounting authority: Esri's
[layer resource](https://developers.arcgis.com/rest/services-reference/enterprise/layer-feature-service/)
and [query documentation](https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/)
describe advertised capabilities, pagination, and ID queries. HTTP
[`Retry-After`](https://www.rfc-editor.org/rfc/rfc9110.html#name-retry-after)
supports a delay or HTTP-date. The
[openpyxl loading documentation](https://openpyxl.readthedocs.io/en/stable/tutorial.html#loading-from-a-file)
explains cached-value loading; this plan deliberately refuses formulas rather
than treating a cache as an authoritative freshly calculated value.

## 4. Failure/publication contract — implemented by ML-127

Separate **complete raw acquisition** from **successful processed publication**.
A GIS retrieval can be complete even if a later export fails. A raw file copy is
not a valid normalized import merely because its bytes were retained.

| Stage | Eligibility and failure rule |
|---|---|
| Reserved / staging | Exclusive unique run identity; never reuse an existing run directory. Stage on the destination filesystem. Snapshot selected source/mapping bytes before normalizing, then parse those exact copies; resolve supporting paths safely before copying. |
| Raw complete | Versioned manifest validates source identity, input inventory/hash/count/page reconciliation, and retrieval completion. May retain explicit quarantined row diagnostics for later normalization. Partial/invalid imports retain private failure evidence, not an eligible raw-complete marker. |
| Processed staging | Write all expected outputs and quarantines; normalize from pinned complete inputs, check counts/lineage/status separation, and hash the completed artifacts. No consumer reads staging. |
| Processed complete | New versioned manifest declares run kind, county, run ID, complete status, source snapshot IDs/hashes, configuration/code/runtime identity, complete output inventory/hashes, and row accounting. Install the validated completion record/final directory atomically on the same filesystem, after closing writers. |
| Failure / interruption | Preserve staging/raw evidence and a bounded `failure.json` where possible: failed stage, error class/reason, location, counts so far, time. Hard process termination may leave no diagnostic; lack of completion alone still makes it ineligible. Never update success/latest pointers. |
| Reader / status / latest | One shared eligibility check for `status`, latest selection, explicit loads, and reviews. Validate manifest version/kind/county/status, required files/counts and actual hashes, not merely filename existence or lexical directory order. Skip invalid/failed/staging runs with diagnostics; fail clearly if no eligible run remains. |

Use new manifest version 2 for the added completion protocol; preserve the ML-120
provenance object and distinguish its own `schema_version`. Resolve staged output
references to final paths before publication; hashes must describe the bytes
actually published, not later rereads of mutable originals. Validate path
containment when reading manifests as well as copying supporting documents.

GIS accounting must satisfy retrieved = normalized + quarantined, with actual
OID/source locations for quarantines. File imports do not skip invalid rows.
Every original file record must be represented in the join's disjoint matched /
unmatched / ambiguous source-row accounting; duplicate-review files overlap that
partition and must **not** be summed into it. Prior/current parcel views may
overlap while their contributing source-row sets stay disjoint. Preserve holds
and unknown monetary totals. Check the nine join exports and seven review CSVs
against a declared inventory, not whatever files happen to remain in a directory.

Move parcel processed exports into immutable per-run directories. The old flat
parcel output paths cannot be updated atomically as a group; if retained for
compatibility, label them non-authoritative conveniences and use an atomically
replaced pointer to a complete run as the authority. Fail closed on cross-device
promotion, directory collision, disk-full/permission errors, or hash failure.
Do not claim a filesystem rename alone guarantees power-loss durability.

Do not backfill complete status, assumed code versions, or missing hashes into
historical snapshots. Show legacy runs as legacy/unverified in status; exclude
them from automatic new-protocol latest selection. Explicit read-only legacy
access requires a deliberate compatibility path and validated available evidence,
with missing checks disclosed. Portable user-selected replay and migrations stay
in ML-123; backups/restores stay in ML-128. Raw county data and diagnostics remain
ignored/private and are never added to CI fixtures or GitHub artifacts.

## 5. Prioritized fixture matrix

F01-F09 are implemented and traced in [validation](validation.md).
H01-H08 are implemented by ML-126 in the source/HTTP fixtures linked from
[retrieval](retrieval.md). R01-R07 are implemented in
[publication fixtures](../tests/unit/test_run_publication.py); see [publication](publication.md).
Construct sanitized inputs; mock transport, clock, file failures, and inventories.
The discovery probe confirms selected gaps but does not replace implementation
regressions. P0 fixtures gate the owning story; P1 fixtures also belong to that
story before Done, with ordering intended to tackle highest factual risk first.

| IDs / priority | Owner | Inputs / cases | Required assertion and existing starting coverage |
|---|---|---|---|
| F01 P0 | ML-125 | Mapping array/null/duplicate keys, wrong types, unsupported assertions/keys, malformed dates/URLs, empty names | Domain errors before normalization/copy; current file tests cover a missing mapped column, not these metadata shapes. |
| F02 P0 | ML-125 | Missing/renamed/type-changed requested GIS fields; added unrelated fields; malformed feature values | Fail schema drift, allow unrelated additions; distinguish null from invalid/quarantined values. Start with `test_isanti_adapter.py`. |
| F03 P0 | ML-125 | NaN/sNaN/positive-negative Infinity, booleans, fractions where forbidden, malformed numeric text; zero/null/threshold equality | Finite Decimal/acreage contract; valid null and finite negative money survive. Existing numeric/money tests cover ordinary/null values. |
| F04 P0 | ML-125 | CSV BOM, whitespace/duplicate/blank headers, short/long records, trailing empty cells, quoted commas/multiline, invalid encoding | Exact widths, valid quotes, original rows/locations; retain current October-schema multiline success fixture. |
| F05 P0 | ML-125 | Text IDs with leading zeros/separators, numeric/scientific XLSX IDs, letter-containing IDs | No coercion/padding; exact documented keys only. Start with `test_parcel_id.py`; update permissive placeholder `"x"` fixture where needed. |
| F06 P0 | ML-125 | CSV and typed XLSX ASMTYR/TAXYR; boolean/fraction/date/future/missing years; mixed/generic sources | Equivalent valid typed years classify the same; no wall-clock reclassification or new monetary meaning. Existing tax-period tests cover string-year cases. |
| F07 P0 | ML-125 | Cached/uncached formulas, error cells, multiple populated/hidden sheets, blank interior rows | Refuse ambiguous workbook selection/formulas; correct sheet/row lineage and closure on failure. Existing XLSX test covers one ordinary active sheet only. |
| F08 P0 | ML-125 | Absolute/UNC/drive/traversal/symlink escapes, missing documents, duplicate destinations, mismatched year reference | No escape/collision reads or copies; valid nested references preserved. Temp fixtures only. |
| F09 P1 | ML-125 | Empty/header-only files, corrupt XLSX/ZIP, unsupported extension, exact/over resource budgets | Domain error without truncation/leaked handles; existing unsupported-extension case is retained. |
| H01 P0 | ML-126 | Bad metadata, missing OID, boolean/negative counts, no Query/order/pagination, invalid configured limits | Fail before pages; schema validation delegates to ML-125. |
| H02 P0 | ML-126 | Advertised lower/equal/higher page max; page over requested length; partial final page | Correct effective request/offsets, no hardcoded 24,000 limit. Existing pagination happy path remains. |
| H03 P0 | ML-126 | Missing/null/bool/string/repeated/extra/out-of-order OIDs; malformed features/attributes | Fail with source page/record; existing duplicate-ID test remains. |
| H04 P0 | ML-126 | Empty-before-end, short pages, transfer-limit contradictions, zero count/inventory | No silent truncation; valid zero is explicit empty evidence, not a payment inference. |
| H05 P0 | ML-126 | Start/end count or ID-set changes, equal-count replacement, metadata drift, absent edit token | Reject detectable changes; disclose unchanged-ID attribute consistency as unknown. |
| H06 P0 | ML-126 | 400/401/403/404 versus 408/429/5xx, transient network failures, success after retry, exhausted attempts | Exact attempt classification; existing HTTP error tests remain and expand beyond one-attempt failures. |
| H07 P0 | ML-126 | Retry-After seconds/date/malformed/past/too-long, pacing, invalid timeout/retry configs | Mocked waits respect budgets; too-long delay fails instead of retrying early. No real sleeps. |
| H08 P1 | ML-126 | Malformed JSON, non-object JSON, ArcGIS transient/permanent errors, oversized/body-truncated responses | Bounded behavior, retained original body and parsed-payload hashes; no cached substitution. |
| R01 P0 | ML-127 | Source/mapping edited during validation; tampered raw page/input hash | Normalize from exact retained copies or fail; source bytes and provenance agree. |
| R02 P0 | ML-127 | Inject failure at source copy, normalization, each export, hashing, manifest write, promotion/pointer update | No partial result is eligible; prior complete runs/pointer remain usable; failure diagnostics retained where possible. |
| R03 P0 | ML-127 | Manifest-only/newest-invalid directories, absent/wrong complete marker, missing/mismatched output inventory | Shared readers/status exclude invalid latest; use valid prior run or fail when none remains. Probe D08 now reports rejection. |
| R04 P0 | ML-127 | GIS quarantine, unmatched/ambiguous/duplicate source rows, mixed prior/current overlap, holds | Exact disjoint source accounting, no double-counted duplicates or money, known missing-ID diagnostics retained. Existing join/period tests are starting coverage. |
| R05 P0 | ML-127 | Concurrent/same-time IDs, preexisting output, disk-full/permission/cross-filesystem errors | Exclusive identity, no overwrite, no false success or destructive cleanup. Existing successful timestamped import is not a collision/failure test. |
| R06 P1 | ML-127 | Interrupted/staging run, stale pointer, malicious manifest paths, legacy unversioned inputs | No automatic eligibility by filename; explicit legacy limitations; no rewrite/delete of historical evidence. |
| R07 P1 | ML-127 | Successful empty candidates, nine join outputs, seven review CSVs, parcel compatibility paths | Declared complete inventory/hashes and stable authoritative run pointer; empty candidates differ from incomplete output. |

Existing offline default selection/network guard/CI remain the verification
boundary: see [testing](testing.md). A new required fixture should run locally and
in the existing four-job matrix, without reading this workstation's actual county
data. Keep deterministic clocks/IDs separate from county dates.

## 6. Bounded delivery decisions and unresolved limits

1. **ML-125 implementation:** input/schema/numeric/path validation and the F01–F09
   matrix. County schema ownership stays in the adapter. Joins, financial meanings,
   and the run publication protocol are unchanged.
2. **ML-126 after ML-125:** implement actual transport limits, retry/pacing/body
   capture, inventories, and H01–H08. It depends on the schema gate; it does not
   add scraping, cache refresh jobs, or an alternate county/API.
3. **ML-127 after both:** implement staging/completion/read eligibility and R01–R07
   across existing parcel/import/review consumers. Do not absorb the portable
   replay, UI, or private backup features of other cards.

The backlog records this dependency chain explicitly; readiness is not automatic
authorization to implement all three. Each owner completes their matrix and docs
before the next dependent card is pulled. Normalization changes must compare
valid synthetic outputs to current semantics and account for any new quarantine.

Open limitations remain explicit: no authoritative monetary component/charge-key
dictionary (ML-117/ML-122), no county identity crosswalk for unmatched records
(ML-121), no proved atomic government dataset version, and no guaranteed power-
loss durability or off-device data recovery. None blocks this discovery spike or
authorizes guessing. New service schema changes require adapter review; newly
documented county meanings require their own evidence-backed task.

## 7. Discovery validation record

Reviewed E01–E06, compared the two retained metadata files, ran the synthetic
probe, and traced each finding to a planned fixture and a bounded owner. No
production ingestion/normalization changes or live government requests were made.
Existing snapshots/listings/correspondence remain unchanged. Local verification
passed 72 default offline tests (one live test deselected), Ruff, the 13-epic /
84-story board check, and 213 relative documentation links/anchors. At discovery
completion the production `src/` and existing `tests/` trees were unchanged;
subsequent ML-125 implementation is documented in [validation](validation.md). Hosted CI for the completion
commit is available from its GitHub checks; local results alone do not imply a
hosted pass. The backlog records discovery completion, not implementation of the
planned F/H/R fixtures.
