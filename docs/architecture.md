# Architecture

## Suitability publication and optional review integration (ML-306)

`enrichment.py` projects a completed constraint graph into canonical CSV/JSON,
retaining a source-hash-bound map review and evidence. Its fixed publication graph
adds one edge (six total), without relaxing historical four/five-edge guards.
Only the new publication's content check reuses the child freshly validated in
that same validation call; there is no cross-read integrity cache. All outputs,
source/report hashes, chronology and accounting reproduce offline.
`suitability_service.py` binds an explicit publication to the exact loaded review/
join completion and exposes immutable allowlisted observations/previews. The native
Streamlit renderer in `ui/suitability.py` adds optional columns, evidence and scoped
downloads; filters reuse session memory, disk actions revalidate. No implicit
latest/parcel-ID-only join, source refresh, new map app, score or canonical tax change.
See [contracts, map review and limits](suitability.md).

## Offline mapped constraint combination (ML-305)

`constraint_runs.py` accepts two explicit completed wetland/flood runs, requires
the identical pinned geometry, selections and CRS/reference evidence, then
copies both graphs into a separate `constraint_analysis`. `constraints.py`
unions explicitly included water/SFHA geometry and calculates the preliminary
remainder against measured parcel area. Upstream holds propagate; coverage gaps
are quantified, not filled. Validation reproduces sources and all derived results.
Only this fixed two-branch graph receives a five-edge budget; existing graphs
retain four. No new dependency, network, tax/geometry mutation, UI or score.
See [policy, controls and commands](constraints.md).

## Separate effective flood observations (ML-304)

`flood_runs.py` pins one explicit geometry graph into `flood_analysis`, separately
from wetland/tax/UI paths. `sources/fema_nfhl.py` owns fixed effective FEMA layer/
table identities, MapServer schema omissions, safe study-ID table selection and
category policy. A schema callback extends the existing exact polygon acquisition
without changing the DNR default. `counties/isanti/flood_crs.py` explicitly handles
native NAD83 geographic input with the audited grid/county bridge, not DNR's UTM
stage. `floods.py` validates, projects, dissolves/clips exact category tuples and
gates metrics on study-matched availability, dated panels and zone geometry.
Panel/revision/study contexts stay distinct; revisions are not extra hazard area.
All calculation/context/coverage results reproduce offline. See [contract](floods.md).

## Separate wetland observations (ML-303)

`wetland_runs.py` pins an explicit geometry graph into a new `wetland_analysis`
run. `sources/dnr_nwi.py` owns reviewed DNR layer/field and versioned inclusion
contracts; `ingestion/spatial_capture.py` and `spatial_layers.py` retain bounded
native responses and reconcile exact AOI/OID membership. The Isanti
`wetland_crs.py` adapter owns the audited adjusted-datum bridge and pinned NOAA
grid. `wetlands.py` performs deterministic validation, local analysis-copy
projection, dissolve/clip and independent project-coverage/date binding.
Offline validation replays capture evidence and reproduces derived results.
Unknown/partial coverage or classification is a held row with null totals, not
zero. The run graph depth budget is four edges for wetland -> geometry -> review
-> join -> raw; fixed allowed kinds/labels, containment and hashes still apply.
No base import needs GIS libraries, and no viewer/tax pipeline is changed.
See [wetland contracts and limitations](wetlands.md).

## Separate polygon foundation (ML-302)

`geometry_runs.py` pins one explicit completed review into a new `parcel_geometry`
run. `counties/isanti/geometry.py` owns the fixed official URL, county identity
fields, native CRS and bounded exact-OID capture contract; it does not change
`ArcGISClient`'s attribute-only behavior. `geometry.py` validates Esri linear
polygon topology and calculates same-native-datum local equal-area observations
with optional Shapely/pyproj dependencies. Captures and analysis share one
all-selected-or-failed completion. `run_checks.py` routes offline integrity and
reproduction checks lazily; existing result kinds retain their contracts.
No viewer, thematic service, score or tax pipeline imports this acquisition path.
See [CRS/tolerance/completion decisions](geometry.md) and default no-repair policy.
ML-303 separately resolves its explicit DNR alignment; FEMA alignment remains
ML-304's own gate, not a blanket approval of other CRS transformations.

The parcel pipeline is deliberately linear: official ArcGIS service → complete raw acquisition → pinned source copy → county adapter/canonical parcel → validation/filtering → completed per-run exports. `ArcGISClient` owns HTTP, retries, metadata, count checks, and pagination. The Isanti county adapter package owns county GIS field names and schema declarations. Core filtering accepts `Parcel` instances and records deterministic rejection reasons.

Phase 1.1 separates source responsibilities. A `DelinquencySource` produces county-independent `DelinquencyRecord` objects from an authoritative delinquency-specific publication. The parcel and delinquency snapshots are normalized independently, joined only by a county-specific deterministic parcel-ID key, and retain independent lineage.

