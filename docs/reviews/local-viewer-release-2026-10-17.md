# Local viewer release check — ML-206

Date: 2026-10-17 (America/Chicago). Scope: the existing read-only local viewer,
not hosting, current tax verification, acquisition recommendations or new data.
Runtime/test code is unchanged from ML-205's final revision
`17f33cb0c8f69aeb6b2fddc84277a5a2db584280`; this delivery packages operating guidance
and release evidence. Raw county files and completed runs were not edited.

## Environment and installation

Windows 11 build 26300, CPython 3.12.14, Streamlit 1.66.0. Agent browser checks used
the Codex in-app browser on Windows, initially 1280 × 720 CSS pixels, device pixel
ratio 1.25. Its exact Chromium/browser build is not exposed by the available
browser interface; no Chrome version or cross-browser certification is inferred.

A new, isolated `.venv-ml206` was created using `python -m venv`. From the project
root, that interpreter successfully installed `-e ".[dev,ui]" -c constraints-dev.txt`,
reported Streamlit 1.66.0, and passed `python -m pip check`. Its supported module
launcher started the saved-results screen on **127.0.0.1:8502**. The actual project
viewer was separately restarted, with permission, on **127.0.0.1:8501**. Its exact
old launcher/listener pair 20800/18608 was verified before stopping; replacement
launcher/listener PIDs were 26812/23920 and the health response was `ok`.

Two setup findings are retained rather than hidden:

- Sandboxed pip/ensurepip initially could not write Windows temporary wheel files.
  The approved non-sandboxed install succeeded; no security policy was weakened.
- An initial virtual environment nested inside the long preparation directory hit
  a Windows package-file path limit while installing Streamlit's bundled templates.
  A fresh short-path environment succeeded. Use a short project/environment path;
  do not enable OS-wide long-path settings as an automatic workaround. The original
  project environment and the failed isolated environment were not deleted.

This is a successful fresh environment install, not a transitive/hash-locked build
or a new framework upgrade. Normal dependency installation may contact the package
index; **offline viewer operation/tests** do not mean installation needs no network.

## Actual-data browser checks

Explicitly selected ML-130 review `4e2ebe46423d4f56aab999d7d9eb3a37`, pinned to join
`ce541e7ad88e4a52826a90c9ff5a2139`. No latest-pointer selection or synthetic fallback.

| Check | Observed result |
|---|---|
| U12: real eligible evidence | Computed view counts 15 focused, 49 outside PILT/exempt, 62 prior-year, 13 special, 291 current-year, 311 distinct union and 42 overlap. These remain nonadditive. |
| Dates and uncertainty | October 13 publication and October 16 captures; no active source hold, report verification unknown, accounting unresolved. Detail canonical balances stay unknown, not zero or raw-field sums. |
| U09: keyboard detail path | ArrowDown/Enter selected `01.013.1402`; Tab reached the labelled clear control then Open parcel details; Enter opened that exact parcel. Focus-visible state and a visible focus outline were observed. No canvas row position is used as identity. |
| Detail evidence | Both prior/current periods, three distinct source rows, separate GIS/listing owners, exact assessment/payable years, not-assessed suitability and no imported historical sample. Back retained the table context. |
| Identity/export guards | A table-header attempt left observed ID/order unchanged. Changing the supported Sort by control to Deeded acres retained selected `01.013.1402`; Open still showed that same parcel and its three source rows. The native grid toolbar had columns/search/fullscreen, no download. Ctrl+C on the actual focusable grid canvas left a browser-clipboard sentinel unchanged; the prior empty browser clipboard was restored. |
| Empty filter | A deliberately unmatched search displayed zero filtered parcels with the explicit warning that this does not mean no county delinquency; Open was disabled. Clear restored the real default view. |
| Native JSON and CSV downloads | Explicit preview showed 15 candidates and 1,764 snapshot-wide issue/accounting entries. Both files were obtained through actual browser download events, then parsed/checked locally. |

The focused CSV is **7,662,733 bytes**. Its 15 candidate IDs/order match JSON,
every data text cell has the documented apostrophe protection or `UNKNOWN`, and
the full context matches across formats except their deliberately different
click-time `integrity_checked_at` timestamps. Both downloads preserve publication,
GIS date, canonical null balances, exact values, snapshot identity and preview
fingerprint `026d3840577b42fa23ad3178efe9de6df651ddf403a04cd7eabafdfed98d1b8c`.
The 1,764 entries are not extra candidates or unique parcels. Downloads remain
local; no county data, screenshots or worklists are added to Git.

