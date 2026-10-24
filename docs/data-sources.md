# Data sources

## Official-map comparison and saved enrichment (ML-306)

[ML-306](suitability.md) publishes saved calculations, not new ingestion. Dated
DNR Wetland Finder views and official FEMA zone/panel renders were inspected for
high-overlap, covered-zero and held/cross-study samples and retained privately.
All six not-printed-panel inventories and the tiny computational residue were
reviewed; v1 holds remain unchanged. Rendered panel grids do not alone resolve
study applicability, and blank images do not establish zero hazard. Published
source limitations remain separate from numerical checks. No government contact,
map selection override, tax refresh or source-data hosting clearance is introduced.

## Offline combined constraint derivation (ML-305)

[The constraint operation](constraints.md) queries no source. It uses explicit
completed DNR/FEMA observations with identical saved parcel geometry and verified
alignment evidence. New processing does not refresh imagery, effective maps,
parcel boundaries or tax balances. The versioned policy includes mapped wetlands,
open water, deepwater and riverine as distinct water constraints plus SFHA;
floodway is nested and 0.2%/minimal-hazard zones are not subtracted. Existing raw
values, spatial dates, source notices and unknowns are preserved in pinned inputs.

## Effective FEMA flood acquisition (ML-304)

[The separate flood path](floods.md) uses the selected official NFHL MapServer:
zones 28, independent availability 0, panels 3, LOMRs 1 and associated Study_Info
41. Native EPSG:4269 geographic coordinates receive an explicit audited operation,
not ordinary-NAD83 relabeling, DNR's UTM input or square-degree area. Spatial AOIs
are not restricted by a county/study filter; study IDs join coverage and date
context only after exact membership retrieval. Missing MapServer metadata
declarations stay unknown and actual returned geometry gates support. Source
counts/OIDs/schema/edit evidence reconcile and originals are retained. No county
fallback, preliminary/effective mixture, revision-as-hazard addition, inferred
LOMA relief, source-data redistribution clearance or tax refresh is introduced.

## DNR wetland acquisition (ML-303)

[The wetland path](wetlands.md) captures DNR Statewide NWI (layer 0) and Project
Boundary (layer 1) for explicit parcel AOIs in native EPSG:26915. Initial/final
counts/OIDs, schema and available edit tokens reconcile; absent edit consistency
is disclosed. Independent project footprints gate coverage, and their intersected
imagery/delivery dates remain separate from 2026 retrieval and old parcel/tax dates.
The explicit Isanti adapter uses the pinned NOAA Minnesota HARN grid and visually
checked MnDOT coordinate pairs, not ordinary-NAD83 relabeling or ballpark fallback.
Unsupported/contradictory classes and incomplete coverage hold numeric totals.
This implements the DNR selection, not a federal/state union or proof of the
newest regional imagery. Source accuracy and unresolved distribution limitations
in [ML-301](suitability-sources.md) still apply. No FEMA implementation or tax
balance refresh occurs here.

## Parcel geometry acquisition (ML-302)

The [separate geometry path](geometry.md) uses the existing official Isanti
TaxParcels_Public FeatureServer/0, requesting only identity/deeded fields and
native polygons for a selected completed review. Exact start/end counts/OIDs,
schema/edit tokens and per-batch parcel identity reconcile before completion.
Native ESRI:103736 uses the adjusted Isanti ellipsoid and US survey feet; full
definitions are resolved/retained, not silently replaced by ordinary NAD83.
New geometry capture time is separate from the October listing and older GIS
capture. True curves are requested explicitly and held if returned; unsupported
Z/M, missing/invalid geometry and incomplete responses never become zero area.
This adds neither a county tax refresh nor thematic-source acquisition. Existing
source accuracy/use/distribution limitations still apply.

Source priority is: official county ArcGIS REST API, official GIS download, official structured tabular data, then official pages. Unofficial substitutes and browser scraping are not used when an authoritative structured source exists.

Every source must be inspected for layer purpose, aliases/types, geometry, spatial reference, record limits, query and pagination capabilities, and semantic definitions. Field names are not definitions. Ambiguous values are retained with cautious names and cannot drive stricter candidate claims.

## Delinquency hierarchy

1. Official county delinquent-tax dataset or electronic file
2. Official county publication
3. Applicable court filing or other authoritative public filing
4. Other authoritative county material

Newspaper OCR and third-party aggregators are not authoritative structured data. File import requires a reviewed mapping and an explicit assertion that rows represent delinquent parcels. Parcel GIS and delinquency sources retain separate lineage.

