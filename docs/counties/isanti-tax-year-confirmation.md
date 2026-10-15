# Isanti county confirmation of the October 13 export

## Source evidence

Kasey Gilly, Property Tax Coordinator, Isanti County Finance & Property Services
Division, replied on October 14, 2026. The original email was supplied by the
user and is preserved in `data/raw/isanti/correspondence/2026-10-14-county-confirmation/initial-reply.eml`.
Its screenshot shows `TAXYR=2025` on every row and different `ASMTYR` values
for the individual charges.

Her initial reply states:

> Our new tax program is based on assessment year.
> TAXYR is assessment year, therefore taxes payable for 2026.
> ASMTYR heading needs to be corrected from what I can see.

She explains the screenshot's assessment-year 2023 charge as payable in 2024
and becoming delinquent in 2025, and the 2022 charge as payable in 2023 and
becoming delinquent in 2024.

The user subsequently supplied this follow-up reply text (original send time
not supplied):

> Hi Daniel,
> It includes all prior years un-paid taxes as well as current year taxes. In the screenshot below if you look at the bottom row that is the amount owing for first half taxes 2026. It does not include the second half yet because they are not late yet. TAXYR on this report is the assessment year for property taxes payable 2026.
>
> Hope this helps!

## Interpretation accepted for this export

- `TAXYR` is the report assessment year: 2025 corresponds to payable 2026.
- `ASMTYR` is the individual charge assessment year, as illustrated by the
  screenshot and its explanation. The misleading heading is retained verbatim
  in raw input; the canonical field is `assessment_year`.
- Individual taxes-payable year = individual assessment year + 1.
- A charge with `ASMTYR < TAXYR` is a listed unpaid prior-year charge.
- A charge with `ASMTYR == TAXYR` is an overdue first-half current-year charge.
- Missing, malformed, or future row years fail validation; no status is guessed.

The earlier zero-2025 comparison was made against the wrong payable-year column.
It does not establish that the listing conflicts with the county reports. The
source-wide year hold is superseded by this county explanation. The presence of
an unpaid prior-year charge may be used for parcel status independently of an
aggregate monetary balance.

## Limits that remain

The accounting definitions of monetary columns and the reason for repeated
owner/charge rows remain unresolved. No balances are summed. All source rows,
original names, monetary strings, and source-row references remain retained.
Canonical monetary amounts stay unknown for this mapping. Current-year overdue
installments are exported separately from prior-year delinquency, and absence
from either view does not mean paid/current. Status describes the supplied
snapshot, not a guarantee of an unpaid balance at a future date.
