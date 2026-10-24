# Effective mapped flood overlap — ML-304

The separate flood CLI screens saved parcels against FEMA's effective National
Flood Hazard Layer (NFHL). It retains mapped categories, independent coverage,
panel/revision/study dates and unknowns. It does **not** decide insurance,
regulatory status, legal buildability, actual flood risk, acquisition suitability,
usable acres or the current tax balance. The local viewer is unchanged.

## Explicit saved input and new observation

Use the existing optional `gis` extra: Shapely 2.1.2 and pyproj 3.7.2. No new
Python dependency or grid download is required. Select a completed ML-302
`parcel_geometry` graph, not a latest pointer or old attribute-only GIS run.

```powershell
.\.venv\Scripts\python.exe -m mn_land.cli analyze-floods --county isanti --geometry-snapshot data/processed/isanti/geometry/EXPLICIT_GEOMETRY_ID
.\.venv\Scripts\python.exe -m mn_land.cli validate-floods --snapshot data/processed/isanti/floods/EXPLICIT_FLOOD_ID
```

Default output is `data/processed/isanti/floods/<new-UUID>/`. A dedicated
`--output-root` may be supplied outside retained runs/source evidence. Each run
pins the exact geometry and its complete review/tax/GIS graph plus selected
parcel/OID/geometry hashes. Only the new flood root's publication pointer changes;
no reader implicitly selects it. Repeat acquisition creates a separate dated
observation, never overwrites tax, geometry, wetland or prior flood results.

The initial scope is 1–15 distinct validated parcels, groups of at most four
native query windows, and at most 20 associated study IDs. Larger selections
refuse before network access rather than silently discard parcels.

## Authoritative effective source and retrieval

