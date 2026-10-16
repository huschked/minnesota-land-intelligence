# Isanti County

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
ML-125 now implements [strict input/schema checks](../validation.md), including
typed years, text-only parcel IDs, retained supporting evidence, and GIS row
quarantines. Historical import notes/results remain historical and unchanged;
ML-126 now implements [HTTP/completeness checks](../retrieval.md), including the
adapter's expected layer name and schema callback. No live refresh or original
result regeneration was performed. Complete-run publication remains ML-127 work.
