# Isanti actual viewer-data preparation (ML-130)

Work date: 2026-10-16 (America/Chicago). **Actual source preparation complete.**
All five new run kinds validate, including the review's full pinned source graph.
This prepares saved data for ML-202/206; it does not implement the UI.

## Inventory and agreed route

Read-only inventory before new county requests or production reimports found
no eligible version-2 parcel, delinquency or review run. Two historical parcel
manifests and five historical file/join manifests lack the required completion
protocol. Historical responses cannot supply missing before/after inventories,
attempt evidence or completion records retroactively.

All five retained `source.csv` copies and the original user download are 608,656
bytes and share SHA-256
`2d7060d273872ae6f087542e5b778dc395103359b59e25a6ca2349cb2fdc030b`.
Use the retained source under
`data/raw/isanti/delinquency/2026-10-14T170022005639Z/source.csv`, not an edited
spreadsheet or reconstructed export. That legacy import records 1,783 rows and
capture time `2026-10-14T17:00:22.005639+00:00`.

The reviewed mapping is
[`isanti-delinquency-2026-10-13.mapping.json`](../counties/isanti-delinquency-2026-10-13.mapping.json),
SHA-256 `76a4b36895ba90ad33150688c9e7884bd785bbc5f2466fbc822d9ffc4431e59e`.
Its [county year evidence](../counties/isanti-tax-year-confirmation.md) has SHA-256
`bb5bf49915760757f0a0940579c69af44382abd437e4c2dafe867eef3b9f45b7`.
The last retained complete-looking legacy GIS manifest was captured
`2026-10-14T14:26:55.494922+00:00`, with 23,890 rows and 12 pages; it is not
technically eligible. Partial acquisition directories remain untouched too.

A private before-inventory records all 108 historical raw files, 80 processed
files and the two reviewed documentation inputs: 190 files, 68,200,177 bytes.
It lives outside completed runs at
`data/processed/isanti/preparation/ml-130-2026-10-16/historical-before.json`.
Raw county data, correspondence and this private per-file inventory are ignored,
not repository attachments or GitHub backups.

Before production work the user explicitly selected: **fresh official GIS plus
October 13 CSV**. Execute the current paced/bounded acquisition against Isanti's
configured `TaxParcels_Public/FeatureServer/0`, then capture the unchanged CSV,
mapping and supporting year evidence into new immutable runs. Pin the new raw GIS
explicitly for the join, then create a new review and validate its full graph.
Do not backfill old manifests, reuse historical review totals as assertions,
contact the county, download verification PDFs or add a viewer-triggered refresh.

## Date and financial limits

The CSV publication/listing date stays October 13, 2026; original `EFFDATE` and
`LTRDT` values were October 7, whose accounting meaning remains unverified.
A new file capture date is not a new tax statement. County-confirmed assessment
year plus one determines payable year; money-column definitions and repeated-row
accounting remain unresolved. Canonical delinquent balances must stay unknown,
not zero or a sum of raw rows. New GIS facts may differ from historical examples;
disappearance is not evidence of payment or availability for purchase.

## Execution and handoff

The unmodified current pipeline ran at revision
`f49e59faf110b75b4d4f579cde2c6e09c56a56c4` on Windows / Python 3.12.14.
Provenance honestly records a dirty worktree because the preparation notes and
board were edited before execution. Runtime source files were unchanged; their
recorded aggregate SHA-256 is
`fefbf98984a13a140816be9db9efd923c38ba94ef36fd8c8965b392c26b2e0c1`.

The official GIS capture started `2026-10-16T23:07:15.997522+00:00`
(18:07:15 Central). It retained 18 HTTP attempts, 12 ordered pages and matching
initial/final counts of 23,890, ID inventories and schema fingerprints. Pacing
was one second with the existing timeout/retry/body/inventory budgets unchanged.
There was no usable edit token: checks reconcile observed membership/schema,
not a guaranteed transactional snapshot. Geometry was not requested.

File recapture time is `2026-10-16T23:07:50.330914+00:00`, 34.333392 seconds
after the GIS capture timestamp. The listing publication date remains
`2026-10-13`, three calendar days before GIS capture. The new raw manifest's
`source_original_name` is `source.csv`, the retained input filename; original
delivery identity is preserved by the unchanged dataset mapping, historical
manifest and exact SHA-256, not a renamed or rewritten source.

All paths below are relative to the configured project data root, which remains
local and ignored. The review pins the join; the join pins exact raw GIS and file
inputs, including supporting year evidence.

| Kind | Exact project-relative run path |
|---|---|
| Raw GIS | `data/raw/isanti/7ba028b0a51b4e64a04402f0635d272f` |
| Processed GIS | `data/processed/isanti/parcels/7cabbd0d8e9a45ab86be92879c6b7d88` |
| Raw file | `data/raw/isanti/delinquency/76737e18c80745d69c15c0368273cbc0` |
| Join | `data/processed/isanti/delinquency/ce541e7ad88e4a52826a90c9ff5a2139` |
| Review | `data/processed/isanti/review/4e2ebe46423d4f56aab999d7d9eb3a37` |