The [ML-301 contract](suitability-sources.md) selects only
[FEMA's public effective NFHL MapServer](https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer):

| Resource | Role |
|---|---|
| 28 Flood Hazard Zones | Exact `FLD_ZONE`, `ZONE_SUBTY`, `SFHA_TF`, study/source IDs and native polygons. |
| 0 NFHL Availability | Independent study availability footprint; never itself a hazard polygon. |
| 3 FIRM Panels | Spatial panel ID/type, raw effective/preliminary dates, scale and not-printed reasons. |
| 1 LOMRs | Spatial revision case/status/effective-date context; not extra hazard area or automatic LOMA relief. |
| 41 Study_Info | Exact associated study IDs, original datum/projection context, raw index/database dates. |

Initial/final service layer identities, source SR and notices are retained. Each
spatial layer reconciles initial/final metadata, AOI count and exact unique OID
inventory. Queries use native geometry AOIs and `where=1=1`, **not a county or
single-study filter**; adjacent-study/county features cannot be dropped by that
filter. Overlapping AOI groups union OIDs before ordered batches of at most ten.
Each batch must return exactly its requested IDs, geometry and fields.

Observed FEMA empty queries can return `objectIds: null`. This is never accepted
alone: an explicit zero count **and an independent empty feature-page
query** must corroborate it, initially and finally. Missing ID keys, nonzero
counts, any returned feature or truncation fail. Raw null responses are unchanged;
the DNR default remains strict. This only verifies an empty source query, not
parcel coverage or a zero hazard result.
The confirmation uses at most min(2,000, advertised record cap), requesting only
the OID. FEMA's spatial scan can produce a truncated empty page with a one-record
cap; the reviewed larger cap must actually return an untruncated empty page.
The truncation guard is not ignored or weakened.

The verified 15-parcel pilot has nine numeric results and six conservative
held/null rows. Neighboring not-printed panel rectangles trigger the initial
context rule even though study-matched Isanti coverage is complete; one held row
also retains a microscopic exact zone-union numerical residue. These are not
assertions of missing Isanti data or a physical unmapped gap. ML-306 records
explicit applicability/residual review before any new, less conservative policy.

The table is queried only for safe, explicitly collected source study IDs, with
its own start/end metadata/count/OID reconciliation, 100-row cap and exact field/
identity/order checks. Missing or multiple study rows are not silently resolved.
OIDs and source-specific IDs remain capture-local, not persistent owner/parcel IDs.

MapServer legitimately omits `objectIdField`, nullability and Z/M flags in the
observed metadata. The unique explicitly typed OID declaration supplies schema
identity; missing nullability/dimension declarations remain **unknown**, not
fabricated FeatureServer properties. Both Z/M and true curves are requested;
actual native coordinates must be exactly two-dimensional linear polygons.
Unsupported curves/dimensions, invalid topology, nulls, quantization, truncation,
identity/count/schema/edit drift or budget exhaustion refuse completion. See
[Esri's map-layer query contract](https://developers.arcgis.com/rest/services-reference/enterprise/query-map-service-layer/).

Native wire bytes, parsed responses, intended requests and actual receipt/retry
times/hashes are retained. The shared bounded transport has 30-second requests,
three attempts, >=1-second pacing, 60-second single/600-second total waits, 64 MiB
per body, 512 MiB aggregate capture files, 20,000 spatial IDs and 128 logical
requests. Oversized batches split by exact OIDs; an oversized single feature
holds the run. An injected offline transport explicitly lacks original wire bytes.
All public requests remain non-atomic; a missing edit token is unknown same-ID
edit consistency, not an atomic snapshot guarantee.

## Explicit geographic datum alignment and numerical checks

The observed FEMA service and all spatial layers declare **EPSG:4269 NAD83
geographic**, longitude/latitude in degrees. This is neither DNR's EPSG:26915
UTM input nor Isanti's adjusted county datum. `FloodAlignment` explicitly checks
that native definition against the reviewed NAD83 input of the pinned Minnesota
grid, applies the actual EPSG:1706 NOAA NADCON HPGN/HARN grid, then the audited
MnDOT county-adjusted geographic convention and ML-302 local equal-area CRS.
The DNR UTM stage is **not** used. No ordinary-NAD83 relabeling, automatic
ballpark/alternate, missing/null-grid or network fallback is allowed.

The existing [alignment reference and control limitations](wetlands.md#explicit-datum-alignment-not-relabeling)
still apply: historical MnDOT paired coordinates check the county bridge and
actual grid at approximately 0.073/0.104 m residuals under a 0.25 m engineering
gate; these are not source boundary accuracy or a survey guarantee. The operation's
stated 0.05 m accuracy is not claimed to contain those observed residuals. Full
native/analysis WKT, axis order, units, grid/control hashes, pipelines, library/
database versions and control residuals are recorded independently for FEMA.

Inverse-aligned parcel envelopes have a 0.00005-degree **query-only** margin;
that margin never fills a coverage gap. Originals are validated before an analysis
copy is locally clipped in native coordinates, densified at 0.0001 degree and
transformed. The coarser 0.0002-degree result must converge within max(0.01 m²,
one part per million). A geodesic inverse roundtrip checks matching vertices
within 1 mm. Area is calculated only in equal-area **metres**, with exactly
4046.8564224 m² per international acre; no square-degree/Web-Mercator acres.

Original thematic geometry is bounded at one million vertices/10,000 rings per
feature. Local analysis has 200,000 vertices per feature/one million per layer
and at most 64 distinct raw category tuples. These are processing limits, not
source-resolution promises. No repair, snapping, buffer(0), simplification or
coordinate rounding is supported. Measured area/deeded acres/discrepancies remain
distinct; percent alone is rounded to eight decimals for presentation.

## Categories, coverage and dates

`fema-effective-categories-v1` retains each exact zone/subtype/SFHA tuple, dissolves
within that tuple and clips against the parcel. Duplicates or same-category overlap
do not double-count. Different-category positive overlap is an explicit conflict,
not a priority rule that chooses a winning polygon. Boundary-only contact is zero.

Mapped SFHA requires a reviewed A/AE/AH/AO/A99/AR/V/VE zone, consistent `SFHA_TF=T`
and reviewed unspecified/floodway subtype. Floodway is a **subset** of SFHA, not
added again. X with `SFHA_TF=F` must distinguish the exact 0.2%-annual-chance and
minimal-hazard subtypes. Unsupported, missing or contradictory categories remain
unknown and hold overall metrics. Minimal hazard is not no flood risk.

Every parcel requires exact complete coverage from independent availability,
eligible effective panels and zone geometry, **matched by study ID**, not just
three unrelated unions. A panel requires a matching study/panel identifier,
reviewed printed panel type and a valid effective date no later than capture.
Not-printed, undated, future or inconsistent panel context remains held. Gaps
retain their geometry/area/status; they are not closed with a numerical buffer.
An empty hazard query is not proof of a genuine zero. Missing, partial, unknown
category, conflicting or unmatched-study evidence yields `status=held` and null
overall metrics. Observed category fragments remain labelled as incomplete.

All spatial panel/revision intersections and exact raw attributes remain visible,
including multiple contexts and repeated revision geometries. Distinct case
numbers are counted separately from polygon count. Revisions must have verified
effective status/date and case identity; otherwise affected parcels are held.
Their footprints are **never** unioned into hazard acreage. No preliminary or
pending service is substituted, no county flood fallback is used, and no LOMA
decision is inferred. The effective source asserts its own incorporated revisions;
these computations are not an independent regulatory audit of that incorporation.

Raw millisecond dates, decoded calendar dates and usable effective dates are
separate. Dates before 1900, malformed/null dates and future/placeholder values
never become today's date. The observed study index year 8888 is retained as
`future_or_placeholder`, with null usable date; null `DBREV_DT` remains unknown.
Independent valid panel dates can still support screening, with a warning that
the study index/database dates are unavailable. One date is never substituted
for another. Panel, revision, study/database, new retrieval, old parcel geometry
and tax-list dates stay independent. Panel scale is not parcel-specific accuracy.

The official FEMA guidance PDF was inaccessible during the implementation check;
no date meaning was inferred from a search snippet. This work preserves unusable
values without asserting a placeholder's undocumented legal/administrative meaning.
The [source contract's accuracy/use limits](suitability-sources.md) remain in force;
public endpoints and blank copyright fields are not redistribution/hosting clearance.

## Publication and reproduction

`flood_analysis` pins `parcels -> parcel_geometry -> review -> join -> raw` under
the existing four-edge graph budget. It contains selection, original capture,
copied reference resources, source features, study records, per-parcel flood
observations, manifest policies, source checks, dates and row counts. Complete
observation runs may contain held rows; an incomplete acquisition/invalid geometry
cannot publish a completion. Normal validation is offline: replay exact requests,
check original wire evidence and references, reproduce all coverage/context/
category geometry and area, and reconcile row counts. Rehashing a tampered derived
metric does not bypass semantic reproduction.

See [dated verification](testing.md#ml-304-effective-floodplain-overlap) for actual
results and platform limits. ML-305 subsequently implements the separate
[explicit mapped-water/SFHA union and remainder](constraints.md), preserving
this screen's six holds. ML-306 remains Ready for integration/official-map review;
neither later operation is an automatic side effect of this screen.
