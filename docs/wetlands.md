# Mapped wetland overlap — ML-303

Implemented 2026-10-19 as a separate CLI observation, not a viewer feature.
The output estimates **mapped** wetland acreage/percent against measured parcel
polygons. It does not identify all jurisdictional wetlands, dry/buildable land,
usable acres, flood risk, acquisition value or a verified tax balance.

## Run deliberately, validate offline

Use the existing optional `gis` extra (Shapely 2.1.2 / pyproj 3.7.2). No additional
Python dependency is introduced. The bundled 9,324-byte public-domain NOAA grid
is a computational reference, not a published county dataset.

```powershell
.\.venv\Scripts\python.exe -m mn_land.cli analyze-wetlands --county isanti --geometry-snapshot data/processed/isanti/geometry/EXPLICIT_COMPLETED_GEOMETRY_ID
.\.venv\Scripts\python.exe -m mn_land.cli validate-wetlands --snapshot data/processed/isanti/wetlands/EXPLICIT_WETLAND_ID
```

Replace placeholders explicitly; no latest-pointer selection. The input must be
a completed ML-302 `parcel_geometry` graph with 1–50 distinct validated parcels.
Default output is `data/processed/isanti/wetlands/<new-UUID>/`; `--output-root`
must be outside retained source/run evidence. Original tax, GIS, review and
geometry runs are pinned into the new graph, never changed. Only the new output
root's publication pointer changes. No viewer restart or UI integration occurs.

## Source and bounded capture

The [ML-301 source contract](suitability-sources.md) selects Minnesota DNR's
[Statewide NWI layer 0](https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_dnr/water_nat_wetlands_inv_2009_2014/FeatureServer/0)
and independent [Project Boundary layer 1](https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_dnr/water_nat_wetlands_inv_2009_2014/FeatureServer/1).
No county/federal substitution or state/federal union occurs. A national/catalog
modification date does not establish fresher Isanti imagery; this work did not
establish a newer Isanti-specific federal inventory.

Inverse-aligned native EPSG:26915 parcel envelopes are expanded by 2 metres for
query completeness, grouped at most four per request. The margin is **not** a
coverage buffer or a boundary repair. Initial/final layer declarations, capabilities,
edit tokens, spatial counts and exact OID memberships must reconcile. Overlapping
query groups union OIDs; ordered batches of at most ten retrieve each OID once.
Each batch must return exactly its requested features and source fields.

Native UTM polygons request true curves and Z/M explicitly so unsupported content
is refused, not silently converted. No server reprojection, quantization,
simplification or coordinate rounding is requested. Original wire bodies,
attempt/receipt times, URL/parameters, hashes and parsed responses are retained.
An injected test transport is labelled as lacking original wire bytes. Public
requests remain non-atomic; absence of an edit token remains an explicit unknown.

Budgets are 128 logical requests, 20,000 IDs, 30-second timeout, three attempts,
at least one-second request spacing, 60-second single/600-second total waits,
64 MiB per response and 512 MiB aggregate capture files (wire plus parsed copies).
An oversized batch splits by exact OIDs; a single oversized feature fails closed.
The first live 16 MiB attempt exposed a connected river polygon extending far
beyond the parcel AOIs. That failed run remains failed; the separately dated
retry uses the explicit bounded 64 MiB policy, not unlimited downloading.

## Explicit datum alignment, not relabeling

Isanti's adjusted county datum is not ordinary NAD83 UTM. Automatic PROJ and
the county's official transformation lookup provided no usable cross-datum
operation. An empty operation list was not treated as a zero shift.

The county adapter implements `mndot-isanti-1996-epsg1706-v1`: DNR NAD83 UTM
to NAD83 geographic angles; explicit Minnesota NADCON HPGN/HARN grid shift
(EPSG:1706); then the MnDOT county-adjusted geographic convention and the
existing ML-302 same-adjusted-datum local equal-area projection. Query windows
use the exact inverse chain. No ballpark, null-grid, automatic alternate or
network grid fallback is allowed. Full definitions, pipelines, versions/database
hash and actual grid hash are recorded, with the reference files copied into
each completed run.

