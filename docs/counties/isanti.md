# Isanti County

## Mapped wetland screen — 2026-10-19 (ML-303)

The [separate DNR wetland operation](../wetlands.md) uses explicit saved geometry,
not a fresh tax balance. `wetland_crs.py` resolves the county-adjusted projection
bridge with two visually checked MnDOT historical coordinate tables and the
actual pinned Minnesota NOAA HPGN/HARN grid. No automatic ordinary-NAD83
substitution is used. DNR native UTM geometries are captured unchanged before
analysis-copy clipping/transformation. Independent project footprints gate
coverage; spatial imagery/delivery context and separate deepwater/open-water/
riverine classes remain visible. Unknowns give held/null totals. No legal
buildability, flood/remaining-acre calculation or viewer change is included.

## Native parcel polygon capture — 2026-10-18 (ML-302)

[Geometry CLI/contract](../geometry.md) adds a separate bounded capture from an
explicit completed review, requiring exact `PARCELID`/`UNFORMATTEDPIN`/`OBJECTID`
agreement. Native ESRI:103736 is `NAD_1983_HARN_Adj_MN_Isanti_Feet`, an adjusted
county ellipsoid with US survey feet, not ordinary NAD83/UTM. Same-native-datum
local equal-area screening avoids an unapproved datum shift; thematic alignment
must be separately resolved before ML-303/304 overlays. Deeded acres, measured
GIS acres and saved snapshot dates remain distinct. Unsupported curves/Z/M,
ambiguous identity and invalid shapes hold without repair or partial completion.
The user-approved live scope is only the existing 15-parcel focused review;
no new tax information, UI changes or county staff request is part of this card.

**Current status: year semantics resolved by county correspondence.** `TAXYR`
is report assessment year; `ASMTYR` identifies the individual charge assessment
year. Taxes payable follow assessment by one year. The export includes unpaid
prior years plus overdue first-half 2026 installments. The earlier hold based on
comparison to the wrong payable-year column is superseded. Corrected results:
62 large parcels with listed prior-year delinquency (49 outside PILT/exempt),
and 291 large parcels with overdue current-year installments, including 42 that
also appear in the prior-year view. Balances remain unaggregated. See
`docs/counties/isanti-tax-year-confirmation.md` and
`docs/reviews/isanti-prior-year-results-2026-10-14.md`.

Accessed: 2026-08-23

[ML-123 replay](../replay.md) checks selected completed parcel inputs against this
configured county service/layer and full-county query. File and GIS dates remain
independent. The historical October results above were not regenerated or certified
under the new protocol; replay adds no monetary definitions or tax-currentness claim.

## Selected source

- Agency: Isanti County GIS
- Dataset/layer: `TaxParcels_Public`, layer 0
- Feature service: `https://gis.co.isanti.mn.us/arcgis/rest/services/LandRecords/TaxParcels_Public/FeatureServer`
- Layer URL: `https://gis.co.isanti.mn.us/arcgis/rest/services/LandRecords/TaxParcels_Public/FeatureServer/0`
- Purpose stated by the parallel official MapServer: published real-property areas combined with CAMA assessing and tax-system information.
- Geometry: `esriGeometryPolygon`
- Spatial reference: WKID 103736; service units are feet
- Maximum record count: 24,000
- Query: JSON/GeoJSON/PBF, advanced queries and pagination supported
- Count observed on 2026-08-23: 23,890 (live and expected to change)

The live run requested 2,000 records per page and completed in 12 ordered pages with an exact count match. Geometry was intentionally omitted from attribute ingestion to avoid transferring large polygon payloads before spatial analysis is in scope. Source `OBJECTID` values `24291464` and `24291465` lacked parcel IDs and were reported as normalization errors rather than silently accepted.

## Field mapping

