# Draft county clarification request

Subject: Clarification of Delinquent Tax Listing 10-13-26.csv

Thank you for providing the listing. We are comparing its parcel identifiers,
tax-year fields, and balances with the county's public parcel reports before
using it for land research. Could you clarify the following?

1. Does `TAXYR=2025` mean taxes payable in 2025, assessment year 2025 with
   taxes payable in 2026, or another accounting period? What does `ASMTYR` mean?
2. Is this a list of unpaid prior-year delinquent balances, unpaid current-year
   installments, historical charges, or another population? Were paid records
   excluded? What date are balances effective as of, given `EFFDATE` and `LTRDT`
   are `7-Oct-26` but the filename is dated October 13?
3. Please define `TAXAMT`, `TAXONLYAMT`, `SPAAMT`, `PENAMT`, `INTAMT`, `FEEAMT`,
   `TOTAMT`, `PENAMT2`, `INTAMT2`, and `TOTAMT2`. Does `TOTAMT` represent an
   outstanding balance after payments, and does it include special assessments?
4. Why can one `PARID` have multiple rows for the same year, often with different
   owners or mailing addresses? Are these owner-history joins, separate charges,
   or something else? What identifier makes a charge unique, and when, if ever,
   should amounts be combined?
5. Could you explain these example differences? County reports were retrieved
   October 14, 2026 and show the following:

| Parcel | Listing TAXYR | Listing TOTAMT | Report 2025 outstanding | Report 2026 outstanding |
|---|---:|---:|---:|---:|
| 01.003.1300 | 2025 | $574.56 | $0.00 | $1,067.04 |
| 01.007.0100 | 2025 | $83.16 | $0.00 | $157.08 |
| 01.124.0401 | 2025 | $177.12 | $0.00 | $334.56 |
| 04.003.0101 | 2025 | $412.08 | $403.01 | $95.83 |

6. Five listing IDs appear in the public `TaxDistribution_Public` table but not
   in the public parcel polygon or point layers: `05.008.0500`, `13.024.0105`,
   `06.609.0010`, `12.609.0010`, and `13.609.0010`. Are these retired, split,
   special-account, or other identifiers? Where can their current parcel identity
   and deeded acreage be verified?
7. Should PILT/exempt-property entries be interpreted differently from ordinary
   property-tax delinquency? Which public county source should be used to confirm
   a parcel's current delinquent balance?

A data dictionary or export specification would be especially helpful. We can
provide the ten-report comparison and original listing-row references if useful.

This is a draft for the user to send; no message has been sent to the county.
