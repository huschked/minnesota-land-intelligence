# Local snapshot selector (ML-202)

The first read-only UI shell can select a completed join or review, validate its
full pinned graph, and show source identities, dates, counts, holds and unknowns.
It does **not** implement parcel tables/filters (ML-203), parcel details/links
(ML-204), contextual exports (ML-205) or the final browser/accessibility release
checks (ML-206). A working shell is not a land acquisition recommendation.

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
verification dates. The shell does not load raw PDFs, correspondence or owner rows.

## Validation and error states

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

An in-memory overview is an observation as of its displayed validation time, not
a continuously watched filesystem or live tax account. Reruns without a disk
action reuse that immutable per-session overview and its original timestamp.
There is no shared/persistent pickle cache or path/mtime-based trust cache. New
disk-backed details and exports in later stories must use the service's
`revalidate` gate before reading; those features are not implemented here.

The catalog is bounded to 200 filesystem entries per result-kind folder. An
overflow/unreadable/unsafe folder produces an explicit notice rather than silently
showing a partial trusted list. User selection is a validated kind/run identity,
not an arbitrary file path, upload or URL. Synthetic datasets are explicitly marked
using retained synthetic fixture provenance/dataset labels. No synthetic dataset
is silently used when actual data is missing.

## Read-only and local-only boundary

[`ReviewService`](../src/mn_land/review_service.py) imports no Streamlit,
acquisition or replay code. It delegates integrity/accounting to the existing
completion validator, follows pinned source references, rechecks their completion
hashes, and exposes an immutable allowlisted overview DTO. New JSON artifact
reads compare the captured bytes against the validated inventory before parsing;
absolute operation paths and raw source dictionaries are not sent to the page.
County normalization and review classification stay in the existing pipeline.

[`launcher.py`](../src/mn_land/ui/launcher.py) forces CLI-level settings, which
outrank global/project config and environment overrides. The checked
[project defaults](../.streamlit/config.toml) match those settings:

- loopback only, headless startup and no email prompt;
- usage telemetry off, file watching/run-on-save off;
- CORS/XSRF protections on and static file serving off;
- minimal toolbar, no frontend exception details or implicit Python magic.

These settings follow the installed API and [official configuration reference](https://docs.streamlit.io/develop/api-reference/configuration/config.toml).
Use the launcher rather than arbitrary direct `streamlit run` overrides. There
are no remote fonts, map tiles, iframes, raw HTML or browser-to-county data calls
in this shell. Source strings render with literal `st.text`, not Markdown/HTML.
No grid/download/upload widgets, arbitrary local-file routes, county links or
credentials are exposed. Future exports/links have their own safety gates.

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
