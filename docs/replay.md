# Explicit snapshots and offline replay (ML-123)

Replay reprocesses selected **completed version-2 inputs**, not whatever happens
to be newest. It makes no government requests or new raw captures. It does not
claim current payment status, synchronize source dates, migrate legacy data, or
automatically install/run historical code. No historical county inputs/results
were reimported or changed to implement this feature.

## Commands

Run from the project root in the existing environment. Replace placeholders with
completed directory IDs; do not pass a `manifest.json` file as the snapshot.

```powershell
# New file import, but explicitly select its saved parcel acquisition.
.\.venv\Scripts\python.exe -m mn_land.cli import-delinquency --county isanti --file data/import/county-file.csv --mapping reviewed-mapping.json --parcel-snapshot data/raw/isanti/PARCEL_RUN_ID --min-acres 10
# Reproduce a completed join using its own pinned inputs and recorded threshold.
.\.venv\Scripts\python.exe -m mn_land.cli replay-delinquency --county isanti --snapshot data/processed/isanti/delinquency/JOIN_RUN_ID
# Choose both completed raw inputs; no latest selection.
.\.venv\Scripts\python.exe -m mn_land.cli replay-delinquency --county isanti --parcel-snapshot data/raw/isanti/PARCEL_RUN_ID --import-snapshot data/raw/isanti/delinquency/IMPORT_RUN_ID --min-acres 10
# Replay a moved, self-contained join into a separate processed root.
.\.venv\Scripts\python.exe -m mn_land.cli replay-delinquency --county isanti --snapshot private-copy/JOIN_RUN_ID --output-root private-replay-output
```

Do not combine `--snapshot` with either raw selector. Both raw selectors are
required for a raw pair. Without an optional parcel selector, ordinary imports
retain latest-eligible selection. `find-candidates` remains live acquisition, not
offline replay; `review-delinquency --snapshot` still selects a completed join.
`--output-root` is a processed data root: results go beneath
`<root>/isanti/delinquency/<new UUID>`. It defaults to configured processed data.
Destinations inside selected inputs or any reserved/completed run are rejected.
No output directory or prior snapshot is reused or overwritten.

## Compatibility and dates

Shared completion checks enforce hashes, containment, source graphs, output/row
accounting and exclusion of failed/partial inputs. Explicit parcel selection
additionally requires the configured Isanti service URL/layer and full-county
`1=1` query. The CLI uses the reviewed official adapter; tests inject a synthetic
client. File county and reviewed agency/assertion/schema are independently checked.
Metadata labels/hashes do not independently establish authoritative origin; source
review is still required. Nothing follows input URLs to fetch replacement data.

New joins record `selection`: mode, selected raw IDs/completion hashes and `dates`.
Dates include original parcel acquisition and file capture timestamps, nullable
publication date, exact signed parcel-minus-import seconds as decimal text, and
parcel UTC date minus publication days when known. Non-simultaneous captures,
unknown publication dates and publication dates later than the UTC capture date
are reported in the manifest and CLI. Timestamp fields require timezones.

Different dates are **surfaced, not guessed compatible**. There is no invented
maximum-age rule, assumed county timezone for a date-only publication, or inference
that absence proves payment. Execution time never replaces captured source times
or the source report's assessment/payable-year boundary.

## Reproduction evidence

`reproducibility.schema_version = 1` records canonical normalized parcel/record
SHA-256 fingerprints, byte hashes of all nine join exports, and sorted candidate
IDs. Canonical JSON uses sorted object keys, preserved record order, compact UTF-8,
Decimal text and ISO date/time text. Hashing is incremental per record and includes
nulls, source-row identities and captured source metadata.

An existing join supplies its threshold unless explicitly overridden. With the
same threshold, all nine exports must match the selected join's recorded hashes;
recorded normalized fingerprints must match when available. A difference fails
before completion/latest publication instead of silently claiming reproduction.
Readers reconcile source/date identities and actual export bytes/IDs, and check
normalized fingerprint format. Fingerprints are producer evidence, not signatures
or independent re-normalization by every reader.

`selection.comparison` distinguishes unchanged reproduction, a raw pair with no
historical output baseline, and deliberate `--min-acres` changes. Changed thresholds
still check recorded normalization, but do not assert identical old/new exports.
Older **complete version-2** joins lacking normalized fingerprints can be compared
against their export hashes; historical normalized content remains explicitly
unknown, never backfilled. `replayed_from` records the selected join ID, completion
hash and previous threshold.

The same inputs/parameters under compatible code yield the same canonical content,
candidate IDs and nine export bytes. New UUIDs, execution timestamps, output/pinned
paths, quarantine diagnostic locations, code/runtime provenance and comparison
metadata are declared run-metadata differences. Historical software is not restored
automatically; behavior changes can legitimately cause a failed comparison.

## Portable graph and legacy boundary

Copy the **entire completed join directory**, including `inputs/`, without changing
its directory name/run ID or contents. Replay follows contained completion references,
not inert historical absolute provenance paths, original raw directories, or latest
pointers. Moving that directory therefore does not require its former roots.
This is portability, not an off-device backup/restore service (ML-128).
Moving between folders on the same platform is verified. Cross-operating-system
replay is not claimed: historical provenance path syntax and export newline
representations can differ, and must not be silently accepted as identical bytes.

New results use the existing immutable completion protocol. Failures retain bounded
diagnostics where possible and cannot replace prior success/latest. A successful
replay may become the latest **processing result**; its old source data has not
become current. Raw source directories/pointers remain untouched.

Historical **pre-version-2** inputs remain legacy/unverified and are rejected with
a clear completion-record error. There is no force flag or silent downgrade.
The existing explicit read-only parcel inspection helper checks available evidence
and discloses missing checks, without adding completion markers or county inventories.
The project's original October results remain historical, not newly certified replay
inputs. A usable new-protocol recovery/reacquisition path for those inputs requires
separate review; no conversion or live refresh occurred in this story.

## Verification

[S01-S07 fixtures](../tests/unit/test_snapshot_replay.py) cover explicit selection
despite a newer empty acquisition; identical bytes/fingerprints under a later clock;
moved joins with former roots unavailable; no raw writes/latest lookup/acquisition;
CSV/XLSX and captured limits; mixed-year rows, unknown balances and holds; thresholds;
resealed incompatible source/query/county/date evidence; failed/corrupt/legacy inputs;
drift rejection preserving prior success; nested-output protection; older complete
runs with unknown fingerprints; CLI paths and invalid thresholds.
See [testing](testing.md) for the actual local/hosted verification outcome.

Implementation `7a53fdbec6a902e770e926b4cbe9447533d69b38` passed all 645 offline
tests without skips on each Windows/Linux x Python 3.11/3.12 job in
[run 38955519528](https://github.com/huschked/minnesota-land-intelligence/actions/runs/38955519528).
No government test executed. The real county files still have no eligible complete
version-2 run; this feature verification used synthetic inputs and did not migrate
or replay those original datasets.
