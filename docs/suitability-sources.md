# Isanti suitability source contract (ML-301)

Decision/review date: **2026-10-17, America/Chicago**. Live observations were made
2026-10-18 04:07–04:25 UTC, still October 17 locally. This is source discovery and
a proposed acquisition/analysis contract, **not implemented parcel enrichment**.
No wetland/floodplain acreage, usable-acre estimate, score or legal determination
was produced. The existing viewer, tax conventions and saved results are unchanged.

## Decision

Use **Minnesota DNR's statewide NWI polygons plus their project-boundary metadata**
for the initial mapped-wetland/deepwater screen. Use **FEMA's effective National
Flood Hazard Layer (NFHL)** for flood categories, with separate availability,
panel-date and revision evidence. Retrieve parcel geometry separately from the
existing official Isanti service; the current attribute pipeline rejects geometry
requests and must not silently change behavior. County flood polygons remain a
separate comparison source, not a fallback substituted for FEMA.

This is an engineering selection for local research. It is not a finding that
state NWI is newer everywhere than federal NWI, that mapped constraints are legal
boundaries, or that data may be repackaged/sold. Source/terms/coverage checks below
remain release gates for later implementation and distribution.

## Compared sources

| Source | Coverage, dates and resolution | Access/terms finding | Decision and limitations |
|---|---|---|---|
| [DNR statewide NWI catalog](https://gis.data.mn.gov/maps/minnesota%3A%3Anational-wetland-inventory-for-minnesota-1/explore), [polygons](https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_dnr/water_nat_wetlands_inv_2009_2014/FeatureServer/0), [projects](https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_dnr/water_nat_wetlands_inv_2009_2014/FeatureServer/1) | Statewide mapped inventory; project-specific imagery, not 2026 ground conditions. Catalog modification 2026-09-23 is not an imagery date. Target mapped unit 0.5 acre; smaller wetlands can be missed. | Public Query/Extract, no token in observed requests. Catalog says custom license; item `licenseInfo` is literal `None`; metadata also references the DNR general license. Preserve all notices; do not interpret that string as unrestricted rights. | Selected baseline: explicit wetland classes, HGM/SPCC and project-date lineage. Separate deepwater/open-water from wetland classes; never treat inventory omission as dry/buildable land. |
| [USFWS national NWI](https://catalog.data.gov/dataset/usfws-national-wetlands-inventory), [official downloads](https://www.fws.gov/program/national-wetlands-inventory/data-download) | Nationwide biological inventory, with project metadata and variable observation dates. National catalog updated 2026-10-02; that does not prove newer Isanti imagery. State/watershed downloads support offline analysis; national refresh is generally twice yearly. | Public access and official downloads. Dataset-specific limitations/citation notices still apply; no license conclusion is drawn from access level or a fact-sheet's license. | Comparison alternative, not unioned with state NWI or an automatic outage fallback. Isanti-specific federal imagery/version equivalence was not established by this spike. Reassess if later regional metadata establishes a better source. |
| [FEMA effective NFHL](https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer), layers 28/0/3/1, table 41 | Live study `27059C` is present. Observed 28 panel records have 2003-11-05 effective dates and scales 1:6,000, 1:12,000 or 1:24,000. Seven LOMR geometries represent two case numbers, not seven independent revisions. | Unauthenticated Query supported; no fee/key in these probes. Service copyright/description fields are blank, not a blanket reuse license. Retain FEMA attribution and source notices; data redistribution/hosted use requires a separate review. | Selected effective flood screen: preserve zone, subtype, SFHA flag, panel and revision context. Do not mix preliminary/pending layers into effective results or use availability polygons as hazard polygons. |
| [Isanti Flood Zones](https://gis.co.isanti.mn.us/arcgis/rest/services/Zoning/FloodZones_Public/MapServer/0), [county GIS notice](https://www.isanticountymn.gov/175/Geographic-Information-Systems) | 775 polygon records observed; schema has `FLOODZONE`, `FIRMPANEL`, `BFE`. One sample X feature has null panel/BFE/edit dates. No verified dataset effective date or positional accuracy was established. | Public Map/Query/Data; credits Isanti County GIS/FEMA. County says reference use, not legal descriptions, with accuracy/availability disclaimers. No separate redistribution grant was verified. | Local comparison/reference only. Lacks FEMA's explicit X subtype and SFHA fields. Counts are not directly comparable to a FEMA study query; never assume both sources are equivalent or combine them. No separate county-authored wetland inventory was established in this bounded review. |
| [Isanti TaxParcels_Public/0](https://gis.co.isanti.mn.us/arcgis/rest/services/LandRecords/TaxParcels_Public/FeatureServer/0) | Polygon service, native WKID 103736; existing deeded acres are attributes, not polygon-derived area. One sample returned one ring/five coordinates for `01.013.1402`, recorded deeded acres 20.0. | Public Query/Extract; county reference-only disclaimer applies. Geometry is not a survey/legal description. | Selected parcel boundary provider for ML-302's separate acquisition path. A new geometry capture is a new dated observation; it must not be relabelled as geometry captured with the older ML-130 attribute snapshot. |

### Wetland dating, accuracy and use terms

[DNR metadata](https://www.arcgis.com/sharing/rest/content/items/b02794b39e1e4125a3c89b059195f3dc/info/metadata/metadata.xml?format=default&output=html)
records original publication 2015-04-30, content-update 2019-05-23, metadata date
2024-03-28 and base imagery spanning 2009–2014. These dates describe different
events. A native-coordinate **bounding envelope**, taken from the county parcel
layer extent, intersects two project records: ECMN imagery `2010`, delivered
2013-05-24; CMN imagery `2013, 2014`, delivered 2018-07-23. The envelope includes
land outside the county and proves neither full county coverage nor that both
projects overlap a given parcel. Later code must spatially bind project dates to
the actual parcel/AOI; missing dates remain unknown.

[DNR's FAQ](https://www.dnr.state.mn.us/wetlands/nwi_faq.html) states the inventory
is preliminary, not a jurisdictional delineation. Its 0.5-acre target is not an
area precision guarantee. The FAQ describes approximately ±5.9 m for 95% of
well-defined boundaries; the dataset metadata gives a different, limited
well-defined-boundary assessment of ±15 m. Preserve both assessments and their
scope; do not average them or promise either as a parcel-specific error bound.
Seasonality, imagery interpretation and small/obscured features limit screening.
[USFWS likewise cautions against regulatory-boundary interpretations](https://www.fws.gov/page/wetlands-geodatabase-disclaimer).

The metadata's linked [general license page](https://www.dnr.state.mn.us/sitetools/data_software_license.html)
did not expose agreement text through the reader. An [official DNR page carrying
the General Geographic Data License](https://www.dnr.state.mn.us/wmas/gps/license.html)
requires acknowledgment and describes a non-sublicensable license with restrictions
on selling the data without written permission; dataset-specific terms can prevail.
That page also contains WMA/GPS-specific cautions, which are not NWI accuracy claims.
Record the catalog/metadata/general-license discrepancy explicitly. **No raw-data
resale, sublicensing or public dataset redistribution is authorized by this spike.**
Resolve applicable terms before that separate product/distribution scope. Preserve
publisher, dataset title/date, notices and attribution in derived research outputs.
This is a source-notice review, not legal clearance or acceptance of an agreement.

### Flood dates, categories and coverage

FEMA live queries confirmed availability study `27059C`, **718 zone polygons** and
the following source combinations. These are feature counts, not parcel counts,
affected acres, unique cases or evidence of a complete parcel/AOI download.

| FLD_ZONE | ZONE_SUBTY | SFHA_TF | Polygon records |
|---|---|---|---:|
| A | null | T | 354 |
| AE | null | T | 119 |
| AE | FLOODWAY | T | 12 |
| X | 0.2 PCT ANNUAL CHANCE FLOOD HAZARD | F | 59 |
| X | AREA OF MINIMAL FLOOD HAZARD | F | 174 |

Do not collapse X to a single constraint/risk meaning. Keep mapped SFHA, floodway,
0.2%-chance and minimal-hazard observations separate. Future subtraction policy is
explicit/versioned in ML-304/305, not inferred from a renderer color or this table.
No overlap outside selected polygons means **no mapped overlap within verified
coverage**, not “no flood risk.” DNR distinguishes effective, preliminary, paper
and unmapped products in [its flood-map guidance](https://www.dnr.state.mn.us/waters/watermgmt_section/floodplain/access-flood-maps.html).

The 28 returned panel records have scales 1:6,000 (2), 1:12,000 (15), 1:24,000 (11);
do not assign one national resolution or positional accuracy. Their common 2003
date does not date every later change. Returned LOMR geometries have effective
dates 2004-06-21 and 2006-04-12. They are supporting revision footprints, not extra
hazard polygons to add to overlap area; LOMA determinations also require separate
context and are not silently applied to parcel status.

**Source anomaly:** table 41's Isanti `INDX_EFFDT` is raw `218330035200000`, decoding
to **8888-08-08**, while `DBREV_DT` is null. It is not a usable current/effective
date. Retain raw/normalized-invalid state and warn; never replace it with capture
time, the panel date or today's date. Valid panel dates remain separate evidence.
No regulatory, insurance, permit or no-risk conclusion is made from this source.

## Observed interface contract

These are live observations, not permanent guarantees. Reinspect before acquisition.

| Layer | Native SR / OID | Limit / supported operations | Explicit fields to retain |
|---|---|---|---|
| DNR NWI 0 | WKID 26915 / `objectid` | 2,000; Query/Extract; ordered pagination; JSON/GeoJSON/PBF | `objectid,attribute,wetland_type,acres,hgm_code,hgm_desc,spcc_desc,cow_class1,circ39_class,hgm_symbol` plus untouched polygon |
| DNR Project Boundary 1 | WKID 26915 / `objectid` | 2,000; ordered pagination | `objectid,project_area,project_area_name,project_partner,delivery_date,spring_imagery_year` plus footprint |
| FEMA NFHL 28 | WKID 4269 / `OBJECTID` | 2,000; Map/Query/Data; ordered pagination | `OBJECTID,DFIRM_ID,FLD_AR_ID,FLD_ZONE,ZONE_SUBTY,SFHA_TF,SOURCE_CIT,GFID,GlobalID` plus polygon |
| FEMA 0 / 3 / 1 / 41 | WKID 4269 for spatial layers / `OBJECTID` | 2,000; Query; table 41 has no geometry | Availability `STUDY_ID`; panels `FIRM_PAN,EFF_DATE,SCALE,PANEL_TYP`; revisions `CASE_NO,EFF_DATE,STATUS`; study `INDX_EFFDT,DBREV_DT` and source study ID |
| Isanti parcel 0 | WKID 103736 / `OBJECTID` | 24,000; Query/Extract; ordered pagination | `OBJECTID,PARCELID,UNFORMATTEDPIN,DEEDEDACRES` plus native polygon, without unrelated tax/owner fields |

Source SR/units/precision are not positional accuracy. State NWI uses the documented
NAD83 UTM zone 15 coordinate system; FEMA returns NAD83 geographic coordinates.
Do not calculate square degrees or Web-Mercator acres. ML-302 must resolve/retain
full CRS definitions, county foot-unit/datum details and a tested transformation;
choose and justify the analysis CRS and area-distortion tolerance there. WKID
numbers alone are not evidence of a correct transform. No new geometry library,
reprojection, topology repair or area algorithm is installed/implemented here.

### Sample requests — specification, not a new command

Use the [ArcGIS query API](https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/)
with explicit parameters and bounded requests. Metadata is inspected before queries;
JSON parse success/HTTP 200 is insufficient if an ArcGIS error is present. For
MapServer layers use their corresponding [map-layer query API](https://developers.arcgis.com/rest/services-reference/enterprise/query-map-service-layer/).

```text
GET {Isanti parcel layer}/query
f=json
where=PARCELID='01.013.1402'
outFields=OBJECTID,PARCELID,DEEDEDACRES
returnGeometry=true
outSR=103736
orderByFields=OBJECTID ASC
resultRecordCount=2
```

That discovery request returned exactly one feature. It is not proof all candidate
IDs are unique. ML-302 must reject missing/duplicate/conflicting parcel identities,
not pick the first row. Do not request source simplification, quantization or a
geometry precision reduction by default; retain native bytes before transformations.
The small discovery probes did not request true curves and therefore do not prove
curve fidelity. For the production path, explicitly request `returnTrueCurves=true`
where supported: the API otherwise densifies curves. Preserve `curveRings` or hold
unsupported curves rather than silently linearizing them. Retain Z/M when present
(or explicitly reject unsupported dimensions); do not quietly discard them while
claiming original geometry preservation. No server reprojection is a substitute
for recording and validating the analysis transform.

```text
GET {DNR NWI layer 0}/query
f=json
where=1=1
geometry=<validated native-SR AOI envelope>
geometryType=esriGeometryEnvelope
inSR=<explicit AOI SR>
spatialRel=esriSpatialRelIntersects
returnCountOnly=true

GET {FEMA NFHL layer 28}/query
f=json
where=DFIRM_ID='27059C'
returnCountOnly=true
```

County/study filtering alone is not sufficient for parcel-boundary completeness:
the production AOI acquisition must include every intersecting feature, including
adjacent studies/counties where applicable. A bounding query selects candidates;
it does not clip polygons or prove coverage. Request native geometry and explicit
fields in subsequent pages, then clip locally only after validated reprojection.

For each fixed query/AOI: capture initial/final metadata, exact count and bounded
OID membership; retrieve deterministic OID batches/pages (initial proposed batch
500, never above the advertised cap); reconcile unique membership, count, geometry
and transfer-limit flags before completion. Split oversized geometry batches under
an explicit budget, not by dropping vertices. Count-zero is not coverage proof.
No equality of counts alone proves an atomic snapshot: retain available edit/version
tokens and report `transactional_snapshot=false`; hold on detectable drift.

The discovery NWI envelope count was **28,401**, not an Isanti wetland count or an
area estimate. Single NWI/FEMA feature probes correctly returned
`exceededTransferLimit=true`; those are **incomplete samples**, never enrichment
inputs. Full-state downloads were not made. The state catalog advertises FileGDB/
GeoPackage; the small AOI REST route avoids assuming an old download URL/format or
adding a shapefile-size workaround. A future bulk route must pin its own archive,
metadata, CRS and completeness evidence instead of silently replacing REST bytes.

## Proposed retained observations and failure states

These are requirements for later work, not fields already present in `Parcel`:

- Source identity: agency, dataset/item/service/layer, source feature ID within the
  captured version, original fields, request URL/parameters, AOI/selection hash,
  retrieval times, exact source-body hashes and pinned completion identities.
  OIDs are snapshot-local; cross-version equivalence is not assumed.
- Geometry: untouched native rings/curves/CRS and bytes, validated transformed copy,
  library/grid/transform/policy versions, units, precision, topology diagnostics,
  repair before/after evidence if explicitly supported. Null/empty/nonfinite,
  malformed, incompatible, ambiguous or unsupported geometry must not become area 0.
- Dates: publication, catalog modification, imagery/project, effective panel,
  revision, retrieval and processing times remain independent. Invalid/future
  observations retain raw values/reasons; source nulls do not become today's date.
- Coverage: distinguish known-complete AOI, partial, unmapped, unavailable, unknown,
  changed-during-read and invalid evidence. Require independently verified project/
  study footprints and reconciliation before claiming complete coverage. If part
  of a parcel is uncovered, preserve the uncovered geometry/amount/status rather
  than extrapolating a complete result.
- Metrics: deeded acres, measured polygon acres, mapped wetland/deepwater overlap,
  mapped flood category overlaps and estimated remaining area are distinct. A
  missing/failed/partial source yields **null/held**, not zero constraint or usable
  acres. A genuine computed zero requires complete coverage and valid geometry.
  Precision/rounding and tolerances are explicit; source `acres`/`Shape__Area`
  values are not a substitute for clipped area in the chosen analysis CRS.
- Keep independent overlaps visible. A later combined constraint uses a geometry
  union to avoid subtracting shared wetland/floodplain area twice, bounded by measured
  parcel area; never subtract from deeded acres as if the two area measures matched.
  Unknown classification/category remains visible and holds affected conclusions.

Reuse existing paced, bounded HTTP/completion principles in a **separate geometry
path**. Proposed defaults: one request at a time, at least one second spacing,
30-second request timeout, at most three total attempts, bounded Retry-After/wait
budgets and body/OID/feature limits. Configure/archive effective limits. A required
wait over budget means stop/retry later; do not bypass controls. UI interaction must
not fetch these sources automatically. Offline fixtures remain the normal tests;
any live checks are explicit, bounded and dated. No new executable command is
introduced by the examples above.

## Bounded follow-up stories

1. **ML-302, next:** separate parcel polygon acquisition/pinning; explicit selected
   saved candidate identity and geometry capture date; CRS/units/transformation,
   geometry validation, measured-versus-deeded area and offline fixture contracts.
   No wetlands/floodplain overlay or UI feature is delivered by that foundation.
2. **ML-303:** acquire/reconcile NWI plus project footprints for the actual parcel
   AOIs; preserve wetland/deepwater/unknown classifications and dates; pin the
   reviewed inclusion policy and dissolve/clip without double counting. Reassess
   federal/state regional versions rather than assume a national catalog date wins.
3. **ML-304:** acquire/reconcile effective NFHL zones and coverage/panel/revision
   context; preserve X subtypes/floodway/SFHA and invalid dates; never claim risk-free
   land from a missing or partial layer. County comparisons cannot silently override.
4. **ML-305/306:** explicitly version the constraint-union/remaining-area policy,
   coverage and precision; validate representative official-map cases and publish
   separately dated enrichment, never inferred legally buildable acres.

Commercial data redistribution/hosting, onsite delineation, permit/insurance
determinations, terrain/access/zoning, valuations and additional counties remain
outside this source-discovery story. No outreach or request to government staff
was made. Do not treat the data-access investigation as permission to start all
follow-ups automatically.

## Evidence and validation

Private new discovery artifacts are under
`data/processed/isanti/preparation/ml-301-2026-10-17/`, not inside completed county
runs and not committed as raw data. `probe_sources.py` contains the exact allowlisted
URLs/parameters; `discovery-index.json` indexes outcomes, source-body hashes and the
observed UTC window. Each HTTP capture keeps original bounded response bytes,
parsed sidecar and size/hash/outcome evidence. The script is a private exploratory
helper, not a supported ingestion/replay command or production completion record.

There are 37 capture records: 28 successes, seven initial sandbox network failures,
one optional FEMA date-summary timeout and one county ArcGIS item lookup returning
400. The approved network run succeeded for the selected services. The timed-out
summary was not relied on; a separate bounded panel-attribute request returned 28
records with no transfer-limit flag. Web-reader FEMA-page/REST failures were not
equated with missing data; direct public structured metadata/query requests worked.
No controls, login or CAPTCHA were bypassed. These are discovery snapshots, not a
full source acquisition or guarantee of continuing availability.

Selected original response SHA-256 values (all `attempt_00001.body`):

| Probe directory below the preparation folder | SHA-256 |
|---|---|
| `probe-d7b3553b/nwi_polygons` | `4533fb6a2fb2b688c242d5b94ec2683c8f003422485de81231f77c9c3b57fa70` |
| `probe-d7b3553b/nwi_projects` | `57f847f6107e81d367decfce7dfe0903c98e2ffb32b46e349deb3160bf2a5f5c` |
| `probe-de6233c9/fema_zones` | `467a388a796b2310653744a4ee88ff313652b910f287fb2eea97c12dc6497a98` |
| `probe-d2858111/fema_isanti_panel_inventory` | `711fdaeffd6bab1223c45b81fcf51f23f9e6a68932005ab8af21906bc113077c` |
| `probe-d2858111/fema_isanti_revisions` | `d8eecd2bda4b6a399112cc6b625d68a58f899f8669800752d035926b5004d9f2` |
| `probe-cb3e2ed3/fema_isanti_study` | `34618885881296540a96385c48ae6b7ff39250df3bc9f3479738e71b465e54e0` |
| `probe-cb3e2ed3/parcel_geometry_sample` | `80653caf61097caf28deff704e731154d0e6cff1e0a3f50c0d74497805f03b3c` |

The offline discovery audit verified retained response hashes, category-count
reconciliation, bounded panel/revision samples, the parcel identity/rings and the
incomplete wetland sample flag. It did **not** test overlay accuracy or scientific
area calculations. All 871 files in the preexisting retained county/audit baseline
still match size/SHA-256. No existing source, mapping, completion, result or latest
pointer was rewritten. No runtime dependency, production/test/CI code or viewer
change was needed; this spike is validated by evidence/contract review and the
board/documentation checks, not artificial new unit tests. Documentation-only CI
uses its configured Linux-only path, not a repeated Windows matrix.
