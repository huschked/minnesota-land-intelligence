# AGENTS.md

## Project Mission

This repository powers the Minnesota Land Intelligence Platform, which uses authoritative public data to identify and analyze Minnesota land acquisition opportunities. The current implementation may support only a subset of the eventual county, GIS, ownership, economics, scoring, and AI-assisted research capabilities. Read `docs/roadmap.md` before expanding scope.

## Core Engineering Principles

1. **Accuracy over coverage.** Never fabricate, infer, silently substitute, or guess missing property information. Unknown data remains unknown.
2. **Authoritative sources first.** Prefer official government structured APIs and downloads over HTML scraping.
3. **Preserve source lineage.** Important values must remain traceable to source agency, URL, layer, retrieval time, source field, raw value, and normalized value where practical.
4. **County isolation.** County schemas belong in county adapters; core code uses canonical models.
5. **Deterministic calculations.** Filtering, GIS, financial calculations, and scoring must be reproducible. Do not use an LLM for directly calculable facts.
6. **AI is advisory.** AI output must never silently become authoritative parcel data.
7. **No legal conclusions.** GIS and zoning results are preliminary screening and require verification.
8. **Do not infer personal circumstances.** Use only objective property and public-record signals.
9. **Respect public systems.** Do not bypass controls, CAPTCHAs, or rate limits. Use retries, caching, timeouts, and reasonable request rates.
10. **Preserve raw data.** Normalized data must not overwrite retained source responses.

### Delinquency Data

Tax delinquency must come from an authoritative delinquency-specific source or a field explicitly verified by authoritative documentation. Ambiguous parcel-GIS tax fields are not verified delinquency. Parcel and delinquency sources remain separate and independently traceable.

## Python Standards

Target modern Python. Use type hints, focused modules, descriptive names, dataclasses where appropriate, readable logging, and explicit exception handling. Avoid premature abstractions and unjustified dependencies.

## Testing Requirements

New ingestion or normalization work requires tests for mappings, null handling, conversions, filtering, pagination, and duplicate handling where relevant. Normal tests must not require a live government API. Run configured checks and report failures honestly.

## Documentation

Keep detailed architecture and source assumptions in `docs/architecture.md`, `docs/data-model.md`, `docs/data-sources.md`, `docs/roadmap.md`, and `docs/counties/`.

Track delivery in `docs/planning/backlog.md`; use its stable story IDs, acceptance
criteria, dependencies, and status. Follow `docs/planning/workflow.md` and regenerate
`docs/planning/kanban.md` after status changes. Future cards do not expand the
current milestone's authorized scope.

## Scope Discipline

Phase 1 does not include PostGIS, a map or web UI, wetlands, floodplain, zoning, terrain, comparable sales, scoring, AI agents, contact enrichment, or additional counties. Build extension points only where justified.

## Definition of Done

Work should be understandable, testable, documented, reproducible, traceable to authoritative sources, and explicit about unknowns.
