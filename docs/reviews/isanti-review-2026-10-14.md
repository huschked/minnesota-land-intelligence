# Isanti Phase 1.1 review - October 14, 2026

**Historical review, superseded by county clarification.** The eight zero-2025
findings compared report assessment year to the wrong taxes-payable year. The
county subsequently clarified the year convention and mixed source population.
See `isanti-prior-year-results-2026-10-14.md` for corrected results. The accounting
and duplicate-balance questions remain valid; the blanket year hold is lifted.

## Outcome

**HOLD: the supplied listing must be reconciled with current official reports
before records are presented as confirmed delinquent acquisition candidates.**

The earlier 164 "verified" candidates were exact matches to the supplied listing.
That was not sufficient to establish current delinquency. Original imports are
preserved; the revised mapping holds all matched records as unverified.

## Independent county-report check

Ten official parcel reports were downloaded directly from the county's
`https://gis.co.isanti.mn.us/ParcelReports/PublicParcelReport.ashx?PIN=<parcel-id>`
endpoint. Original PDFs and SHA-256 hashes were retained in
`data/raw/isanti/verification/2026-10-14T144713278440Z/`.

All ten parcel IDs and deeded-acreage values match the GIS inputs. GIS owner
text appears in all ten reports. However, eight reports show $0 outstanding
under **2025 Payable**, despite positive `TOTAMT` and `TAXYR=2025` in the listing.
The remaining two are PILT parcels with positive 2025 outstanding balances that
also differ from the listing amounts. These comparisons do not establish that
either source is erroneous or that any unexamined parcel is current.

The reports' year-column headers were checked during text extraction. Rendered
pages for 01.003.1300 and 04.003.0101 were also inspected visually. The ten-report
comparison is retained under the review directory listed below; this is an
evidence check, not a claim that every parcel was manually verified.

For example, 01.003.1300 shows 17.50 acres in both sources, $574.56 in listing
`TOTAMT`, and $0.00 outstanding for 2025 in its October 14 county report. Its
2026 outstanding amount is $1,067.04. Assessment-year versus payable-year
conventions are a possible explanation requiring county confirmation.

Seven sampled parcels have non-null GIS assessed values. Those amounts align
with the reports' **2025 Values** EMV totals, not necessarily the newer **2026
Values**. Three have unknown 2025 GIS valuations, which remain unknown. No
updated valuation was silently substituted.

## Land review views

The original 164 large-parcel listing matches were assigned to mutually
exclusive review groups. These are factual review views, not opportunity scores:

| Review group | Parcels |
|---|---:|
| PILT/exempt | 15 |
| Rural vacant/nonproductive classification | 25 |
| Other zero improvement value | 67 |
| Positive improvement value | 53 |
| Unknown improvement value | 4 |

The 149 records outside PILT/exempt classifications form a land-review view.
They are not presumed privately owned, available for sale, or currently delinquent.

## Duplicate and unmatched diagnostics

- 420 repeated parcel-ID groups are retained.
- 253 groups have identical fiscal values; 167 have differing fiscal values.
- No amounts were added and no owner-history row was selected arbitrarily.
- 147 additional large parcels remain ambiguous.
- Eight unmatched rows represent five distinct IDs. All five IDs were found by
  exact formatted-ID queries in `TaxDistribution_Public` (FeatureServer table 1).
  None was found in the parcel polygon layer, parcel point layer, or personal
  property layer queried. Tax-distribution records do not establish deeded acreage,
  so these records remain unmatched to GIS parcels.

## Artifacts

Review directory:
`data/processed/isanti/delinquency/2026-10-14T143019768539Z/review/2026-10-14T145511653574Z/`

- `isanti_candidate_review.csv`: all original 164 large-parcel listing matches.
- `isanti_land_review.csv`: 149 outside PILT/exempt classifications.
- `isanti_PILT_exempt_review.csv`: 15 special-classification records.
- `isanti_duplicate_group_review.csv`: all 420 groups and fiscal-pattern diagnostics.
- `isanti_unmatched_parcel_review.csv`: five IDs with original row references.

The ten-report evidence comparison (`isanti_official_report_comparison.csv` and
`official_report_comparison.json`) remains in the preceding review directory,
`data/processed/isanti/delinquency/2026-10-14T143019768539Z/review/2026-10-14T144455141758Z/`.

The latest review views explicitly label every record as held for county
reconciliation. Earlier views remain historical artifacts. The county-report
comparison and revised mapping supersede their pending verification labels.

The corrected import is
`data/processed/isanti/delinquency/2026-10-14T145422464512Z/`. It retains 447
exact identity matches, of which 164 meet the acreage threshold, as unverified.
Verified-candidate outputs are empty. This does not mean Isanti has no delinquent
large parcels; it means this source has not yet been reconciled. The original
164-match output remains preserved for auditing.

Validation: all 48 tests passed, including the live GIS integration test and
regressions for exact-match retention under a hold, unknown-value handling,
snapshot selection, and review labels. Ruff passed.

## Next dependency

Send the accompanying draft `isanti-county-questions-2026-10-14.md` to the county
contact who supplied the listing. No outreach has been sent by this application.
The needed response concerns year conventions, current versus historical
balances, duplicate-row structure, and unmatched account identities. Keep Phase 2
on hold until the source is reconciled.
