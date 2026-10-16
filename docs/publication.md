# Complete-run publication and shared readers (ML-127)

New runs use a version-2 completion protocol. Historical datasets, results,
correspondence and manifests are not modified or retroactively certified.
No live acquisition or production reimport was performed for this implementation.

## What becomes usable

| Kind | Run directory below configured data root | Completion stage / outputs |
|---|---|---|
| `parcel_raw` | `raw/isanti/<id>` | Raw-complete metadata, counts, ID inventories, ordered pages and available HTTP evidence. |
| `delinquency_raw` | `raw/isanti/delinquency/<id>` | Raw-complete exact file/mapping/supporting bytes, validated records and captured hashes. |
| `parcel_processed` | `processed/isanti/parcels/<id>` | Four parcel exports, normalization diagnostics, accounting, execution/operation manifests. |
| `delinquency_processed` | `processed/isanti/delinquency/<id>` | All nine join exports, source-row accounting, diagnostics and operation manifest. |
| `review` | `processed/isanti/review/<id>` | All seven review CSVs, summary and pinned input evidence. |

IDs are UUIDs, reserved with exclusive directory creation; actual source/capture
and execution dates remain in manifests. A reserved directory is **logically
staging**, regardless of its final-looking name. It is never eligible merely
because it contains `manifest.json`, `summary.json`, exports or hashes.

Writers close all artifacts, enumerate/hash them, reconcile required outputs and
counts, then validate `completion.pending.json`. They install `completion.json`
using a same-directory atomic replacement and update the kind root's `latest.json`
using another same-filesystem replacement. This publishes a completion record,
not a rename of the whole directory. The run itself is not overwritten or reused.
Existing flat parcel exports are left untouched as historical/non-authoritative
files; new parcel results and `execution.json` live in their immutable run directory.

Successful raw acquisition and successful processing are distinct. A later filter,
normalization, export or processed-publication failure does not invalidate an
already completed raw acquisition. It does not produce a successful processed run.

## Pinned bytes and evidence

File import captures the bounded mapping before parsing it. Its retained mapping
is validated against the original reference base before any source/supporting file
is copied. Invalid/unsafe mappings leave private mapping/failure evidence without
copying their referenced files. Normalization uses the exact retained file,
mapping and safely resolved/copied supporting documents, never a later reread of
mutable originals. Captured hashes are fixed before normalization and checked
again before raw completion. Source metadata retains the raw capture timestamp.

Every processed run copies its selected, validated complete input runs under
`inputs/<label>/<source-id>`. Copying is bounded by the captured file sizes and
checked against the captured hashes; shortening, growth or modification fails.
The new run validates those pinned copies before normalization and again before
publication. Reviews pin their join, which already pins its exact parcel and file
inputs. The dependency graph has a bounded depth and only the declared kind/label
relationships are allowed. No absolute operation/provenance path is followed to
substitute an unverified input; new readers resolve the completion graph's contained
relative references. Historical execution locations inside copied provenance are
preserved as evidence, not rewritten or used as read instructions.

`completion.json` has `schema_version: 2`, kind/county/run identity, complete stage
and status, timezone-aware creation time, complete relative artifact inventory
(sizes and SHA-256), source completion hashes, and explicit output row counts.
Its `provenance.schema_version` remains **1**, with code/runtime/configuration
identity. These two schema versions describe different records.

The [shared validator](../src/mn_land/runs.py) checks identity, supported version,
failure/completion state, required outputs, actual bytes/hashes, source graph,
and [content accounting](../src/mn_land/run_checks.py). Unsafe absolute/traversal/
alternate-stream/device paths, duplicate inventory names, symlinks, escaping or
cycling directories, missing/extra files and changed sources are rejected. JSON
completion records are capped at 8 MiB; other JSON evidence reads at 128 MiB;
inventories at 10,000 files with a 20,000-entry traversal budget. These are local
engineering protections, not county limits. Windows uses extended-length paths
internally for nested evidence; no permissions are weakened.