| Canonical concept | Source field | Official alias | Interpretation |
|---|---|---|---|
| parcel ID | `PARCELID` | Parcel Identification Number | direct |
| deeded acres | `DEEDEDACRES` | Deeded Acres | direct |
| owner | `OWNERNME1` | First Owner Name | only first owner field published |
| mailing address | `PSTLADDRESS*`, `PSTLCITY`, `PSTLSTATE`, `PSTLZIP*` | Postal fields | combined without inventing missing components |
| previous taxes owed | `TOTPRVTXTOD` | Total Previous Taxes Owed | retained under this exact cautious concept |
| current taxes owed | `TOTCNTTXOD` | Total Current Taxes Owed | direct source-aligned concept |
| land value | `LNDVALUE` | Land Value | direct |
| improvement value | `IMPRVALUE` | Improved Value | normalized as improvement value |
| assessed value | `CNTASSDVAL` | Current Assessed Value | direct |
| classification | `PRIMARYCLASS` | Class Classification 1 | primary only |
| legal description | `LEGALDESCRIPT` | Legal Description | direct |
| source reference | `PARCEL_REPORT` | Parcel Report (Link) | direct |

## Tax semantics and limitation

Official layer metadata calls `TOTPRVTXTOD` “Total Previous Taxes Owed.” It does not define “previous,” state that the balance is delinquent/past-due, identify the tax year, or explain payment/update timing. Therefore this implementation does **not** map it to `past_due_tax_amount` and does not emit qualifying candidates. It retains the value as `previous_taxes_owed` for audit/manual follow-up. Written confirmation or an official data dictionary from Isanti County is required to enable the strict tax criterion.

In the 2026-08-23 run, 6,697 of the 7,091 normalized parcels with at least 10 deeded acres had a positive `TOTPRVTXTOD`. That prevalence reinforces that the value must not be assumed to mean delinquency. A separate, explicitly non-candidate review sample is generated for semantic confirmation.

## Phase 1.1 delinquency integration