The browser-tool operations took about 49 seconds for JSON and 144 seconds for
CSV, including browser/download mediation and validation. These are not isolated
server performance benchmarks. Large contextual exports can be slow; do not
repeatedly click or remove integrity checks. Prefer narrower candidates/JSON when
appropriate, recognizing that issues remain snapshot-wide.

## Zoom and accessibility boundary

The user explicitly confirmed **“200% zoom is readable and usable”** after being
asked to check filters, parcel selection/details and exports in Chrome/Edge. This
is user-performed Windows/browser acceptance evidence, **not agent-automated zoom
verification**. The exact browser/version and a screenshot were not supplied.
The available browser controls did not verify native zoom; a viewport override
also did not produce a verified smaller viewport and was reset. Neither is
reported as an automated 200% pass.

Labels, text warnings, keyboard selector/activation and visible focus were checked.
No screen reader, exhaustive contrast/keyboard matrix, all canvas mouse hit targets,
mobile browser or Excel re-save audit was performed. This is a bounded local
release check, not WCAG/accessibility or spreadsheet interoperability certification.
The labelled selector/detail path is primary; the canvas is not the only way to
inspect a parcel. Report essential usability failures before expanding the UI.

## Isolated error and refusal checks

An approved **127.0.0.1:8503** QA server used only locally generated synthetic
completion graphs from the existing offline fixtures, prominently labelled as
synthetic. Acquisition/import/replay/latest functions were prohibited in its
wrapper. No original county run was corrupted to test failure behavior.

- A valid completed empty result remained distinct from missing/invalid evidence.
- A real legacy entry in the saved-results catalog had Load disabled.
- A synthetic hold rendered `<script>not markup</script>` literally, displayed an
  active-hold warning and withheld candidate browsing while preserving issues.
- After preparing that held issue-only export, changing **only its disposable
  synthetic summary** caused keyboard activation of the actual deferred JSON
  button to fail. **Check export status** visibly reported “Download refused”,
  no stale/partial file, and cleared the old table/preview/loaded evidence.
  The server log records the expected `RunValidationError`, not successful output.

An earlier mouse-driven failure attempt stalled and produced a backend session-ID
mismatch after a browser websocket closure; no file was observed, but that was
**not** counted as evidence-change refusal. A fresh active-session keyboard test
above supplied the actual refusal evidence. Background/disconnected sessions may
lose in-memory selection: explicitly select/load again; never silently select latest.

Private screenshots/helpers/logs and disposable fixture graphs are retained under
`data/processed/isanti/preparation/ml-206-2026-10-17/`, outside completed county
runs. The two temporary QA servers are stopped after verification; the main
8501 viewer remains available. No retained source data was deleted.

## U11: offline/read-only boundary and regression

The supported launcher has loopback-only forced flags, telemetry/static serving
off and CORS/XSRF protections on. Installed-option tests verify CLI precedence
over deliberately unsafe environment overrides. DOM resource inspection found
no absolute remote embedded resources; county references in details remain
explicit links, never embedded requests, and were not followed. The independent
service has no acquisition/replay call path. Offline tests block DNS/socket calls;
the isolated browser wrapper also rejects acquisition/import/replay/latest calls.
No county refresh, report fetch, source edit or public exposure was performed.
This is code/test/browser-resource evidence, **not a packet-capture audit of all
workstation traffic**. Loopback is not authentication or isolation from other users.

Local targeted tests: **22 passed in 62.12s** (launcher, shell, deferred UI cases).
One pytest-cache write-permission warning is not a test failure. In the fresh
short-path environment, **36 passed in 3.48s** (launcher and pure worklists), with
cache writing disabled. These sets overlap; they are not an additive full-suite
claim. Synthetic browser graph preparation passed its offline fixture check.

All **871** preexisting baseline raw/processed/audit/helper files retained exact
sizes and SHA-256 after checks; only active `server.log`/`server-error.log` files
were excluded from the baseline. New private QA artifacts/environments and local
browser downloads are separate. Saved inputs, mappings, years, outputs and latest
pointers remain unchanged.

No production, test, dependency-pin or CI code changed. The existing full hosted
gate remains [ML-205 run 39082776024](https://github.com/huschked/minnesota-land-intelligence/actions/runs/39082776024):
840 offline passes, no skips, per Windows/Linux × Python 3.11/3.12 job. This
documentation-only release handoff uses the configured Linux-only fast CI; it does
not claim a new Windows matrix or repeat unchanged full local tests.