```text
Official parcel GIS -> Parcel -------------------+
                                                   exact normalized-ID join -> status -> candidates
Official delinquency file -> DelinquencyRecord --+
```

Absence from a snapshot does not establish that a parcel is current. Duplicate delinquency rows and duplicate parcel join keys are ambiguous, not silently aggregated. Unmatched source rows are exported for review.

New parcel acquisitions store initial/final metadata and count/ID inventories, ordered parsed pages, and bounded original HTTP bodies with per-attempt evidence/hashes under an exclusively reserved UUID directory. Capability, page, membership and detectable-change checks are described in [retrieval](retrieval.md). New file imports capture exact bounded mapping/source/supporting bytes before normalization. Raw and processed completion are separate; failed/staging directories are not results. See [publication](publication.md). Historical captures remain unchanged.

Additional counties should implement `CountyAdapter` and produce the same canonical model. Future GIS enrichment can attach derived observations after normalization; persistent spatial processing can move to PostGIS only when scale warrants it. None of that is part of Phase 1.

Source-specific review holds are explicit mapping settings. They propagate into
delinquency records and prevent exact joins from becoming verified delinquency.
Identity matching, source-list presence, and confirmed tax status are distinct.
Independent official-record evidence is retained separately from raw imports;
new hold-aware outputs do not overwrite earlier snapshots. Isanti review views
group factual classifications and improvement values without generating scores.

County-confirmed mixed sources classify each record's tax period before joining.
Prior-year unpaid status is existential: one or more confirmed prior-year rows
can establish parcel presence, while repeated fiscal components still cannot
establish an additive total. Multi-row lineage is retained. The source's report
assessment year sets the current/prior boundary, independently of execution date.
Separate exports prevent current overdue installments from entering the prior-year
candidate count; parcels may appear in both views with disjoint supporting rows.

## Execution identity

`mn_land.provenance` records package version, local Git revision/dirty state when
available, the actual Python source-file hashes, Python/platform, installed
distribution versions, effective nonsecret configuration and its SHA-256, and
explicit input/output file hashes. See [reproducibility](reproducibility.md).
This is execution evidence, not a new authority for county facts. A dirty revision
is not a recoverable release on its own; retain the corresponding source changes.
The helper performs no network requests and adds no runtime dependency.

New GIS raw manifests carry request/runtime identity and raw artifact hashes.
`find-candidates` writes `execution.json` in its immutable processed run, linking those
inputs to the derived exports. Join manifests and review summaries carry their own
`provenance` object. Their self-hashes are deliberately excluded. Historical
snapshots and old flat parcel exports are not rewritten. New outputs use per-run
directories and validated completion records/pointers, not flat compatibility files.

## Implemented ingestion hardening

