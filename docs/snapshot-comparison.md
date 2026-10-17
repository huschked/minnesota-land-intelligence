# Saved snapshot comparisons (ML-124)

`compare-snapshots` compares two explicitly selected completed Isanti joins. It
does not retrieve GIS, refresh tax balances, replay/reimport data, select latest
inputs, infer seller circumstances, or change either historical result. This is
a CLI report, not a viewer refresh button or scheduled job.

```powershell
.\.venv\Scripts\python.exe -m mn_land.cli compare-snapshots --county isanti --before data/processed/isanti/delinquency/BEFORE_RUN_ID --after data/processed/isanti/delinquency/AFTER_RUN_ID --as-of 2026-10-17 --stale-after-days 30
```

Pass directories, not manifest files. `--as-of` is required: it is an operator
UTC calendar date, never an implicit machine clock. `--stale-after-days` defaults
to 30, accepts integers 0–36500, and is a screening policy, not a county assertion
about validity or payment. Age equal to the threshold is within policy; greater
age is stale. Missing dates are unknown and future dates are separately flagged.
Listing publication, listing capture and GIS capture each have their own age.
Recapturing the same CSV does not make its publication or tax status newer.

`--output-root` optionally selects a processed-data root. New reports go beneath
`<root>/isanti/comparisons/<UUID>` (default `data/processed`). Outputs inside
reserved/completed inputs are rejected. Prior results and latest pointers survive
a failed report. A successful comparison updates only the comparison latest pointer.

## Meaning and scope

`changes.json` includes the union of normalized listing parcel IDs, including
below-acreage-threshold, held, unmatched and ambiguous records. IDs remain strings
with leading zeros. Each record has `added`, `missing`, `changed` or `unchanged`
status and separate before/after observations:

- Listing presence and canonical source rows, including original raw values and
  retained row/sheet locations. Reordering source rows alone is not a change;
  repeated rows retain their multiplicity. Monetary rows are never summed.
- Normalized non-geometry GIS observations, dated join statuses and membership
  in the separate prior-year/current-year large-parcel views. View counts can overlap.
- Changed field names, `current_payment_status: unknown` and
  `identity_relationship: not_inferred`.

Missing means **not observed in that listing**, never paid, cleared or available
for purchase. GIS observations may still exist for a missing listing ID. A held
source can remove candidate membership without removing the listing observation;
the previous dated status is retained alongside the later unverified status.
Report-year rollover uses the recorded assessment/payable mapping, not today's
year. Former current-year charges can become prior-year observations without any
inference of payment. Unknown canonical money remains null, not zero.

`manifest.json` retains both source dates, run IDs/completion hashes, agency and
dataset, source/mapping hashes, year conventions, report payable-year populations,
holds, thresholds, counts, quarantine counts, freshness policy, warnings and
limitations. Separate full normalized GIS ID additions/disappearances do not
establish parent/child splits, mergers, retired IDs or replacement relationships.
Input order is explicit; backward source dates warn rather than silently swap it.

## Compatibility, preservation and validation

Both joins must pass version-2 completion validation and carry normalized input
fingerprints that reproduce with current normalization code. Pre-completion legacy
inputs and older complete joins without these fingerprints are rejected; no
historical certification is added. Matching semantic profiles are required:
GIS service/layer/full-county query/fields, source agency/URL, column mappings,
delinquency assertion, year convention and numeric acreage threshold. Dataset
names, publication dates, evidence bytes and holds may differ and are disclosed.
Matching metadata is not independent proof of authoritative origin; use reviewed
county mappings and sources. Synthetic fixture provenance is labeled explicitly.

The new `comparison` completion kind pins both complete join graphs with their raw
sources. Copy the whole report directory, preserving its UUID/name and contents,
for same-platform portability without original input roots. Historical absolute
provenance paths are inert, not replacement inputs. Cross-OS portability and
off-device backup are not claimed. Content validation reproduces the difference
from pinned evidence and policy, rejecting resealed payment claims or omitted
warnings as well as ordinary hash/inventory corruption.

No source URLs are followed. Comparison files contain retained property/source
rows and should be treated as private local research artifacts. This card adds
no browser exposure, new financial calculations, GIS boundary analysis or exports.

## Verification

[Offline fixtures](../tests/unit/test_snapshot_diff.py) exercise rollover,
mixed-year rows, disappearance with retained GIS, apparent parent/child IDs,
holds, stale/future/unknown dates and policy boundaries, row order/multiplicity,
unknown money, below-threshold/unmatched/duplicate GIS IDs, incompatible profiles,
backward dates, corrupt/legacy inputs, failed publication, immutable inputs,
moved-folder validation, resealed payment claims and CLI behavior. Network,
latest selection, replay and reimport are explicitly prohibited in report tests.
See [testing evidence](testing.md) for measured verification and the actual-data
control; the control is not a second independent tax observation.
