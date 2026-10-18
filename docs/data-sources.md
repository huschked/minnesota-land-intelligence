# Data sources

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