[MnDOT's county projection guidance](https://www.dot.state.mn.us/surveying/toolstech/mapproj.html)
and historical paired coordinates on [GSID 12519](https://www.olmweb.dot.state.mn.us/Geod/PDF%20Single%20Sheet/GSID_12519.pdf)
and [GSID 12549](https://www.olmweb.dot.state.mn.us/Geod/PDF%20Single%20Sheet/GSID_12549.pdf)
support the explicit bridge. The paired tables were visually checked in the
actual source PDFs, not inferred from approximate map-service coordinates.
County projection residuals are approximately 0.000125/0.000216 m; independently
checked grid residuals are 0.103683/0.072810 m. Both controls must pass 0.001 m
projection and 0.25 m grid engineering gates. The grid operation's stated 0.05 m
accuracy is **not** claimed to contain those observed residuals. Neither these
gates nor the historical monument sheets establish parcel-specific accuracy or
current physical survey control. This is an explicit legacy regional operation,
not an assertion that it is the newest/best-ranked operation.

Grid SHA-256 is
`e6b5da45fea4fa0f050a5656e34379e81c5175e90bf535b8a8498dbdb1e4554c`.
The [publisher's NOAA notice](https://cdn.proj.org/us_noaa_README.txt) identifies
the grid as public domain. Controls and their PDF hashes are pinned separately.
Changed/missing resources or out-of-grid coordinates hold processing.

## Deterministic area and inclusion

`dnr-wetland-dissolve-clip-v1` validates the original Esri polygon without repairs,
including shells/holes and topology. Connected source features can be much larger
than the selected parcels: original validation has a one-million-vertex/10,000-ring
limit. Only an analysis copy is locally clipped to the native query windows,
densified at 10 m and transformed. Local densification is bounded at 200,000
vertices per feature and one million per layer. The 20 m comparison must converge
within max(0.01 m², one part per million); inverse roundtrip must be within 1 mm.
These are numerical checks, not source positional-accuracy promises.

`dnr-nwi-cowardin-screen-v2` requires a recognized complete Cowardin-code syntax
and consistent source `wetland_type`, not a guessed label or partial prefix.
It adds DNR's verified detailed forested, shrub and shrub/emergent label/code
pairs. The initial v1 policy remains replayable with its original held results;
saved observations are not rewritten to apply a newer interpretation.

| Category | Treatment |
|---|---|
| Vegetated/other wetland | Recognized palustrine forest/shrub/emergent and selected littoral classes; included. |
| Open-water wetland | Recognized palustrine pond and littoral aquatic/unconsolidated-bottom classes; included, separately visible. |
| Deepwater | Recognized limnetic lake classes; separate, not included in wetland numerator. |
| Riverine mixed | Riverine can include wetlands and deepwater; separate, not silently counted as all wetland. |
| Unknown/inconsistent | Unsupported, missing or contradictory codes/labels; positive parcel overlap holds overall metrics. |

Within each category, union/dissolve precedes parcel clipping: duplicate and
overlapping features are counted once. Positive-area overlap between different
categories is an explicit conflict and holds overall metrics rather than choosing
a class. Boundary-only contact has zero area. Parcel holes/multipart shapes are
preserved. Denominator is measured equal-area parcel area, not deeded acres;
international acres use exactly 4046.8564224 m². Source/deeded discrepancies remain
separate. Only displayed percent is rounded (eight decimals), not geometry.

## Coverage and dates govern interpretation

Coverage is checked against the **independent dissolved project footprints**.
Complete requires no uncovered geometry; no gap filling or tolerance buffer is
used. Zero NWI features alone is not coverage evidence. Missing/partial coverage,
positive unknown classification or cross-category conflict gives `status=held`
and null overall acreage/percent, never an invented zero. Observed category
fragments remain available but explicitly are not complete totals on a held row.

Every positive-area parcel/project intersection retains its footprint, project
ID/partner, raw and normalized imagery years and delivery date. Multiple contexts
are retained; no single latest imagery date is chosen. Missing/invalid/future
dates remain unknown with raw values preserved. New retrieval, old parcel
capture, imagery, project delivery and original tax-list dates stay independent.

See DNR's [inventory FAQ](https://www.dnr.state.mn.us/wetlands/nwi_faq.html)
and the source contract for mapping/seasonality/scale limitations and differing
published positional assessments. Numeric processing precision does not improve
inventory accuracy or constitute a jurisdictional delineation. DNR attribution
and source notices apply; this implementation provides no raw-data resale,
sublicensing, public hosting or redistribution clearance.

## Saved evidence and verification

A `wetland_analysis` completion pins `parcels -> parcel_geometry -> review ->
join -> raw inputs`. It contains selection/geometry hashes, `capture/`, `reference/`,
`source_features.json`, `wetlands.json`, manifest and row counts. An observation
run may complete with held parcel rows; an incomplete acquisition or invalid
geometry cannot publish a completion. Offline validation replays the exact
request sequence, reconciles raw bytes, policy/source checks and references,
then reproduces geometries, categories, dates, areas and row counts. Hash-only
edits to a derived area cannot bypass semantic reproduction.

See [dated verification](testing.md#ml-303-mapped-wetland-overlap) for actual
run results, preservation, platform coverage and the explicit Windows exception.
ML-304 subsequently implements the [effective flood screen](floods.md), and ML-305
the separate [mapped-water/SFHA union and remainder](constraints.md). These do not
rewrite wetland results or reinterpret deepwater/riverine as all wetlands.
ML-306 official-map review/publication/integration remains Ready, not started.
