# Local parcel research viewer (ML-202/203/204/205)

The read-only UI selects a completed join or review, validates its full pinned
graph, and shows source identities, dates, counts, holds and unknowns. ML-203 adds
candidate tables, filters, pagination and a labelled keyboard parcel selector.
ML-204 adds revalidated source-evidence details/links; ML-205 adds contextual
CSV/JSON worklists with explicit preview and click-time validation. Final browser/
accessibility release checks (ML-206) remain unfinished. This viewer is
not a land acquisition recommendation.

## Install and run locally

From the repository root, in a project virtual environment with pip:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,ui]" -c constraints-dev.txt
.\.venv\Scripts\python.exe -m mn_land.ui.launcher
```

Or use the installed `mn-land-viewer` console command. The only launcher option is
`--port 8502` (an integer from 1 through 65535). The supported launcher forces
`127.0.0.1` and does not forward arbitrary Streamlit flags. Open
[the local viewer](http://127.0.0.1:8501) explicitly. Stop a foreground launch with
Ctrl+C. If the port is occupied, choose another port; do not kill another app.

On this workspace the venv originally had no pip module; installation used the
bundled pip's `--python .venv/Scripts/python.exe` option to target this venv, not
the bundled dependency environment. No system package directory was modified.

The optional extra pins **Streamlit 1.66.0**, supporting Python 3.11+. Its sizable
transitive stack includes NumPy, pandas, PyArrow, Altair and ASGI/server packages;
none becomes a base CLI requirement. NumPy resolution can differ on Python 3.11
and 3.12 because current releases have different Python minimums. This is a direct
framework pin plus the existing development constraints, not a transitive/hash
lock or a guarantee that future package-index resolutions are identical.
The [upstream release notes](https://docs.streamlit.io/develop/quick-reference/release-notes)
and installed version-matched skill/docs informed the choice. Platform/version
verification is recorded in [testing evidence](testing.md).

The CLI/service still install with `.[dev]` (no Streamlit), or the base package
without development extras. Invoking the viewer without its extra returns an
install hint; importing `mn_land`, the CLI, service or launcher does not import
Streamlit. Ordinary core tests do not need a UI dependency; shell tests explicitly
require the `ui` marker/extra. CI installs and checks the pinned UI extra on its
selected platform/Python matrix so those tests cannot silently disappear there.

## Select saved evidence

1. Select a join or review in **Saved result**. The catalog scans local
   `data/processed/isanti/delinquency` and `data/processed/isanti/review` only.
   No snapshot is loaded automatically and `latest.json` never chooses for you.
2. Select **Load selected snapshot**. The application service validates the
   graph again and reads only exact inventoried JSON bytes. Integrity validation
   is not independent county verification or a claim of current debt.
3. Inspect source publication/capture/GIS dates and the validation timestamp,
   source agency/dataset, counts, unknown-field counts, holds and limitations.
   Current-year and prior-year views may overlap; they are not an additive total.
4. **Reload local snapshots** rescans and revalidates the already loaded identity.
   A new local result does not replace it. Selecting a different dropdown option
   also leaves the loaded identity unchanged until Load is selected.

The [actual ML-130 handoff](reviews/isanti-viewer-preparation-2026-10-16.md) is
join `ce541e7ad88e4a52826a90c9ff5a2139` / review
`4e2ebe46423d4f56aab999d7d9eb3a37`. The real review currently has 62 prior-year
large parcels, 49 outside PILT/exempt and 15 focused parcels. These are computed
from that chosen result, never UI constants. The listing is October 13; GIS and
recapture are October 16. All 62 combined balances remain unknown, and manual
report verification is pending. No new report was fetched by the viewer.

Report verification date is shown as **Unknown / not recorded** because the
current review comparison schema does not establish a dated report verification.
Result completion and historical PDF acquisition dates must not be relabeled as
verification dates. The viewer does not load raw PDFs or correspondence. Table
owner text is the GIS owner observation, not a merged/preferred county-listing owner.

## Narrow and inspect parcels (ML-203)

After Load, scroll to **Parcel research table**. The default land-focused view
uses the existing county review buckets, not a vacancy/buildability model.

- Choose a prior-year research view, current-year view, distinct union or overlap.
  Search displayed parcel ID, GIS owner and classification text. Text search is
  literal and case-insensitive; county ID search also ignores known separators,
  without changing displayed IDs or their leading zeros.
- Acreage bounds are inclusive exact Decimals; inputs accept decimal text to avoid
  binary-float rounding. Blank minimum uses the loaded floor; blank maximum is
  unbounded. A minimum below the candidate floor is rejected, not silently clamped.
  A review can impose a higher floor than its join; both thresholds remain visible.
- Select classification values (including explicit unknown), improvement all/
  known/unknown/known-zero/known-nonzero, and PILT/exempt review filters. The
  **Known other classification** filter excludes unknown classification as well
  as special classes. Zero improvement is an assessment observation, not proof
  of vacancy. Special classifications do not imply purchase availability.
- Counts apply all non-view filters and show each view separately. The union is
  distinct; the overlap is explicit. Do not add prior/current counts. A no-match
  filter is not a claim that the county has no delinquent parcels.
- **Sort by** and **Descending** define deterministic order across all pages,
  using Decimal values, nulls last in either direction and ascending parcel ID
  tie-breaks. Page sizes are 25/50/100. Filter/order/size changes reset the page,
  not an eligible selected identity. Grid header clicks only select columns;
  client sorting is disabled via the installed column-selection API. No grid
  row position is interpreted as a parcel identity. Exact decimal strings remain
  exact and blank cells remain unknown rather than zero.
- Use **Parcel ID to inspect**, then **Open parcel details**. This labelled path
  works independently of the grid and includes the whole filtered identity set,
  not just the current page. The selection records county, snapshot token,
  completion hash and parcel ID. Sorts/pages/reruns cannot silently open another
  parcel; filtering it out clears it with an explanation. Back keeps filters;
  Clear resets filters and selection. Loading another snapshot clears both,
  while Reload revalidates the same snapshot and keeps compatible state.
  For more than 2,000 filtered parcels, the dropdown is bounded to the current
  page plus any still-filtered selected ID; paging/search provides the other IDs
  without sending an unbounded option list to the browser.

An active source/comparison hold withholds candidate browsing rather than
re-exposing held join candidates; source/issue counts remain visible above.
Unmatched/ambiguous/held issue-row tables and contextual exports are not added by
ML-203/204. No balances are summed and no live source is requested.

## Inspect source evidence (ML-204)

**Open parcel details** explicitly revalidates the selected saved graph and the
county/snapshot/completion-hash/parcel identity before reading contributing source
evidence. A spinner marks this disk-backed action; it can take longer than pure
filtering. A final integrity check rejects changes during the read. Failure clears
the loaded table/details and requires a valid explicit load; no repair/fallback occurs.

Below the selected parcel summary, inspect:

- GIS mailing address, assessed values and legal description with source-field
  labels; GIS owner and separately mapped listing owner observations are not merged.
- Both contributing tax periods even when the table is filtered to one. Assessment
  versus payable years, row references, canonical unknown money and aggregation
  status remain distinct. Raw zero is not a verified canonical zero.
- Every contributing listing row, ten per source page, with CSV physical line range
  or XLSX sheet/record identity. Repeated fiscal rows are retained, not summed.
  Reviewed raw fields render literally; unreviewed extra columns are withheld with
  a count. Monetary abbreviations/effective dates are not guessed accounting facts.
- The retained county-confirmed year-evidence document's name/hash, without a
  local-file or correspondence download.
- Only parcel-specific sample findings pinned to this selected review, if any.
  Recorded-year alignment is shown separately from unknown source-hash/date binding;
  samples do not verify every parcel/year or current payment status. The ML-130
  review has no pinned sample; historical PDF checks elsewhere are not imported.
- Fixed-label links to the reviewed county parcel report and GIS reference. Only
  exact HTTPS host/path/query patterns are accepted; a report PIN must match this
  parcel. Links open only when clicked and may show newer external information.
  The app never embeds/fetches reports or serves local files. Synthetic links are off.

Source hashes, IDs, agency and separate dates appear in **Saved evidence lineage**;
operation paths are not exposed. Access, usable/buildable acreage, wetlands,
floodplain, zoning, resale value and profit are explicitly not assessed. These
details explain evidence, not whether to buy.

Filter/sort/source-page reruns reuse the immutable per-session detail observation
and retain its check timestamp. Back keeps table filters. Filtering out/changing
the selected parcel clears details. Reload revalidates the table but clears details;
select Open again to inspect newly revalidated evidence. There is no automatic
continuous watch, global trusted cache, county refresh or owner outreach. Exports
are a separate explicit ML-205 action described below.

## Validation and error states

For exports, see [the contextual worklist guide](worklist-exports.md): select all
filtered pages or the selected parcel, preview source/filter/order/count context,
inspect separate snapshot-wide issues, then use the explicit CSV/JSON buttons.
CSV text protection is disclosed; JSON preserves canonical values/nulls. Downloads
revalidate again on click, never use a stale prepared byte blob, and do not modify
retained sources/latest pointers. Changed evidence refuses the download; Check
export status displays deferred errors and clears stale views. Filter/scope/selection/
reload changes revoke the prior preview; pure paging does not change the export set.

- **Complete:** eligible at catalog scan; explicit Load revalidates. Valid empty
  candidates receive their own message and preserve unmatched/other counts.
- **Legacy / incomplete:** completion evidence is missing. The entry is inspectable
  by identity/reason but its Load action is disabled. Do not add completion files.
- **Failed / unsupported / invalid:** failed run, unsupported schema, corrupt,
  missing, linked or incompatible input. No automatic fallback or repair.
- **No eligible result:** explains missing/unverified inputs, not a successful
  zero-parcel result. Prepare new runs outside the UI (ML-130's operator workflow).
- **Evidence changed after load:** a new explicit load/reload fails visibly and
  clears the loaded view. No previous view stays underneath a failed-load message.

An in-memory overview/table/detail is an observation as of its displayed validation time, not
a continuously watched filesystem or live tax account. Reruns without a disk
action reuse the immutable per-session observation and its original timestamp.
There is no shared/persistent pickle cache or path/mtime-based trust cache. New
disk-backed details and exports use the service's full graph/identity validation
gate, including click-time export revalidation.

The catalog is bounded to 200 filesystem entries per result-kind folder. An
overflow/unreadable/unsafe folder produces an explicit notice rather than silently
showing a partial trusted list. User selection is a validated kind/run identity,
not an arbitrary file path, upload or URL. Synthetic datasets are explicitly marked
using retained synthetic fixture provenance/dataset labels. No synthetic dataset
is silently used when actual data is missing.

## Read-only and local-only boundary

[`ReviewService`](../src/mn_land/review_service.py) imports no Streamlit and invokes
no acquisition or replay. It delegates integrity/accounting to the existing
completion validator, follows pinned source references, rechecks their completion
hashes, and exposes immutable allowlisted overview, parcel-table and evidence DTOs. New JSON/raw artifact
reads compare the captured bytes against the validated inventory before parsing;
absolute operation paths and unrestricted source dictionaries are not sent to the page.
Details parse captured CSV/XLSX bytes under the retained input limits, match every
source row/year to saved candidates, and allowlist display fields before rendering.
County normalization and review classification stay in county code. The table
projection reuses the existing county review-bucket function; no raw tax fields
are reinterpreted in widgets. Filtering/sorting/pagination and selection checks
live in the framework-independent [table service](../src/mn_land/parcel_table.py).

[`launcher.py`](../src/mn_land/ui/launcher.py) forces CLI-level settings, which
outrank global/project config and environment overrides. The checked
[project defaults](../.streamlit/config.toml) match those settings:

- loopback only, headless startup and no email prompt;
- usage telemetry off, file watching/run-on-save off;
- CORS/XSRF protections on and static file serving off;
- minimal toolbar, no frontend exception details or implicit Python magic;
- `client.disableDataExport=true` to disable built-in grid download/clipboard copy.

These settings follow the installed API and [official configuration reference](https://docs.streamlit.io/develop/api-reference/configuration/config.toml).
Use the launcher rather than arbitrary direct `streamlit run` overrides. There
are no remote fonts, map tiles, iframes, raw HTML or browser-to-county data calls
in this shell. Source strings render with literal `st.text`, not Markdown/HTML.
Only allowlisted current-page columns reach the grid, with native plain-text
rendering (not Markdown/image/link columns). The app also sets the scriptable
export-disable option before any grid renders. This prevents UX shortcuts from
bypassing contextual/formula-protected exports; it is **not access control**:
displayed data remains accessible to the local user/browser. Only explicit ML-205
contextual download widgets are exposed, with no upload widgets, arbitrary local-file
routes or credentials. ML-204 exposes
only the validated county reference links described above.

Loopback is not authentication or isolation from another local account/browser.
Do not forward the port or bind on a LAN/public interface. The app is not deployed
and datasets remain ignored local files, not a GitHub or cloud backup.

## Verification scope

Offline service fixtures cover legacy/failed/unsupported/corrupt/valid-empty
graphs, active holds, null amounts, identity stability, read-after-validation
changes, bounded catalogs, pinned source identity, portability and no automatic
latest/acquisition/replay. Service loads and CLI help are also exercised with all
Streamlit imports deliberately blocked.

Supported AppTest controls exercise explicit selection/load/reload, pure reruns,
newer-result stability, corruption invalidation, synthetic labels, empty states
and literal source holds. Windows asyncio needs an internal socketpair for
AppTest; its fixture allows only a factory-created self-wakeup pair while keeping
DNS, public and arbitrary loopback connections blocked. This is not permission
for UI county requests. AppTest is not a browser, zoom/focus or screen-reader audit;
those actual usability checks remain ML-206.

ML-203 adds pure [filter/identity tests](../tests/unit/test_parcel_table.py),
[validated-load tests](../tests/unit/test_parcel_table_load.py), and
[AppTest interactions](../tests/unit/test_parcel_browser.py). They cover dynamic
overlap counts, Decimal boundaries, unknown-versus-zero, classification/holds,
stable sorting/pagination/selection/back/reset, malicious literal source text,
allowlisted grid columns and installed export/sort configuration. See
[testing evidence](testing.md) for actual-data checks and platform results. Grid
browser/clipboard/zoom/screen-reader behavior is not certified by AppTest.

ML-204 adds [pure evidence/link tests](../tests/unit/test_parcel_evidence.py),
[integrity/load tests](../tests/unit/test_parcel_detail_load.py), and
[detail AppTest cases](../tests/unit/test_parcel_detail_ui.py). They cover all rows,
year/period consistency, independent owners, repeated money/unknowns, CSV/XLSX
identity, values-only spreadsheets, URL spoofing/mismatch, literal markup/formulas,
sample scope, read-time changes, no acquisition/substitution and cached reruns.
The saved ML-130 data also passed detail/back/reload checks with both periods,
three contributing rows, two safe references and no historical sample substitution.

Implementation `8e79a2eeb4492d9f7fb385a3773c1ca269124f96` passed all 758 offline
tests without skips in each hosted Windows/Linux x Python 3.11/3.12 job in
[run 39044032811](https://github.com/huschked/minnesota-land-intelligence/actions/runs/39044032811).
Actual-data AppTest also passed with the 15/49/62 views and stable selection.
The user-approved restarted viewer was checked healthy on 127.0.0.1:8501. Refresh
the browser, explicitly choose Review `4e2ebe46423d4f56aab999d7d9eb3a37`, then Load;
research filters and the table appear below the source dates/limitations panels.

ML-204 implementation `80e669f66cadf31d58c5818eebc98fbfb19432c9` passed all **803**
offline cases without skips in each hosted Windows/Linux x Python 3.11/3.12 job in
[run 39079534737](https://github.com/huschked/minnesota-land-intelligence/actions/runs/39079534737).
The actual-data details/back/reload check passed again on committed code, with all
859 baseline saved files unchanged. The approved project-only restart is healthy
on [127.0.0.1:8501](http://127.0.0.1:8501). Refresh, explicitly load the ML-130 review,
choose a filtered parcel ID, then select **Open parcel details**. Full contextual
exports were subsequently added by ML-205. Final browser accessibility release
checks still remain ML-206.
