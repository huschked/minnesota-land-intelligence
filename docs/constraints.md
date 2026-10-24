# Combined mapped constraints and preliminary remaining acres — ML-305

This offline CLI combines deliberately selected completed wetland and effective
flood observations. It estimates land remaining **under an explicit mapped-
constraint policy**, not verified upland, actual usable land or legally buildable
acres. It adds no source retrieval, tax refresh, UI, score or legal determination.

## Formula and versioned inclusion

`mapped-water-sfha-union-remainder-v1` operates in the shared, audited local
equal-area CRS, in square metres. International acres divide by exactly
4046.8564224. Measured polygon area is the denominator; deeded acres and their
discrepancy remain separate source observations, never the subtraction base.

- Water mask: union the DNR vegetated/other wetland, open-water wetland,
  **deepwater and riverine mixed** category geometries.
- Flood mask: effective FEMA **SFHA**, which already contains mapped floodway.
- Constraint: parcel intersect union(water mask, SFHA).
- Estimated usable remainder: parcel difference constraint.

Deepwater and riverine are deliberately included as separate mapped water
constraints: counting them as remaining land would be misleading. They are **not
reclassified as wetlands**, and ML-303's original narrower wetland numerator is
unchanged. This is a conservative research policy, not a regulatory exclusion rule.
The broader water mask, individual categories and shared water/SFHA overlap are
visible in the calculation. Overlapping polygons, subsets and floodway are never
added twice. Boundary-only contact subtracts zero area; holes/multipart remain.

FEMA 0.2%-annual-chance and minimal-hazard zones are not subtracted by this policy.
They remain independently visible in the pinned flood observation. Minimal hazard
does not mean no risk. Availability, panels, study and revision footprints provide
coverage/date context only, not extra hazard area. Unknown classification is not
an excluded favorable category: any upstream hold makes the combined total null.

## Explicit inputs, coverage and dates

Both observations must validate and reproduce from original retained capture.
They must pin the identical completed parcel-geometry run/completion hash, ordered
parcel/OID/analysis-WKB hashes, full equal-area CRS/runtime evidence, grid and
control hashes. No approximate CRS/area matching, parcel-ID-only join, inferred
replacement parcel, implicit subset or latest-pointer selection is allowed.
Selections are bounded at 1–15 distinct parcels, matching the current flood scope.

Every source hold propagates, even if geometric coverage is complete. The output
retains individual wetland-project and four independent FEMA coverage-gap
geometries/areas, their dissolved union and independently covered area. Repeated
coverage gaps are not added twice. A zero evidence gap **does not** override panel,
date, classification, conflict or other source holds. Observed fragments on held
source rows cannot become a numeric combined constraint or remaining-acre value.
No numeric usable estimate is issued for ML-304's six held pilot parcels.

Source capture/as-of times, algorithms and inclusion policies are independently
pinned in the manifest. Original parcel capture, listing date, DNR spatial imagery/
delivery and FEMA spatial panel/revision/study dates remain in the contained source
graph, with raw invalid dates/nulls unchanged. Processing today does not mean
current source conditions: pilot DNR imagery is 2010, delivery 2013; eligible Isanti
FEMA panels are dated 2003-11-05, separately from 2026 retrieval. Applicability
and numerical-residual review remains ML-306; no source policy was loosened here.

## Numerical controls

Union and remainder areas must each be in [0, measured parcel area]. The geometry
partition and inclusion-exclusion residuals are retained and must be within
max(0.01 m², parcel m² × 1e-6). Failure holds the combined metrics; values are not
clamped. This is a processing check, not a source-accuracy guarantee.

GEOS may reorder rings and change floating-point area summation for a full parcel.
Only **exact topological equality** permits reusing the original parcel geometry;
subtracting empty geometry is identity. No area/distance tolerance establishes
that equality. This does not erase gaps or repair source shapes. No buffer, snap,
simplification or geometry rounding is applied; tiny nonempty coverage gaps still
hold, regardless of the area reconciliation tolerance. Only display percent is
rounded to eight decimals; geometry/acreage is not rounded for calculations.

## Run and reproduce without a network

Use the existing optional `gis` extra; no additional dependency is introduced.

```powershell
.\.venv\Scripts\python.exe -m mn_land.cli analyze-constraints --county isanti --wetland-snapshot data/processed/isanti/wetlands/EXPLICIT_WETLAND_ID --flood-snapshot data/processed/isanti/floods/EXPLICIT_FLOOD_ID
.\.venv\Scripts\python.exe -m mn_land.cli validate-constraints --snapshot data/processed/isanti/constraints/EXPLICIT_CONSTRAINT_ID
```

Default output is a new `data/processed/isanti/constraints/<UUID>/`; a dedicated
`--output-root` must not overlap retained source evidence. Both full source graphs
are copied byte-for-byte into contained `inputs/wetlands/` and `inputs/floods/`.
This intentionally duplicates their common ancestry for portability. Only the new
constraint root's publication pointer changes; no reader automatically selects it.
Old sources, tax exports and the viewer are untouched. Runs can complete with held
rows; incompatible/malformed source runs cannot publish.

`constraints.json` holds measured/deeded distinctions, source-row fingerprints,
coverage diagnostics, category components, shared area, union/remainder WKB,
m²/acres/percent, hold reasons and numerical residuals. Held combined metrics
are null. `manifest.json` records policy, source graph identities, independent
dates, runtime/CRS evidence, processing times, zero network requests and summary.
Offline validation reproduces both upstream observations and the combined results.
Rehashing a changed metric, policy, source date or summary cannot bypass semantic
reproduction. Completion is integrity evidence, not a digital authority signature.

DNR/FEMA source attribution and notices remain in pinned captures. Nothing here
grants source-data resale/public hosting clearance. ML-306 separately implements
[official-map comparison, enrichment exports and optional review UI integration](suitability.md).

## Verified saved-data pilot — 2026-10-24

Run `2cac708e0d2044a4be3b28d381197467` deliberately combines completed wetland
`cc72a8e3c282433696c19203f21b75ea` and flood `a4618c9a288e4742b60a96537231cf60`
against geometry `3804ff3662ac4e63939defa218c09df3`. Nine rows have numeric
preliminary remaining-acre estimates; the same six flood-held rows stay null.
Eight numeric parcels have shared water/SFHA area counted only once. Independent
offline reproduction and hash audit verify all 4,617 baseline files unchanged.
See [dated test/platform evidence](testing.md#ml-305-combined-mapped-constraints).
The private per-parcel report is
`data/processed/isanti/preparation/ml-305-2026-10-24/shortlist-results.md`.
