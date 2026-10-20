# Parcel polygon foundation — ML-302

Implemented 2026-10-18. This is a separate CLI acquisition/analysis path, not a
viewer feature, thematic overlay, remaining/usable acreage or legal opinion.
Saved candidate/tax runs and the attribute-only ArcGIS client remain unchanged.

Successor [ML-303](wetlands.md) now adds a separate mapped wetland observation
using this explicit completed geometry. Its audited cross-datum operation does
not alter the ML-302 same-datum contract or automatically approve FEMA alignment.

## Explicit operation and installation

The optional `gis` extra pins Shapely 2.1.2 and pyproj 3.7.2. Shapely/GEOS checks
polygon topology; pyproj/PROJ resolves CRS definitions and performs deterministic
coordinate/ellipsoidal calculations. Base CLI/viewer imports do not require them.
Full CI installs `.[dev,ui,gis]`; a base-only install skips GIS-specific tests,
which is not a full geometry verification claim.

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,ui,gis]" -c constraints-dev.txt
.\.venv\Scripts\python.exe -m mn_land.cli acquire-geometry --county isanti --snapshot data/processed/isanti/review/EXPLICIT_COMPLETED_REVIEW_ID --view focused
.\.venv\Scripts\python.exe -m mn_land.cli validate-geometry --snapshot data/processed/isanti/geometry/EXPLICIT_GEOMETRY_ID
```

Replace placeholders deliberately. No implicit/latest review selection. Supported
views are the existing `focused`, `outside_special`, `prior`, `special`, `current`,
`either` and `both` definitions. Only completed version-2 **review** graphs are
accepted; join-only input must first receive an explicit review. Active county
holds and empty/ambiguous selections refuse before network access. Source IDs,
the original review completion hash and all contained inputs are pinned and
revalidated. Canonical digit-only identity must be exact nine-character text.

Default output is `data/processed/isanti/geometry/<new-UUID>/`; `--output-root`
selects a dedicated geometry root. A successful publication updates only that
root's pointer, never tax/attribute/review pointers. No reader auto-selects that
pointer. Re-running creates a new run; it cannot replace an old result.

## Acquisition and native fidelity

[Official Isanti layer](https://gis.co.isanti.mn.us/arcgis/rest/services/LandRecords/TaxParcels_Public/FeatureServer/0)
is allowlisted in the county module. Requests are limited to `OBJECTID`,
`PARCELID`, `UNFORMATTEDPIN`, `DEEDEDACRES` and geometry. Every request retains
URL, exact parameters, UTC start/end, retry range, parsed response and original
HTTP bytes/hash (including failed attempts). Injected offline transports explicitly
disclose that wire bytes are unavailable; they are not live-source evidence.

Start/end metadata, count and exact unique OID inventories must reconcile. Each
sorted OID batch must return exactly its requested membership and unique selected
PINs, with formatted/unformatted identity agreement. OIDs are capture-local, not
assumed stable since the saved GIS date. Transfer truncation, unexpected rows,
missing geometry/fields, capability/CRS/schema/edit-token drift fail closed.
An absent edit token is an explicit same-ID consistency unknown. Public service
requests are non-atomic even with an unchanged token; this is not a transactional
or independently signed snapshot.

[Esri's query contract](https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/)
requires explicit `returnTrueCurves=true` to avoid default curve densification.
We require that capability, ask for native `outSR=103736` and both Z/M dimensions,
and request no quantization, simplification, precision rounding or offset.
Layer Z/M dimensions are currently held before polygon queries; returned curves,
extra dimensions and quantization are also held. Native `curveRings` stay in raw
evidence; no analysis area is published for them. Server fidelity remains a
source assertion, not a proof that the county's stored shapes are accurate.

Budgets: 1–500 selected parcels; batches at most 50 and no greater than the server
limit; at most 100 logical requests, 30-second timeout, three total attempts per
request, >=1-second pacing, 25 MiB per body, 128 MiB total capture files,
60-second single/120-second total waits. Oversized feature batches split by exact
OID membership; a single oversized polygon or aggregate excess holds the whole
run. Native/derived polygons have 200,000-vertex/1,000-ring per-polygon limits and
the complete analysis has a one-million-vertex limit. Budgets are engineering
limits, not county guarantees or silently relaxed thresholds.

## CRS decision and calculation

Native **ESRI:103736** resolves to `NAD_1983_HARN_Adj_MN_Isanti_Feet`, US survey
feet (exactly 1200/3937 metres). Its adjusted ellipsoid has semi-major axis
6378411.321 m and inverse flattening 298.257222100883. These datum/ellipsoid/unit
properties are checked against the reviewed definition; conflicting WKID/latest
WKID/WKT/vertical references fail. Full WKT2, source spatial-reference precision
metadata and PROJ database hash/version are retained, not just a numeric code.
[MnDOT's county projection table](https://www.dot.state.mn.us/surveying/toolstech/mapproj.html)
corroborates Isanti's adjusted ellipsoid and county projection parameters.

The analysis CRS is a **custom local Lambert Azimuthal Equal Area**, centred at
45.55 N, 93.3 W, with the *exact same native geographic datum/ellipsoid*, metre
axes, zero false origin. It has no invented EPSG ID. This avoids an unverified
Isanti-adjusted-datum -> ordinary NAD83 substitution. The generous reviewed
coordinate envelope (-94,45.2,-92.8,45.9) is a processing sanity guard, **not a
county boundary, authoritative coverage test or geodetic accuracy statement**.

Only one available same-datum operation with zero stated transformation error is
accepted. PROJ network access is disabled, ballpark operations are forbidden,
and required-but-missing grids hold. The selected pipeline, full source/analysis
WKT2, axis policy (`always_xy`), actual grids, Shapely/GEOS/pyproj/PROJ versions,
PROJ database hash and EPSG/Esri database versions are recorded.
[pyproj transformation controls](https://pyproj4.github.io/pyproj/stable/api/transformer.html)
and [custom CRS construction](https://pyproj4.github.io/pyproj/stable/build_crs.html)
support this explicit choice. Zero operation error is **not** zero boundary error.
No cross-datum alignment with wetlands/FEMA is approved by ML-302; ML-303/304 must
resolve and audit their actual operations/grids or hold the overlay. Never relabel
this adjusted datum as ordinary NAD83/UTM to bypass that gate.

Original Esri coordinates remain untouched. Analysis copies densify native straight
edges to <=10 metres before nonlinear projection; a <=20-metre copy provides a
convergence check. Float64 coordinates retain full output precision, no snapping
or rounding. A numerical area difference must be <=max(0.01 m², one part per
million of measured area); same-ellipsoid geodesic control must be within
max(0.01 m², ten ppm); inverse round-trip error must be <=0.001 m. These bound
numerical processing, **not** source boundary accuracy. Area is calculated from
validated equal-area polygons, never degrees, Web Mercator or `Shape__Area`.
Acres use the international acre, exactly 4046.8564224 m²; this is explicitly not
43560 US-survey-feet squared.

## Topology, unknowns and completion

[Esri polygon rules](https://developers.arcgis.com/rest/services-reference/enterprise/geometry-objects/)
define clockwise exterior rings and counterclockwise holes. The smallest strictly
containing shell owns each hole. Islands can remain separate multipart shells;
overlaps, orphan holes, duplicate rings, self-intersections, unclosed/degenerate/
empty/nonfinite coordinates and unsupported representations hold.
[Shapely's validity checks](https://shapely.readthedocs.io/en/stable/manual.html)
are explicit; construction alone is not validation. Topologically identical
polygons across different parcel IDs hold even when serialization differs.
No auto-closing, orientation fix, `make_valid`, `buffer(0)`, dissolve or other
repair is supported. Failed shapes retain their originals and diagnostic hold
with null area; no fabricated before/after repair record is generated.

Each published observation includes parcel/OID, canonical native-JSON geometry hash, normalized
analysis WKB/hash, part/hole/vertex counts, topology results, measured m²/acres,
new GIS deeded acreage and difference/flag, numerical control errors, source-field
names, and saved candidate deeded acreage separately. New geometry capture dates
live at run level; old dates remain in the pinned source graph. Missing deeded
acreage yields null difference/flag, not zero. A difference exceeding
max(0.1 acre, 2% of deeded acreage) is a **review flag**, not a source correction
or uncertainty interval. Measured acreage is not net/usable/developable acreage.

`parcel_geometry` uses the existing exclusive reservation/contained pinned graph/
hash inventory/completion protocol. Complete means **every selected identity and
analysis passed**. Any failure preserves staging plus `failure.json`; there is no
silent partial success, promotion of a failed run or old-run mutation. Offline
validation replays retained exact queries, reconciles source checks and wire bytes,
and reproduces analysis; changed libraries/databases/algorithm can refuse rather
than silently recalculate old evidence. Completion is integrity evidence, not a
county signature, operating-system immutability or backup of ignored data.

## Verification

Synthetic compact fixtures cover known area, holes/multipart, duplicate geometry,
invalid/empty/nonfinite/curved/Z shapes, CRS/unit/conflicting-WKT/axis failures,
missing best operation, ballpark rejection, precision/roundtrip/convergence,
deeded discrepancies, selected identity ambiguity, source drift, truncation,
batch splitting, individual/aggregate budgets, held/empty sources, pinning,
wire evidence and rehashed semantic tampering. Default tests never call government
services. See [dated testing evidence](testing.md#ml-302-parcel-polygon-foundation).