The official [Isanti County delinquent-taxes page](https://www.isanticountymn.gov/731/Delinquent-Taxes) defines unpaid prior-year tax and penalty as delinquent and describes annual court filing and newspaper publication. As of 2026-08-23, no current official downloadable CSV/XLSX parcel list was located. The requested county electronic file remains the intended authoritative input.

Use `inspect-delinquency-file` first, then create a reviewed mapping based on `docs/examples/isanti-delinquency-mapping.example.json`. Import accepts only CSV/XLSX and requires an explicit `each_row_represents_delinquent_parcel` assertion. The original file, mapping, hashes, and import manifest are retained under `data/raw/isanti/delinquency/<run-id>/`.

### Parcel-ID normalization

Isanti join keys are created by trimming leading/trailing whitespace and removing only periods, hyphens, and whitespace. The remaining value must consist entirely of digits. Original identifiers are preserved. There is no fuzzy matching, numeric coercion, padding, or truncation. Thus `01.001.0201`, `01-001-0201`, and `01 001 0201` join to `010010201`; identifiers containing letters or other punctuation fail validation.

One source row plus one GIS parcel with the same normalized key becomes `VERIFIED_DELINQUENT`. Multiple source rows or multiple GIS parcels sharing a key become `AMBIGUOUS`. Source rows with no GIS parcel become `UNMATCHED`. Absence from a published list remains unverified and never means current.

Actual source-column mappings must be added here only after the county file arrives and is inspected.

## October 13, 2026 county listing import

The following initial-import notes and counts are historical. They predate county
clarification and are superseded by the current status above; raw snapshots remain
unchanged for audit.

The user supplied `Delinquent Tax Listing 10-13-26.csv` from Isanti County.
Provenance is the user's statement of county delivery; no accompanying cover
letter or field dictionary was supplied. The reviewed mapping is
`docs/counties/isanti-delinquency-2026-10-13.mapping.json`.

- Listing date: 2026-10-13, as supplied by the user and original filename.
- Internal `EFFDATE` and `LTRDT`: `7-Oct-26` on every row. October 13 must not
  be presented as a confirmed balance-effective date.
- Original rows: 1,783; distinct `PARID` values: 871.
- All rows have `ROLLTYPE=RP` and `TAXYR=2025`.
- `PARID` maps to parcel ID, `OWN1` to delinquency-source owner, and `TAXYR`
  to listed delinquent year. All IDs are nine-digit strings; no zero padding
  or numeric conversion was applied.
- Mailing columns and all abbreviated monetary columns remain in original
  source rows. They are not silently assigned canonical meanings.
- For every row, `TOTAMT = TAXAMT + PENAMT + INTAMT + FEEAMT` using exact
  decimal arithmetic. This establishes arithmetic consistency, not the
  accounting definition or effective date of each component.

The parcel GIS was refreshed on 2026-10-14: 23,890 features retrieved and
23,888 normalized, with the same two missing parcel IDs reported separately.
The final join output is
`data/processed/isanti/delinquency/2026-10-14T143019768539Z/`.

| Result | Count |
|---|---:|
| Unique normalized source-to-GIS matches accepted | 447 |
| Accepted parcels with at least 10 deeded acres | 164 |
| Duplicate delinquency parcel IDs | 420 |
| Source rows with ambiguous GIS joins | 1,328 |
| Ambiguous matched parcel IDs | 419 |
| Ambiguous matched parcels with at least 10 acres | 147 |
| Unmatched source rows | 8 |
| Unmatched distinct parcel IDs | 5 |

The unmatched IDs are `050080500` (four source rows), `130240105`,
`066090010`, `126090010`, and `136090010`. No fuzzy matching or aggregation
was used to resolve them. They require county review for identity, parcel
changes, or roll-specific identifiers.

Candidate JSON includes each entire original county row and independent
delinquency metadata. Canonical balances remain null pending a county data
dictionary. Source `TOTAMT` is available in `delinquency_original_row`.
The candidate CSV and JSON describe listed delinquency for this snapshot,
not a guarantee that a balance remains unpaid at a later date. GIS owner text
differs from source `OWN1` for 128 of 164 candidates; both values are retained,
and no ownership history is inferred from that difference.

All 164 candidate IDs, source-row references, and acreage thresholds were
independently checked against the retained inputs. A deterministic ten-record
sample is exported for human county-record comparison. No manual viewer
verification has yet been claimed.

The public data carries an accuracy/currency/suitability disclaimer. Parcel reports can support human comparison but do not replace county confirmation of field semantics.

## Ingestion hardening discovery (ML-119)

The two retained August 23 and October 14 `layer_metadata.json` files inspected
during ML-119 have identical SHA-256 hashes, field names/types/aliases/nullability,
and advertised limits. No actual GIS schema drift was observed between those
captures; this is not a fresh live-service check or a promise against future drift.
The known year-heading clarification is an existing county semantic correction,
not permission to infer a new field meaning. CSV versus XLSX year-cell types are
an ingestion-format issue documented in the [contract and fixture matrix](../ingestion-contracts.md).

That document preserves the mixed prior/current convention, unknown balances,
and unresolved identities while specifying bounded ML-125/126/127 hardening.

## Suitability source discovery — 2026-10-17 (ML-301)

The [reviewed source/retrieval contract](../suitability-sources.md) selects DNR NWI
and its project-date footprints for preliminary wetland/deepwater screening, FEMA
effective NFHL for categorized flood screening, and this county's existing parcel
service for a future separate geometry path. The county
[`Zoning/FloodZones_Public/MapServer/0`](https://gis.co.isanti.mn.us/arcgis/rest/services/Zoning/FloodZones_Public/MapServer/0)
is comparison-only: its thinner zone schema/date evidence must not silently replace
FEMA. A sample county X polygon has unknown panel/BFE/dates; X alone does not
establish a particular FEMA subtype or a lack of flood risk.

New bounded probes confirmed parcel layer WKID 103736 and polygon capability;
`01.013.1402` returned one polygon with five ring coordinates and recorded deeded
acres 20.0. No area was computed. The existing attribute pipeline intentionally
rejects `return_geometry=True`; it was not changed or used to publish a new run.
This sample is a separately dated observation, not a retroactive geometry/source
update to ML-130. Raw responses are retained separately as private discovery
evidence. Existing county data/year meanings and current-payment uncertainty remain
unchanged. No countywide polygon acquisition, overlays, legal boundary conclusion
or staff outreach occurred.
ML-125 now implements [strict input/schema checks](../validation.md), including
typed years, text-only parcel IDs, retained supporting evidence, and GIS row
quarantines. Historical import notes/results remain historical and unchanged;
ML-126 now implements [HTTP/completeness checks](../retrieval.md), including the
adapter's expected layer name and schema callback. No live refresh or original
result regeneration was performed. ML-127 implements [complete-run publication](../publication.md)
and shared reader checks for new inputs/results. Historical Isanti snapshots remain
legacy/unverified in status and are not automatically selected. Monetary-field and
unmatched-account questions still require county evidence.
