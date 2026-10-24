# Saved suitability publication and review — ML-306

This publishes the existing [ML-305 mapped-policy calculations](constraints.md)
as a separate completed local enrichment run, with canonical CSV/JSON, retained
map-review evidence and optional integration into the existing review viewer.
It does not refresh sources/taxes, determine regulatory status, create a map
application, rank investments or rewrite prior observations. Unknown stays unknown.

## Publish deliberately, reproduce offline

```powershell
.\.venv\Scripts\python.exe -m mn_land.cli publish-suitability --county isanti --constraint-snapshot data/processed/isanti/constraints/EXPLICIT_COMPLETED_ID --validation-report PATH_TO_REVIEW/review.json
.\.venv\Scripts\python.exe -m mn_land.cli validate-suitability --snapshot data/processed/isanti/enrichment/EXPLICIT_ENRICHMENT_ID
```

Use the existing optional `gis` extra for source replay. `suitability_enrichment`
pins the complete constraint graph under `inputs/constraints/`, preserving its
two branches and common ancestry. Only this fixed new graph permits six edges;
historical graphs retain their four/five-edge budgets. Default output is
`data/processed/isanti/enrichment/<UUID>/`. Dedicated `--output-root` cannot
overlap retained runs or review evidence. No implicit latest selection or source
request occurs. Runs can complete with explicitly held parcel rows.

The source-bound `review.json` names its exact constraint completion hash, an
aware review timestamp, method, findings and bounded representative parcel/official
map URLs. Its 1–30 individually hash-pinned PNG/JPEG/JSON/Markdown evidence files
are copied into `validation/`. Synthetic reviews must identify their method as
`synthetic_fixture` and are labelled in the UI. The report is a retained review
declaration, not a machine-verifiable survey or external authority certification.

`enrichment.json` contains a schema version, shared context and distinct ordered
records. Context includes source/candidate identities and hashes, listing date,
independent source/parcel capture dates, inclusion policy, analysis CRS/runtime
evidence, review findings/limits and notices. Records preserve normalized text
parcel IDs, measured versus deeded acres, individual wetland/water and flood
metrics, combined constraint/shared/remainder acres, coverage-gap area, source
row/geometry hashes, spatial project/panel/study dates and holds. Detailed WKB
and original attributes remain in the pinned graph rather than the review grid.

`enrichment.csv` has one row per parcel, fixed columns and quoted fields. Context,
holds and date contexts are JSON cells. `\N` denotes null, distinctly from a
numeric zero. CSV contains the same canonical scalar values, not apostrophe-
modified presentation values. Unsafe scalar formula/control/null-marker text
refuses export; arbitrary source text is not an executable scalar cell. **Import
parcel IDs as text or use JSON:** a spreadsheet's automatic CSV inference can
remove leading zeros despite quoting. No universal spreadsheet/re-save guarantee
is claimed. JSON preserves canonical types/nulls; no Excel workbook is introduced.
Both outputs are bounded at 8 MiB; failures produce no partial output.

Offline validation checks all retained source bytes/semantics, report/evidence
hashes, publication chronology, exact derived JSON/CSV bytes and row accounting.
Rehashing altered metrics or reports cannot silently promote old calculations.
Only a child freshly validated within that same graph-validation call is reused
by the export projection; nothing caches integrity checks across separate reads.

## Existing viewer integration

First explicitly load the compatible join/review candidate snapshot. Then choose
a **Saved suitability publication** and press **Load suitability evidence**.
Catalog names are unvalidated until that action; no publication is auto-attached.
The publication must pin the exact loaded review or join ID **and completion
hash**, and its parcels must belong to that candidate observation. Source holds,
wrong lineage, incomplete/changed runs or missing optional GIS refuse loading.

The existing research table gains suitability status, GIS-measured acres and
preliminary remaining acres. Existing candidate filters still apply to **deeded**
acres. `complete`, `held` and `not_assessed` are distinct: parcels outside the
selected suitability observation are not assessed, never assigned zero constraints.
Parcel details show components, shared area, hold reasons, independent dates,
source hashes, policy and map-review limitations. Numeric wetland observations
may remain visible on a flood-held parcel, but combined/remainder totals are null.

Cheap reruns reuse a per-session immutable observation; they do not repeatedly
replay GIS. Explicit Load/Preview/Download revalidate. Suitability downloads are
separate from the unchanged tax worklist export, with all-filtered-across-pages
or selected-parcel scope. Preview reports numeric/held/not-assessed counts and
pins filters/order/identities. Changing filters, loaded evidence, scope, selection
or reloading revokes old jobs. Deferred download checks before and after fresh
validation; errors clear stale suitability values without silently replacing them.
Reload never fetches a county/GIS service. The viewer remains loopback-only.

## Official-map sample review — 2026-10-24

Three saved parcels were deliberately selected: high wetland/SFHA overlap
`040060400`, independently covered zero-overlap `060311200`, and cross-study/
numerical-diagnostic held parcel `010131402`. DNR Wetland Finder views and official
FEMA MapServer zone/panel renders were inspected and privately retained. These
are new dated **comparison views**, not fresh inputs to the saved calculations.

The high-overlap view shows DNR emergent/forested classes (clicked feature PEM1D)
and extensive FEMA Zone A. The DNR popup's 76.53 acres describes the whole source
feature, **not the parcel's wetland acreage**. The zero-control viewport has no
visible NWI/SFHA fill and an Isanti panel dated 2003-11-05; a blank picture alone
does not prove zero, so saved independent coverage still gates the numeric result.
The held sample's FEMA render labels both Isanti 27059C0325D and Anoka grids
27003C0100E/0095E, illustrating cross-study panel overlap rather than absent Isanti
coverage. The native export requested all zone/panel layers, no single-study filter.

All six held panel inventories were reviewed. The Anoka not-printed records state
`AREA OUTSIDE COUNTY BOUNDARY`; Pine's state `NO SPECIAL FLOOD HAZARD AREAS
IDENTIFIED`. All six have complete study-matched Isanti coverage. The reasons and
eligible printed panels remain distinct. FEMA's [official index training](https://emilms.fema.gov/is_0273/groups/285.html)
describes panel grids, community boundaries and not-printed notes separately; a
rendered grid/label does not establish applicability for a regulatory parcel
decision. No ignored panel, less conservative policy or new numeric total is
introduced. All six remain held/null; v1 replay and original source files persist.

The approximately 1.96e-8 m² zone-union processing residue on `010131402` cannot
be adjudicated from these maps; it is not a physical missing-coverage assertion.
It remains explicit, without snapping, buffering or a tolerance-based fill.
The computational area gate is unchanged: max(0.01 m², measured area × 1e-6),
not a source-position guarantee. Visual comparison is qualitative; no independent
pixel-to-acre error bound was established and renderer extents may adjust to
aspect ratio. DNR searches locate approximate geographic centers, not a precision
overlay. The [DNR FAQ](https://www.dnr.state.mn.us/wetlands/nwi_faq.html) separately
describes source identification/classification and positional limitations; its
published accuracy is not independently certified for these parcels. No legal
buildability, jurisdictional delineation, insurance or purchase conclusion follows.
