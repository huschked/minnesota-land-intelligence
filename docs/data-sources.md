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
planned field/type gates, service limits/retry/completeness rules, file constraints,
and partial-run policy. Those hardening rules are specified, not yet implemented.
