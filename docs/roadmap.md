# Roadmap

Delivery is tracked in the [Kanban board](planning/kanban.md), with
[epics and detailed stories](planning/backlog.md) and a shared
[workflow and Definition of Done](planning/workflow.md). This roadmap defines
outcomes and sequence; the backlog owns actionable status and dependencies.

The ultimate outcome is a source-traceable shortlist of delinquent-tax land worth
further property research, due diligence and possible offers/acquisition/holding
or resale. Delinquency is a lead signal, not proof of availability, a bargain or
profit. Mapped-constraint screening is implemented; full suitability, economics
and scoring are not existing investment conclusions.

1. **County parcel/tax ingestion (complete):** Isanti source discovery, raw preservation, canonical normalization, guarded filtering, exports, and tests.
1.1. **Authoritative delinquency integration (current):** county year conventions and mixed prior/current population confirmed. Corrected import yields 62 large prior-year parcels, with ten sampled county reports corroborating prior-year status and acreage. Monetary aggregation and unmatched-account identities remain pending. Preserve separate overdue-current-year exports.
1.2. **Basic local review UI (complete, bounded local release):** ML-202–206 deliver [the read-only local viewer](viewer.md) with optional Streamlit 1.66.0, explicit validated snapshot loading, dates/counts/holds/unknowns, searchable/filterable parcel tables, deterministic pagination, keyboard parcel selection, revalidated source-evidence details/links and [contextual CSV/JSON worklists](worklist-exports.md) with separate issues. [ML-130 prepared actual eligible data](reviews/isanti-viewer-preparation-2026-10-16.md) using fresh October 16 GIS plus the unchanged October 13 listing. [ML-206 release checks](reviews/local-viewer-release-2026-10-17.md) cover fresh installation, real-data keyboard/download/refusal workflows, clipboard and user-confirmed 200% zoom; they are not accessibility certification or public deployment. Phase 9 remains the full mapping/research application.
2. **GIS land suitability (complete, bounded mapped-constraint release):** [ML-301](suitability-sources.md) selects authoritative sources; [ML-302](geometry.md) provides pinned polygons/CRS/area controls. [ML-303](wetlands.md) yields 15 focused mapped-wetland observations with separate imagery/project dates. [ML-304](floods.md) adds effective FEMA SFHA/floodway/X-category screening, independent study/panel/zone coverage and spatial dates. [ML-305](constraints.md) combines mapped-water/SFHA without double subtraction. [ML-306](suitability.md) reviews representative official maps and all held panel contexts, publishes canonical CSV/JSON, and integrates explicitly selected evidence into the local table/details/downloads. Nine records are numeric; six conservative holds stay null after review, not invented zeros or absent Isanti coverage. All 5,778 baseline files remain unchanged; taxes/analytical sources were not refreshed. [Verification](testing.md#ml-306-suitability-validation-and-publication) records 1,193 offline tests on each Linux version, local Windows checks, cancelled slow hosted Windows jobs and native browser-delivery limits. No legal buildability, insurance, investment rank or public map application is established. County accounting still blocks verified financial analysis.
3. **Access and terrain (next: ML-401 source discovery, Ready/not started):** frontage, public-road access, elevation, slope, parcel shape. Discovery must distinguish physical proximity from legal access and document road/DEM dates, coverage, CRS and units before implementation. No future card starts automatically.
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
the Phase 1.1 reliability work into ML-125 ([validation, now implemented](validation.md)),
ML-126 ([retrieval/completeness, implemented](retrieval.md)), and ML-127
([complete-run publication, implemented](publication.md)). None expands county/GIS/UI
scope or tax meanings. ML-123 adds [explicit selected-snapshot/portable replay](replay.md)
for completed version-2 inputs; historical pre-completion runs are not retroactively
certified, converted or reimported by these reliability changes.
ML-124's [saved snapshot comparison](snapshot-comparison.md) adds dated
added/changed/missing reports and explicit stale-data policy without treating
disappearance as payment, inferring parcel replacement links or retrieving data.