The reviewed October export supports the existing mixed prior/current assertion
under [county-confirmed year conventions](counties/isanti-tax-year-confirmation.md),
not an assertion that every row is prior-year delinquency. See
[ingestion contracts](ingestion-contracts.md) for the observed schema evidence,
field/type gates, service limits/retry/completeness rules, file constraints,
and partial-run policy. ML-125's [file/schema validation](validation.md) is
implemented, as are ML-126's [HTTP retrieval/completeness](retrieval.md) and ML-127's
[completion publication and reader validation](publication.md). Existing retained
pre-completion snapshots remain legacy/unverified, not silently migrated. An active year convention always requires retained evidence;
strict parsing does not expand the authority or meaning of any source.

[ML-123 replay](replay.md) selects completed retained parcel/import inputs explicitly
or from a completed join's contained graph; it does not fetch another source, follow
old absolute paths or silently replace inputs with latest. County/service/layer/full
query compatibility, source dates and missing publication dates are surfaced. Date
differences are not a freshness or payment-status conclusion. Pre-completion inputs
remain legacy/unverified; no source inventories or completion evidence are backfilled.

[ML-130](reviews/isanti-viewer-preparation-2026-10-16.md) subsequently captured
genuine new eligible runs from the same official Isanti GIS and unchanged October
13 county listing. Historical files remain untouched. The [ML-202 viewer](viewer.md)
reads those saved graphs without a source request, replay or reimport; a new UI
load/validation date is not a fresh tax statement or payment-status check. No new
county source, monetary definition, report verification or source-year meaning is
introduced by the UI.

[ML-124 comparisons](snapshot-comparison.md) preserve two saved observations,
including separate listing publication/capture and GIS capture dates. Explicit
operator freshness thresholds do not establish a county validity period or current
payment status. Disappearance is only non-observation; split/retirement links are
not inferred. No new source request, tax definition or accounting resolution is
introduced by the comparison report.

ML-203's saved candidate table reads the selected join's prior/current exports
through completion/inventoried-byte validation. County classification and parcel-ID
separator rules are reused, not redefined by widgets. Filtering source observations
does not refresh them or establish vacancy, usable/buildable acreage, tax debt or
current payment status. GIS owner text is labelled independently; no listing/GIS
owner merge or new contact enrichment is introduced.

ML-204 reads all contributing listing rows from exact inventoried source bytes;
assessment/payable/report-year distinctions reuse the retained county-confirmed
convention, not the host clock. Raw monetary abbreviations and effective/letter
dates remain literal observations with unresolved definitions, not computed debt
or inferred balance dates. GIS attributes retain source-field labels and listing
owner text stays separate. Evidence names/hashes identify retained year support
without serving correspondence or arbitrary local files.

The only public links are reviewed Isanti HTTPS GIS-layer and parcel-report
destinations (and a mapping source URL only if it meets that same strict allowlist).
Parcel-report PIN must match the selected parcel. No source row supplies arbitrary
clickable URLs; no report or website is fetched/embedded in the viewer. Link
validation is not a live response/content check. Synthetic links are suppressed.
Only an inventoried comparison pinned to the selected review can contribute a
parcel-specific sample result, with recorded payable years and unknown source-hash/
report-verification-date binding disclosed. The ML-130 review has no such sample;
ten historical checks elsewhere are not applied to its parcels or current balances.

ML-205 [contextual exports](worklist-exports.md) consume the same selected pinned
graph. Preview and click-time generation validate exact saved evidence, not a live
county account. Candidate fields reuse reviewed year/money/source-row checks;
unmatched/duplicate/ambiguous/unverified/fiscal-group and redacted diagnostic entries
remain snapshot-wide issues. CSV text protection never changes retained source
bytes; JSON preserves canonical text/nulls. No source refresh, inferred balance,
owner merge, evidence publication or new contact enrichment occurs.

## Suitability source discovery (ML-301; no enrichment implemented)

The [dated Isanti suitability contract](suitability-sources.md) compares county,
state and federal coverage, dates, resolution, interfaces and use notices. Selected
thematic providers are DNR statewide NWI plus project footprints and FEMA effective
NFHL plus availability/panel/revision context. The county flood layer is a separate
comparison, not an automatic substitute. For these themes the primary publishing
agency's lineage/category detail takes precedence over a thinner county derivative;
county-first discovery does not imply county data is always the best thematic source.

Bounded live metadata/query samples confirmed both services and a single Isanti
parcel polygon. They are new discovery observations, not geometry attached to old
tax snapshots or a refreshed delinquency account. Catalog update, imagery, panel
effective, revision and capture dates remain separate; a raw FEMA study date in
year 8888 is invalid, not a current effective date. Missing/partial coverage must
hold derived metrics as unknown, not zero. Use/attribution notices and unresolved
redistribution scope are preserved; public access is not blanket data-resale rights.
ML-302/303/304 own actual acquisition/geometry/overlay implementation and fixtures.
