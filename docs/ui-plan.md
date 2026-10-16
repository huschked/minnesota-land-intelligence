# Local land-review viewer decision (ML-201)

Decision date: 2026-10-16. **Discovery complete; no UI is implemented or installed.**

## Outcome and user

The product ultimately turns authoritative delinquency data into land acquisition
research: evaluate property facts, then future suitability/economics to decide which
parcels merit due diligence and possible offers, purchase, holding or resale.
This milestone makes the existing evidence usable; it does not decide what to buy.
Delinquency does not prove a bargain, availability, owner motivation or profit.

Assumptions: one researcher, this Windows computer, local browser, read-only saved
results, no accounts or collaboration. These are implementation defaults, not a
new user interview or a promise of public hosting. The main action is:
**choose dated evidence -> narrow a research view -> inspect a parcel -> export
a contextual worklist**. Notes/outreach, persistent research decisions, maps,
scores, valuation, profit calculations and AI recommendations are not added here.

## Technology decision

Select **Streamlit** for Phase 1.2, with an optional `ui` dependency group added
only during implementation. Keep the CLI/core usable without that extra.
Python data-table interaction and row-selection APIs are documented in
[Streamlit's dataframe reference](https://docs.streamlit.io/develop/api-reference/data/st.dataframe).
That supports a small local viewer; it does not establish that our app is accessible
or production-ready. This suitability choice is engineering judgment, not a benchmark.

| Option | Fit for this milestone | Decision |
|---|---|---|
| Streamlit | Reuses Python service/model logic; built-in widgets/table; adds a runtime dependency and rerun/state concerns. | Selected for the small local viewer, subject to implementation gates below. |
| FastAPI + templates/custom browser table | More direct HTML/accessibility control, but requires routes, templates and browser interaction work for this same slice. | Reserve for a later need that justifies the extra surface. |
| Continue CSV/manual commands | No new stack; retains current friction and does not deliver the table-to-detail workflow. | Keep as recovery/inspection fallback, not the viewer solution. |

The custom-template alternative is technically supported by
[FastAPI's template documentation](https://fastapi.tiangolo.com/advanced/templates/);
the relative engineering effort above is our assessment, not a framework claim.
Official Streamlit reference pages displayed version 1.66.0 during discovery.
The skill discovery script found **no installed Streamlit in this project's venv**;
version-matched bundled guidance could not be loaded, so official web references
were used. No package was installed. ML-202 must resolve/pin a compatible version,
read its installed guidance, and test Python 3.11/3.12 and Windows startup. The
currently documented APIs/configuration are not assumed available in every version.

## Data readiness is a separate gate

A read-only CLI status check on this date found **no eligible complete version-2
county run**. The original two parcel acquisitions and five file/join imports are
historical/legacy evidence, not silently selectable completed inputs. The historical
[Isanti review](reviews/isanti-prior-year-results-2026-10-14.md) documents the 15-,
49- and 62-parcel views; those counts are examples, not live totals or UI constants.

Choose a strict viewer boundary: load completed join/review graphs using existing
validation. List legacy/incomplete/failed entries with a reason, but disable viewing
them as validated candidates. Do not add a force flag, create missing inventories,
backfill completion markers, or treat source-year confirmation as technical completion.
If nothing is eligible, explain the state and link to preparation instructions;
show no fabricated zero-result success and no real-looking sample data by default.
Synthetic demonstrations, if used for testing, must say **Synthetic test data**.

New **ML-130** prepares actual usable inputs via a reviewed recovery/reacquisition
route. It is not performed by this discovery or by a UI interaction. Preserve
historical bytes/results and separate old file publication date, new capture date,
and GIS date; use only genuinely obtained current-protocol evidence. New counts may
differ from historical counts and must not be forced to match. ML-202 can develop
against sanitized fixtures independently; ML-206 cannot claim real-data usability
until ML-130 supplies eligible actual results. See [replay boundaries](replay.md).

**Subsequent ML-130 handoff on 2026-10-16:** [actual preparation evidence](reviews/isanti-viewer-preparation-2026-10-16.md)
records a successful fresh official GIS acquisition, exact October 13 file
recapture, join and review with valid version-2 source graphs. The actual
62/49/15 view IDs match the historical sets, but amounts remain unknown and new
manual report verification is pending. Use the documented explicit run IDs and
revalidate on load. The initial discovery status above remains a dated finding;
historical runs were not certified. This does not install or implement a UI.

## Primary workflow and layout

The layout below is a planning wireframe, not a screenshot or implemented app:

```text
Land research review                 [Reload local snapshots]
[Saved result: ID, kind, source dates]   Completion checked at ...
[Holds / old or mismatched dates / unknown balances / limitations]
[View] [Search] [Acreage] [Classification] [Improvement state] [Sort]
Research table: parcel ID | deeded acres | class | tax period | warnings
[Parcel ID selector] [Open parcel details]       [Clear filters]
Parcel details: facts -> source years/rows -> holds -> official references
[Export filtered worklist + context]     [Validation and unmatched issues]
```

1. **Select saved evidence.** Show ID, join/review kind, listing publication and
   capture dates, GIS acquisition date, completion state and validation warnings.
   Require an explicit choose/load action, never a hidden latest switch.
   Reload scans local files only. A newer result does not replace a selected one
   during filtering. Changing snapshots clears incompatible filters/selection.
2. **Choose a view.** Default to land-focused prior-year research; permit broader
   context and separate current-year/held/issue views. Compute counts from the chosen
   result, not the historical report. Keep holds and date limitations above the table.
3. **Filter and sort.** Search parcel IDs and displayed property/owner text; numeric
   acreage bounds, classification, improvement known/unknown/zero, and period.
   Preserve identifier strings/leading zeros. Empty values remain unknown, not zero.
   Use Decimal-backed service filters/numeric ordering, with explicit null placement
   and parcel-ID tie-breaks; UI formatting must not change canonical values.
4. **Open details.** A labelled parcel selector plus an explicit button is the
   primary keyboard path. Optional table selection is a shortcut, not the only path.
   Store `(county, snapshot ID, parcel ID)`, not a row index; sorting/filtering cannot
   open the wrong parcel. If a selection is filtered out, clear it with an explanation.
   Returning to results retains the current snapshot/filters.
5. **Inspect evidence.** Show deeded acres (not usable/buildable acres), classification,
   improvement/assessment values, independent GIS and listing owner texts, status,
   assessment/payable years, all supporting source rows and active holds. Unknown
   monetary totals stay unknown; uninterpreted source amounts are separately labelled
   raw observations, never summed or promoted to canonical debt. Sample corroboration
   applies only to the sampled parcel/years, never every parcel or current balances.
6. **Export for further research.** Explicitly choose filtered or selected records.
   Preview count, deterministic service sort, filters, snapshot IDs/hashes, source
   dates and warnings. This is not an offer list or an automatic owner-contact action.
   Unknowns remain explicit; CSV formula protection is a presentation transformation,
   not a source rewrite. Exports never mutate retained outputs or latest pointers.

### View meanings, not fixed counts

| View | Definition | Historical example only |
|---|---|---:|
| Land-focused prior-year | Within the outside-PILT/exempt prior-year view, rural vacant/nonproductive classification or other zero improvement value. Not verified vacant/buildable. | 15 |
| Outside PILT/exempt | Prior-year large parcels excluding the two reviewed special classifications. Not proof of private ownership or availability. | 49 |
| All prior-year large parcels | Listed prior-year unpaid status, with at least the imported acreage threshold; includes special classifications. | 62 |
| PILT/exempt review | Special classifications retained visibly, not erased or assumed purchasable. | 13 |
| Current-year overdue | Separate current-year installment evidence, not additional prior-year delinquency. | 291 |

The first view is a subset of the second, which is a subset of the third. The
historical prior/current intersection is 42; do not add their counts to claim a
unique-parcel total. Count distinct identities within each view. Held/unverified,
unmatched and ambiguous rows remain inspectable in clearly separated issue views.
UI classification logic must reuse the county review service, not reinterpret
raw Isanti field names inside widgets. Filters cannot request records below an
imported candidate threshold without separately reprocessing retained inputs.

## Thin service and execution boundary

Plan a framework-independent review service and a thin Streamlit entry point
(proposed paths: `src/mn_land/review_service.py`, `src/mn_land/ui/app.py`; not created).
The service validates selected join/review snapshots through `validate_run`, follows
their pinned references, exposes allowlisted canonical display DTOs, and owns
deterministic views/filtering/details/export context. Widgets do not normalize
county fields, calculate balances, acquire data, or invoke replay. Existing CLI
acquisition/replay remains an explicit operator workflow outside this viewer.

Streamlit reruns on interaction and its caches can share values across sessions;
[its execution/caching documentation](https://docs.streamlit.io/develop/concepts/architecture/caching)
explains why state needs deliberate handling. Keep a selected validated in-memory
DTO with its validation time in session state; never persist a trusted-validation
boolean/cache keyed only by path/mtime. Revalidate on load/reload, before any new
disk-backed detail read, and before export. If evidence changed, invalidate the
view and require a new selection. Pure in-memory filtering must not reread mutable
originals, reimport data, rewrite outputs or contact the county. Avoid persistent
pickle caches and global mutable parcel data in this first slice.

Local deployment policy: bind `server.address` to `127.0.0.1`, disable usage telemetry
and the email prompt, retain CORS/XSRF protections, keep static file serving off,
and use bundled/system assets without remote fonts or tiles. Configuration controls
exist in [Streamlit's configuration reference](https://docs.streamlit.io/develop/api-reference/configuration/config.toml);
ML-202/206 must verify the selected version's behavior. These settings are not
authentication or protection from another local account/browser. No LAN/public bind,
cloud deployment, data upload, credentials or open-source exposure is introduced.

Only allowlisted display fields are sent to the grid; hiding a column is not
redaction. Do not serve raw data directories, email attachments or arbitrary local
paths. Render untrusted source text escaped, with no unsafe HTML. Disable built-in
grid export/copy controls where supported so they do not bypass contextual/formula-
safe exports; this is a UX guard, not data access control. External county URLs must
pass scheme/host/path checks and open only on an explicit user click, with a notice
that the external record may be newer. No embedded or background county requests.
If the selected version cannot disable bypassing export controls, use a compatible
version or a controlled table renderer before release; do not waive export safety.

## Accessibility and validation gates

Use visible labels, logical headings, text warnings (not red/green alone), visible
focus, keyboard-reachable controls, no hover-only facts and a labelled detail path
outside the grid. Streamlit explicitly advises against empty selectbox labels in
[its widget reference](https://docs.streamlit.io/develop/api-reference/widgets/st.selectbox).
Target readable desktop layouts and 200% browser zoom with contained table scrolling;
stack details when space narrows. Keyboard/screen-reader and contrast checks follow
[WCAG 2.2 guidance](https://www.w3.org/WAI/WCAG22/quickref/), but no conformance is
claimed without testing. If essential flows fail, use a simpler native table/detail
rendering or revisit the framework rather than bypass the accessibility gate.

[AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest)
provides simulated widget testing, including selectboxes. Use it with sanitized
fixtures for supported controls; it is not a browser, screen-reader audit, or proof
that every grid interaction works. Retain actual Windows/browser keyboard/zoom
checks in ML-206. Keep service tests independent of UI dependencies and use ML-129's
targeted-development/full-regression policy; no artificial unit tests for this plan.

### Acceptance examples to carry into implementation

| ID | Example and expected outcome | Delivery |
|---|---|---|
| U01 | No eligible run, but historical files exist: explain legacy state, no fake zero results or forced completion. | ML-202, ML-130 |
| U02 | Valid result selected: all facts/details/export retain its IDs, source dates and warnings despite newer local runs. | ML-202 |
| U03 | Valid empty candidates differs from missing/corrupt/failed/unsupported input; errors never fall back silently. | ML-202 |
| U04 | Change filter/sort, choose a parcel and return: correct identity, nulls, numeric boundaries and current filters are preserved. | ML-203, ML-204 |
| U05 | Prior/current overlap, source hold or repeated fiscal rows: no additive parcel total, false verification or computed debt. | ML-203, ML-204 |
| U06 | Unknown access/usable acres/zoning/resale value/profit: show not assessed, not a green opportunity score or zero risk. | ML-204 |
| U07 | Malicious URL/source markup/formula-leading text: no script execution, arbitrary local serving or unsafe worklist export; raw evidence unchanged. | ML-204, ML-205 |
| U08 | Files change after load: reload/new disk reads/export revalidate and fail visibly; no stale cache presented as newly verified. | ML-202, ML-205 |
| U09 | Keyboard-only parcel selection, visible focus, readable 200% zoom and clear unknown/hold labels work on Windows. | ML-206 |
| U10 | Browser grid sorting/export shortcut cannot change parcel identity or bypass declared export filters/context. | ML-203, ML-205 |
| U11 | Local browsing/filtering makes no county requests; opening a validated external link is an explicit browser action. | ML-202, ML-206 |
| U12 | Actual newly eligible inputs can be selected; counts are computed, not forced to the historical 15/49/62. | ML-130, ML-206 |

## Bounded handoff and remaining uncertainty

ML-202 creates the service boundary, optional tested UI dependency/entry shell,
selector, validation/error states and fixture tests. ML-203 adds table/filters;
ML-204 details/evidence; ML-205 safe contextual exports; ML-206 packages and checks
the actual Windows workflow. ML-130 independently prepares real eligible data;
ML-124 checks refresh/difference semantics. None of these cards is implemented by
this discovery, and no live acquisition/reimport is authorized merely by adding one.

Unknown until implementation: compatible resolved dependency footprint, measured
startup/load latency, selected-version grid export controls and browser accessibility.
Revisit Streamlit if those gates fail, or when real multi-user/hosted/map requirements
justify a different frontend. Local-first service isolation limits that later rewrite.