Join completion SHA-256:
`0a356f40f9fac841acef8552790b0451d8004fe2014bcb88e4df8b57b0f8bed0`.
Review completion SHA-256:
`eff2a5e9f9e0eb1b436de2c006a3bfe71c886af92537d01e2e191adb6ba4c5b3`.
The private after-evidence records all five completion hashes, output counts and
selection dates at
`data/processed/isanti/preparation/ml-130-2026-10-16/validation-after.json`.

### Actual counts and unresolved records

| Control | Actual new result |
|---|---:|
| GIS retrieved / normalized / quarantined | 23,890 / 23,888 / 2 |
| Listing rows: prior / overdue current | 523 / 1,260 |
| Listing rows total | 1,783 |
| Unique normalized matched parcel IDs | 866 |
| Matched prior-year IDs, all acreages | 203 |
| Large prior-year parcels (at least 10 acres) | 62 |
| Outside PILT/exempt | 49 |
| Focused rural-vacant or zero-improvement view | 15 |
| PILT/exempt review | 13 |
| Large overdue-current-year view | 291 |
| Unmatched source rows / distinct IDs | 8 / 5 |
| Duplicate listing groups / duplicate-review rows | 420 / 1,332 |
| Ambiguous / unverified large exports | 0 / 0 |

Two GIS features have missing parcel IDs and remain quarantined, not repaired.
Matched versus unmatched source-row accounting is 1,775 + 8 = 1,783; the 866
unique matched IDs must not be mistaken for a source-row count. Duplicate-review
rows overlap source-row accounting and are not an additive population.

The 49 non-special parcels comprise 8 rural-vacant, 7 other zero-improvement,
32 positive-improvement and 2 unknown-improvement parcels. The 15-parcel focused
view is a screening definition, not verified buildability or a buy recommendation.
All 62 candidates have null canonical delinquent tax, penalty and combined balance
amounts. No balance aggregation or financial-analysis readiness is claimed.
The GIS-only strict candidate export remains correctly empty because GIS tax
semantics are unverified; the separate authoritative file establishes listing
status. There is no active source/year verification hold, but accounting and
unmatched-account questions (ML-117/121/122) remain unresolved.

### Historical comparison and verification boundary

A one-off read-only control compared actual parcel-ID sets against the corrected
October 14 outputs. Prior-year 62, current-year 291, all-review 62, land 49,
focused 15 and PILT/exempt 13 have identical IDs: zero additions/removals in each.
Counts were computed from new outputs, never imposed as acceptance constants.
This is not ML-124's general refresh-difference feature and does not establish
that every property field or outstanding balance stayed unchanged.

The new review deliberately did **not** reuse October 14 PDF comparison evidence
as a fresh verification. It records manual verification `pending`, no official
sample comparison, and ten worklist records. Every candidate is labeled
`listed_prior_year_unpaid_unsampled`. Historical sample findings remain in their
original files. Tax-status screening is ready for the dated listing; monetary
analysis is not ready. The summary's zero `delinquency_status_changes` is a
no-overrides control, not proof of no payments since October 13.

An explicit **offline** replay of the new join at unchanged acreage produced
`identical_exports_and_recorded_normalization`: both normalized fingerprints,
all nine export hashes and candidate IDs matched. The replay was isolated under
`data/processed/isanti/preparation/ml-130-2026-10-16/replay/isanti/delinquency/f04a7c3e60014ab784cf7f46b64b7a65`,
so default join/review selection still points to the handoff above. No second
county acquisition or PDF requests were needed.

The shared validator passed all five actual run kinds and the isolated replay,
including contained source graphs, hashes, counts and date/selection evidence.
The before/after check found **all 190 historical files unchanged**, including
legacy manifests, CSV copies, prior review/PDF/correspondence and reviewed year
evidence. No completion record was installed into a historical run.

### Use in ML-202 and ML-206

Use explicit join `ce541e7ad88e4a52826a90c9ff5a2139` and review
`4e2ebe46423d4f56aab999d7d9eb3a37`; validate on each load rather than trusting
the IDs or this document. `mn-land status --county isanti` now reports COMPLETE
for all five kinds while historical entries remain ineligible. The review's
seven CSVs include all/land/focused/PILT views, duplicates, unmatched IDs and the
county-verification worklist. Preserve the old listing date, fresh GIS/capture
dates, null amounts and pending verification in the future viewer.

This handoff removes ML-130's actual-data prerequisite, not ML-202/206's UI,
accessibility or packaging acceptance checks. No Streamlit installation, map,
scoring, accounts, deployment, county email or dataset upload occurred. Git tracks
only the three data `.gitkeep` placeholders; local datasets and private audit
files need a separate backup and will not appear in a fresh GitHub clone.
