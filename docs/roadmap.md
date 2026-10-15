# Roadmap

Delivery is tracked in the [Kanban board](planning/kanban.md), with
[epics and detailed stories](planning/backlog.md) and a shared
[workflow and Definition of Done](planning/workflow.md). This roadmap defines
outcomes and sequence; the backlog owns actionable status and dependencies.

1. **County parcel/tax ingestion (complete):** Isanti source discovery, raw preservation, canonical normalization, guarded filtering, exports, and tests.
1.1. **Authoritative delinquency integration (current):** county year conventions and mixed prior/current population confirmed. Corrected import yields 62 large prior-year parcels, with ten sampled county reports corroborating prior-year status and acreage. Monetary aggregation and unmatched-account identities remain pending. Preserve separate overdue-current-year exports.
1.2. **Basic local review UI (planned):** snapshot selection, searchable parcel tables, source-linked detail views, and filtered exports for existing results. Select the technology during discovery; no UI has been implemented. This brings basic usability earlier while Phase 9 remains the full mapping/research application.
2. **GIS land suitability:** wetlands, floodplain, polygon analysis, estimated usable acreage. Do not begin until Phase 1.1 data is imported and validated.
3. **Access and terrain:** frontage, public-road access, elevation, slope, parcel shape.
4. **Planning/development screening:** zoning, lot size, subdivision, density, septic/soil screening; all preliminary.
5. **Ownership intelligence:** duration, absentee status, adjacent/common-owner parcels; no sensitive inferences.
6. **Comparable sales and economics:** eCRV, comparable sales, price/acre, valuation comparisons.
7. **Opportunity scoring:** transparent deterministic suitability, ownership, financial, and overall scores.
8. **PostGIS:** persistent spatial analysis when justified by scale.
9. **Web application:** map, filters, rankings, parcel details, visible sources.
10. **AI research layer:** ordinance summaries, anomaly review, due-diligence lists, explanations; never authoritative facts.
11. **Multi-county expansion:** prioritize adapters by source accessibility and investment strategy.

Gross acres, estimated usable acres, and legally buildable acres must always remain distinct.

Phases are epics, not single implementation tickets. Future epics begin with
source/requirements discovery and have explicit exit criteria in the backlog.
PostGIS remains conditional on measured need. County accounting questions block
verified financial comparisons, not all factual parcel review. No future-phase
implementation is started by adding it to this plan.

ML-119's [ingestion contracts and fixture matrix](ingestion-contracts.md) refine
the remaining Phase 1.1 reliability work into ML-125 (validation), ML-126
(retrieval/completeness), then ML-127 (complete-run publication). The discovery
does not itself implement those guarantees or expand county/GIS/UI scope.
