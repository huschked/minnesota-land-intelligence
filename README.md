# Minnesota Land Intelligence Platform

Track work in the [Kanban board](docs/planning/kanban.md). Its
[epic/story backlog](docs/planning/backlog.md) contains acceptance criteria,
dependencies, priorities, and evidence; the [workflow](docs/planning/workflow.md)
explains status updates. The [roadmap](docs/roadmap.md) remains the phase overview.

**Current result: county-confirmed year conventions applied.** The export mixes
unpaid prior-year taxes and overdue first-half current-year installments. The
corrected import produces 62 prior-year delinquency parcels of at least 10 acres,
including 49 outside PILT/exempt classifications. The separate current-year view
has 291 large parcels and overlaps the prior-year view by 42 parcels. Ten sampled
prior-year parcel reports corroborate outstanding prior-year balances and acreage.
See `docs/reviews/isanti-prior-year-results-2026-10-14.md`. Monetary components
and repeated-row balance totals remain unresolved and are not aggregated.

Phase 1 is a conservative command-line pipeline for the official Isanti County parcel service. It retrieves paginated records, preserves immutable run artifacts, normalizes county fields, applies a separate candidate filter, and exports CSV/JSON.

Phase 1.1 adds a separate authoritative delinquency-file importer. Delinquency status never comes from the parcel GIS unless its semantics are independently verified.

ML-126 adds [respectful HTTP and source-completeness checks](docs/retrieval.md):
bounded paced retries, retained response evidence, and initial/final count, ID and
schema reconciliation. ML-127 adds [complete-run publication and shared reader
validation](docs/publication.md), with immutable per-run outputs and pinned inputs.
Historical snapshots remain legacy/unverified and are not automatically selected;
they are not deleted or backfilled. ML-123 adds [explicit snapshot selection and
offline replay](docs/replay.md) for completed version-2 inputs, not legacy migration.

The county service describes `TOTPRVTXTOD` only as **Total Previous Taxes Owed**. That does not by itself prove delinquent/past-due status, so strict candidate classification is intentionally disabled until an authoritative definition is documented. The pipeline still preserves that source value as `previous_taxes_owed` and reports the semantic gate clearly.

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate
python -m pip install -e ".[dev]" -c constraints-dev.txt
```

The recorded dependency resolution targets Windows x64 / Python 3.12.14.
See [reproducibility and recovery](docs/reproducibility.md) for PowerShell setup,
offline verification, run identity, and the separate backup needed for ignored data.

## Commands

```bash
mn-land validate-source --county isanti
mn-land status --county isanti
mn-land find-candidates --county isanti --min-acres 10
python -m mn_land.cli find-candidates --county isanti --min-acres 10
python -m mn_land.cli inspect-delinquency-file --county isanti --file data/import/county-file.xlsx
python -m mn_land.cli import-delinquency --county isanti --file data/import/county-file.xlsx --mapping reviewed-mapping.json --min-acres 10
python -m mn_land.cli replay-delinquency --county isanti --snapshot data/processed/isanti/delinquency/COMPLETE_RUN_ID
python -m mn_land.cli review-delinquency --county isanti --snapshot data/processed/isanti/delinquency/COMPLETE_RUN_ID --min-acres 10
pytest
pytest -m integration
```

## Tests and GitHub checks

`python -m pytest` runs offline tests by default. Ordinary tests block DNS and TCP
connections, and unknown markers fail collection. Use mocked transports and
sanitized fixtures for normal tests; deliberately live tests must carry the
`integration` marker.

`python -m pytest -m integration` explicitly runs live government-service tests.
To verify that selection without contacting the service, use
`python -m pytest -m integration --collect-only -q`.

[GitHub Actions](.github/workflows/ci.yml) runs lint, dependency checks, board
validation, and offline tests on pushes and pull requests, with a manual trigger
also available. Code changes use the full Windows/Linux x Python 3.11/3.12 matrix;
documentation-only completion updates use Linux-only fast CI. CI only
collects the live tests; it never executes them. It uses no county files or custom
secrets, and does not deploy the application. See [testing](docs/testing.md).

[Strict input validation](docs/validation.md) rejects malformed mappings, unsafe
evidence paths, non-finite values, numeric parcel-ID cells, ragged CSV rows, and
ambiguous/formula-bearing workbooks. It preserves source row/sheet locations and
GIS quarantine diagnostics. Existing county snapshots/results are not regenerated.

Raw responses are written to `data/raw/isanti/<run-id>/`; processed artifacts go to `data/processed/`. These generated files are ignored by Git.

When strict classification is gated, `isanti_tax_semantics_review_sample.csv` contains up to ten deterministic examples labeled **NOT A CANDIDATE**. It exists only to help a human ask the county what the source field means. The required candidate verification sample remains empty when there are no verified candidates.

Delinquency inspection reports columns and cautious potential mappings but never auto-accepts them. Copy and review `docs/examples/isanti-delinquency-mapping.example.json`; remove unavailable optional fields and replace every placeholder. Import preserves source/mapping/supporting bytes in an immutable UUID raw snapshot and joins against the latest eligible complete parcel acquisition, or the explicit `--parcel-snapshot`. New UUID processed results retain candidate/issue exports, source dates and reproducibility evidence. Replay reads completed retained inputs without a new raw capture or government request.

The October 13 county listing uses the reviewed mapping in
`docs/counties/isanti-delinquency-2026-10-13.mapping.json`, with supporting county
correspondence documented and copied into the raw snapshot. Candidate JSON retains
every supporting prior-year row and its metadata. Multiple authoritative rows may
establish unpaid prior-year status without establishing an additive balance.
Generic sources with unresolved duplicate semantics still remain ambiguous.

## Trust boundary

The output is acquisition-screening data, not a title, tax, legal, zoning, or buildability determination. Review `docs/counties/isanti.md` before interpreting tax values.