[ML-119's contracts and fixture matrix](ingestion-contracts.md) distinguish
observed behavior from proposed validation/retrieval/publication guarantees.
ML-125 implements [strict validation](validation.md): bounded CSV/XLSX readers,
mapping/evidence checks, finite numeric representations, an adapter-owned metadata
callback, and explicit normalization diagnostics. ML-126 now implements
[respectful HTTP and source completeness](retrieval.md), using that callback before
queries and again at the end. Policy is shared between Settings, client and transport;
sequential pacing/retry budgets and original response capture use fake clocks in tests.
ML-127 implements [staged completion publication and shared reader eligibility](publication.md).
Producers pin validated source graphs and reconcile actual artifacts/rows before
installing version-2 completion records and latest pointers. Legacy manifests and
recorded hashes alone are not new-protocol eligibility. No migration is performed.

ML-123 adds [explicit snapshot selection and offline replay](replay.md). File capture
and joining retained inputs share one processing path; replay never calls acquisition
or latest selection. It reuses captured input limits and dates, checks the selected
county/service/layer/query, pins exact inputs, records normalized/export fingerprints
and rejects unexpected drift before completion. Moved join graphs remain self-contained.
Historical pre-completion runs are not migrated or certified; current code/runtime
identity is recorded rather than pretending to restore historical software.

## Saved snapshot differences

ML-124 adds [offline saved-join comparison](snapshot-comparison.md) through
`snapshot_diff`, using existing county normalization/join semantics and recorded
fingerprints. A new immutable `comparison` run pins two join graphs; its content
validator recomputes the report from contained evidence and explicit date policy.
No acquisition, reimport, latest-input selection or UI refresh is involved.

## Local viewer shell and planned research workflow

[The UI plan](ui-plan.md) defines the eventual basic review workflow. ML-202's
[implemented shell](viewer.md) uses a framework-independent `ReviewService` and
existing graph validation, with explicit join/review loading and local catalog
states. A frozen allowlisted overview carries IDs, hashes, dates, counts, holds,
unknowns and validation time; raw source dictionaries/paths are not browser DTOs.
Streamlit is an optional extra, imported only by the app/launcher invocation.
No source normalization, acquisition/replay, scoring or balance aggregation belongs
in widgets. Exact inventoried-byte JSON reads reject changes after validation and
pinned-child completion identities are checked between reads. New loads/reload
revalidate; pure reruns keep the per-session in-memory observation and its original
timestamp, not a pathname/mtime trust cache. New disk-backed details/exports must
use the same revalidation gate. [ML-130 supplied eligible real inputs](reviews/isanti-viewer-preparation-2026-10-16.md)
in new runs while historical files remain legacy. ML-206 still has a
real-data/accessibility release gate. The launcher enforces loopback, telemetry off,
CORS/XSRF on, static serving off and literal source-text rendering. Tables/filters
are added by ML-203 below; ML-204 adds parcel evidence links/details and ML-205
adds contextual/formula-protected exports;
no data migration or county acquisition is performed by the shell.

ML-203 adds a separate immutable `ParcelDataset` projection from the selected
join's two exact inventoried candidate exports. The loader revalidates the graph
and completion identity, applies the selected review floor and withholds browsing
under active holds. `parcel_table` reuses county classification and ID normalization
while owning exact Decimal filters, distinct view counts, null-last stable ordering,
pagination and county/snapshot/hash/parcel selection identities. Cheap reruns use
only per-session immutable observations, not shared pickle caches or new disk reads.
The UI sends only allowlisted current-page fields, disables grid export/copy and
client column sorting, and uses an independent labelled keyboard detail-summary
path. ML-205 adds contextual exports below; browser release QA remains ML-206. No ingestion
or canonical monetary meaning changes.

ML-204 adds frozen `ParcelDetails`/`ListingRow`/`PeriodEvidence` projections and a
literal-text renderer. Explicit Open revalidates the selected graph and identity,
reads exact inventoried CSV/XLSX bytes through the existing bounded table parser,
matches every contributing record/location to the candidate exports, checks year
sets and the reviewed county convention, then revalidates before returning. Raw
monetary observations are never summed or promoted to unmapped canonical balances.
Ten-row source pagination and ordinary reruns reuse the immutable per-session DTO;
Reload clears details and requires another explicit Open. A failed new disk action
clears stale table/details rather than retaining them underneath an error.

County-specific display fields and strict HTTPS host/path/query/parcel link rules
live in the Isanti adapter. Fixed-label links open only on user clicks, never
through embeds, automatic report requests or local file routes. Lineage contains
run IDs, fields, dates and hashes, not operation paths or correspondence contents.
Only the explicitly selected review's inventoried comparison can supply parcel-
specific sampled findings; missing source-hash/date binding is disclosed and no
historical sample discovery or general/current verification is implied.

ML-205 adds pure immutable [worklist projection/serialization](worklist-exports.md)
and county-isolated saved issue-table allowlists. The service revalidates on Preview
and on each native deferred download, checks the semantic preview fingerprint,
reuses exact parcel source-row/year/money validation, and returns only bounded
in-memory bytes. Filters/scope changes revoke old jobs via per-session events;
thread errors use a queue and clear stale views on the next interaction. Download
threads do not touch session state. Candidate rows are distinct filtered/selected
IDs across pages; snapshot-wide issue/accounting entries remain separate. CSV text
protection is disclosed; JSON retains canonical exact-decimal strings/nulls. Saved
outputs, raw inputs and latest pointers are never modified. ML-206 subsequently
records [bounded Windows/browser release evidence](reviews/local-viewer-release-2026-10-17.md)
including native downloads/refusal, clipboard and keyboard checks, separately
from AppTest and user-performed 200% zoom acceptance. It adds no runtime component,
network exposure or data mutation; screen-reader/conformance certification remains
outside these recorded checks.

## Historical Phase 2 source decision (ML-301)

This paragraph records the discovery boundary. ML-302 geometry, ML-303 wetland
and ML-304 flood observations are now implemented separately as described above;
ML-305 combination is implemented separately above; ML-306 official-map validation
and integration remain future work.

The [suitability contract](suitability-sources.md) selects DNR NWI/project footprints
and FEMA effective NFHL/coverage/panel/revision evidence after bounded official
metadata/query checks. A separate polygon acquisition path must preserve the
existing attribute-only `ArcGISClient` contract and pinned tax results. Geometry
and future enrichment are new dated immutable observations, not edits to old
source graphs or hidden viewer requests. County-specific IDs/provider fields stay
in adapters; reproducible geometry/coverage/area logic stays outside widgets/LLMs.

ML-302 must define acquisition/CRS/topology/area validation; ML-303/304 will acquire
and overlay selected thematic data; ML-305/306 will combine/validate/publish it.
No geometry library, projection, persistent GIS store, overlay, endpoint or new
UI feature is introduced by this discovery. Missing source coverage or invalid
geometry/date evidence cannot produce a trusted zero constraint or buildable acres.
