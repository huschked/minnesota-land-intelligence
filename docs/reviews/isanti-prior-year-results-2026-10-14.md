# Corrected Isanti prior-year delinquency screening

County Property Tax Coordinator correspondence establishes that this export mixes
unpaid prior-year taxes and overdue first-half current-year installments. Applying
the confirmed year convention supersedes the earlier blanket verification hold.

## Source and year mapping

- Original listing: `Delinquent Tax Listing 10-13-26.csv` supplied by the county.
- County evidence: `docs/counties/isanti-tax-year-confirmation.md`, copied and
  hashed with the reviewed mapping in the raw import snapshot.
- `TAXYR=2025`: report assessment year, taxes payable 2026.
- `ASMTYR`: individual charge assessment year; its payable year is ASMTYR + 1.
- `ASMTYR < TAXYR`: unpaid prior-year source row.
- `ASMTYR == TAXYR`: overdue first-half current-year row. Second-half taxes are
  excluded because the county says they are not late at the export date.
- Amount components and repeated-row balance structure remain unconfirmed.

## Corrected counts

| Measure | Count |
|---|---:|
| Total source rows | 1,783 |
| Prior-year unpaid rows | 523 |
| Prior-year distinct parcel IDs | 204 |
| Prior-year unique GIS matches | 203 |
| Prior-year matched parcels with at least 10 deeded acres | 62 |
| Prior-year large parcels outside PILT/exempt classifications | 49 |
| Prior-year large PILT/exempt parcels | 13 |
| Current-year overdue rows | 1,260 |
| Large parcels in the separate current-year view | 291 |
| Large parcels present in both views | 42 |
| All-source unmatched rows / IDs | 8 / 5 |

There is one unmatched prior-year parcel ID: `050080500`. It remains visible and
is not assigned acreage. The two missing GIS parcel IDs remain normalization errors.

The 49 parcels outside PILT/exempt classifications total 1,644.44 deeded acres,
with a median of 25 acres; 17 have at least 40 acres. These classifications do not
establish private ownership, purchase availability, access, usable acres, or buildability.

| Review view within the 49 parcels | Count |
|---|---:|
| Rural vacant/nonproductive classification | 8 |
| Other zero improvement value | 7 |
| Positive improvement value | 32 |
| Unknown improvement value | 2 |

The first two views yield a factual land-focused review set of 15 parcels.

## Multiple rows and monetary limits

31 of the 62 large prior-year parcels have one prior-year source row; 31 have
multiple rows. A confirmed unpaid prior-year row supports status even if it is
repeated. Every row remains preserved, and none of its amounts are summed.
Canonical delinquent balances remain null. No preferred source owner name is
selected from repeated owner rows; GIS ownership and all source names remain
independently traceable.

## Independent official-report sample

Ten reports were retrieved October 14 from the county's public ParcelReports
endpoint, preserved with hashes in
`data/raw/isanti/verification/2026-10-14T171054128230Z/`.

All ten agree on parcel identity and acreage and show a positive outstanding
balance for at least one listed prior taxes-payable year. Some older listed years
are outside the reports' six-year taxation window and remain unverified by that
window. This validates the year interpretation and sampled prior-year status,
not every individual amount or all 62 current balances. Two taxation pages were
also rendered and visually checked; all ten table comparisons were checked by
year-header-aware extraction.

Comparison CSV:
`data/processed/isanti/delinquency/2026-10-14T170022005639Z/review/2026-10-14T170919281292Z/isanti_official_report_comparison.csv`.

## Outputs

Corrected import:
`data/processed/isanti/delinquency/2026-10-14T170022005639Z/`.

- `isanti_verified_delinquent_candidates.csv` and JSON: 62 prior-year large parcels.
- `isanti_overdue_current_year_parcels.csv` and JSON: 291 large current-year parcels.
- `isanti_duplicate_delinquency_records.csv`: all repeated source rows with period labels.
- `isanti_unmatched_delinquency_records.csv`: unmatched rows with period labels.

Current review directory:
`data/processed/isanti/delinquency/2026-10-14T170022005639Z/review/2026-10-14T171422882320Z/`.

- `isanti_land_review.csv`: 49 outside PILT/exempt classifications.
- `isanti_land_focused_review.csv`: 15 rural-vacant or zero-improvement parcels.
- `isanti_PILT_exempt_review.csv`: 13 special-classification parcels.
- `isanti_county_verification_worklist.csv`: ten deterministic sample records.

## Next step

Review the 15 land-focused parcels and the county's forthcoming monetary-field
explanation. Screening by confirmed prior-year status is available now; financial
comparisons must await balance definitions. Phase 2 GIS work has not begun.