## Accounting and unknowns

GIS IDs are partitioned into normalized and quarantined records, with exact
OID/page/feature locations for error diagnostics: retrieved = normalized +
quarantined. Missing optional-value warnings are not counted as quarantines.
Raw acquisition metadata, original recorded hashes, counts, ID inventories, page
sequence/order and transfer flags are reconciled again by readers.

Each file record belongs to exactly one matched, unmatched or ambiguous source-row
partition. Duplicate-review rows overlap that partition and are not added to it.
Prior-year/current-year/unverified-period row sets are disjoint; parcel-level
prior/current views may overlap. All nine exports and seven review CSVs have
declared inventories and actual row-count checks. Valid empty candidates/review
buckets retain usable headers and complete markers, unlike incomplete results.

Source holds remain effective, and unknown abbreviated balances are not summed.
This does not add a county interpretation, tax-currentness claim, source
transaction guarantee, legal conclusion or owner circumstance inference.

## Readers, latest and legacy

Status, automatic latest, explicit parcel loads, new joins/reviews, and optional
report-worklist consumers use the same completion validator. A valid latest pointer
is authoritative for its kind. If missing/stale/invalid, selection checks complete
eligible runs by recorded creation time, emits diagnostics and falls back to a
valid prior run. Invalid, failed, staging and legacy runs are not usable results;
no eligible run produces a clear error, not an empty success.

Historical runs without version-2 completion remain **legacy/unverified** in
status and are excluded from automatic selection. `load_parcel_snapshot(...,
allow_legacy=True)` is a deliberate read-only inspection path: it requires an
explicit record count, checks available hashes/pages/schema, discloses missing
checks, and never creates a marker. It cannot downgrade a new-protocol staging,
failed or invalid completed run. There is no silent legacy fallback in producers.
[ML-123 portable user-selected replay](replay.md) is available for completed
version-2 inputs, not migration/certification of pre-completion inputs. Backups
remain ML-128.
Existing CSV/JSON files remain on disk for historical inspection.

Reviews no longer write beneath and mutate a completed join. Report-comparison
scripts write separate private comparison evidence beneath their evidence folder,
not inside completed reviews. A new review may explicitly capture that JSON with
`review-delinquency ... --comparison <file>`; no unversioned comparison is silently
discovered. Comparison shape/counts are validated, copied and hashed, and remain
advisory corroboration without changing authoritative parcel/tax status.

## Failures and limits

After reservation, failures retain inputs/partial artifacts and bounded
`failure.json` diagnostics where writing remains possible (stage, error class,
reason, counts, time). A failure marker makes even an installed completion record
ineligible if a later pointer update failed; previous successful files/pointers
are not rewritten. Disk-full/permission/hash/collision/cross-device errors fail
closed. Abrupt termination can leave no diagnostic; absence of a valid completion
is sufficient to reject staging. Pending pointers are not inputs or successes.

Atomic replacement is based on Python's [filesystem operation](https://docs.python.org/3.12/library/os.html#os.replace).
This is a local-filesystem completion protocol, not power-loss durability, a
distributed transaction/lock across sync clients, a signature, an OS sandbox or
protection against an authorized local actor rewriting all evidence. It does not
claim off-device backup or a point-in-time county database version. Pinning
duplicates evidence and uses additional private disk space; no historical files
are deleted to recover space.

## Regression evidence

[R01-R07 tests](../tests/unit/test_run_publication.py) cover captured-original edits,
retained-input tampering, every parcel/join/review export failure, normalization,
hash/manifest/marker/pointer failures, malformed inputs, invalid/legacy manifests,
malicious paths/pointers, symlink escape, exclusive concurrent identity reservation,
empty candidates, quarantines, period overlap and holds. Existing ingestion and
normalization tests now create genuine synthetic complete source runs rather
than blessing historical fixture directories. See [testing](testing.md) for results.
