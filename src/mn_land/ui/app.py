"""Read-only snapshot selector and ML-203 parcel tables."""

import streamlit as st

from mn_land.config import settings
from mn_land.parcel_table import (
    IMPROVEMENTS,
    SORTS,
    SPECIAL,
    VIEWS,
    TableFilters,
    number,
    query,
    select_parcel,
    selected_row,
    selector_ids,
)
from mn_land.review_service import ReviewService
from mn_land.runs import RunValidationError

st.set_page_config(page_title="Minnesota land review", layout="wide")
st.set_option("client.disableDataExport", True)
st.title("Minnesota land review")
st.caption("Read-only saved evidence · Parcel research")
st.text("Choose a saved result to inspect its source dates, counts and limitations.")
st.caption("Full source-evidence details and contextual exports are still to come.")

service = ReviewService(settings.SETTINGS.processed_dir)
st.session_state.setdefault("catalog", None)
st.session_state.setdefault("loaded", None)
st.session_state.setdefault("load_error", None)
st.session_state.setdefault("parcels", None)
st.session_state.setdefault("open_parcel", None)


def clear_table():
    for name in (
        "table_view",
        "table_search",
        "table_min",
        "table_max",
        "table_class",
        "table_improvement",
        "table_special",
        "table_sort",
        "table_desc",
        "table_size",
        "table_page",
        "table_signature",
        "parcel_choice",
        "open_parcel",
    ):
        st.session_state.pop(name, None)
    st.session_state.open_parcel = None


reload_clicked = st.button("Reload local snapshots", key="reload")
if reload_clicked or st.session_state.catalog is None:
    with st.spinner("Checking saved local evidence…"):
        st.session_state.catalog = service.catalog()
        if st.session_state.loaded is not None:
            try:
                previous = st.session_state.loaded
                st.session_state.parcels = service.load_parcels(
                    previous.key,
                    expected_completion=previous.completion_sha256,
                )
                st.session_state.loaded = st.session_state.parcels.overview
                st.session_state.load_error = None
            except RunValidationError as exc:
                st.session_state.loaded = None
                st.session_state.parcels = None
                clear_table()
                st.session_state.load_error = str(exc)
    tokens = {entry.key.token for entry in st.session_state.catalog.entries}
    if st.session_state.get("snapshot_choice") not in tokens:
        st.session_state.snapshot_choice = None

catalog = st.session_state.catalog
for notice in catalog.notices:
    st.text(notice)
if not any(entry.eligible for entry in catalog.entries):
    st.warning("No eligible complete result is available. This is not a zero-candidate result.")
    st.text(
        "Legacy runs stay unverified. Prepare new eligible data outside this viewer; see ML-130."
    )

entries = {entry.key.token: entry for entry in catalog.entries}
choice = st.selectbox(
    "Saved result",
    options=list(entries),
    index=None,
    format_func=lambda token: entries[token].label if token in entries else "Invalid selection",
    key="snapshot_choice",
    placeholder="Choose a join or review snapshot",
)
entry = entries.get(choice)  # A widget allowlist is UX, not server-side validation.
if entry is not None:
    st.text(entry.reason)
if st.button("Load selected snapshot", key="load", disabled=entry is None or not entry.eligible):
    # Clear first: a failed load must not leave the former result looking current.
    st.session_state.loaded = None
    st.session_state.parcels = None
    st.session_state.load_error = None
    clear_table()
    try:
        with st.spinner("Validating the selected source graph…"):
            st.session_state.parcels = service.load_parcels(entry.key)
            st.session_state.loaded = st.session_state.parcels.overview
    except RunValidationError as exc:
        st.session_state.load_error = str(exc)

if st.session_state.load_error:
    st.error(st.session_state.load_error)
loaded = st.session_state.loaded
if loaded is None:
    st.info("No snapshot loaded. Choose an eligible result and select Load.")
    st.stop()

st.header("Loaded evidence")
if loaded.synthetic:
    st.warning("Synthetic test data — not actual county results.")
st.text(f"Isanti · {loaded.key.kind} · {loaded.key.run_id}")
st.caption("The loaded identity stays fixed until you explicitly load another result.")
st.text(f"Integrity validated at: {loaded.validated_at.isoformat()}")
st.caption(
    "This is an in-memory observation at that time, not continuous disk or tax verification."
)
st.text(
    f"Listing publication: {loaded.listing_publication_date or 'Unknown'} · GIS captured: {loaded.gis_captured_at.isoformat()}"
)

with st.expander("Source dates and verification"):
    st.text(f"Listing agency: {loaded.listing_agency}")
    st.text(f"Listing dataset: {loaded.listing_dataset}")
    st.text(f"Listing publication: {loaded.listing_publication_date or 'Unknown'}")
    st.text(f"Listing file captured: {loaded.listing_captured_at.isoformat()}")
    st.text(f"GIS captured: {loaded.gis_captured_at.isoformat()}")
    st.text(
        f"Report verification date: {loaded.report_verification_date or 'Unknown / not recorded'}"
    )
    st.text(f"Result completed: {loaded.created_at.isoformat()}")
    st.text(f"Manual report verification: {loaded.manual_verification}")

st.subheader("Holds and limitations")
if loaded.holds:
    st.warning("Active source hold — review the retained evidence before relying on candidates.")
    for hold in loaded.holds:
        st.text(hold)  # Source text must never become Markdown, HTML or an automatic URL fetch.
else:
    st.text(
        "No active source hold recorded. This does not establish current balances or availability."
    )
for warning in loaded.warnings:
    st.text(warning)

with st.expander("Recorded source counts and unknown fields"):
    st.text(f"Imported candidate minimum: {loaded.minimum_acres} deeded acres")
    for label, count in loaded.counts:
        st.text(f"{label}: {count:,}")
    if dict(loaded.counts)["Prior-year large parcels"] == 0:
        st.info(
            "Valid completed result with no prior-year large candidates; see holds and other counts."
        )
    st.subheader("Unknown fields in the prior-year candidate view")
    for label, count in loaded.unknown_counts:
        st.text(f"{label}: {count:,} unknown")
    st.text("Access, usable/buildable acreage, zoning, resale value and profit: not assessed.")

with st.expander("Pinned source identities"):
    st.text(f"Completion SHA-256: {loaded.completion_sha256}")
    st.text(f"Join: {loaded.join_id}")
    st.text(f"GIS: {loaded.parcel_id}")
    st.text(f"GIS source: {loaded.gis_layer}")
    st.text(f"Listing import: {loaded.import_id}")
st.caption("Reload checks local files only. No county request, replay or source edit is performed.")

st.header("Parcel research table")
dataset = st.session_state.parcels
if dataset is None or dataset.overview != loaded:
    st.error("No matching table observation is loaded. Explicitly load this snapshot again.")
    st.stop()
st.text(f"Loaded candidate floor: {dataset.minimum_acres} deeded acres")
st.caption("This is not usable or buildable acreage. Lower-acreage parcels were not loaded.")
if loaded.holds:
    st.warning(
        "Candidate browsing is withheld while an active source hold remains. Recorded issue counts stay above."
    )
st.button("Clear filters and selection", key="clear_table", on_click=clear_table)

with st.container(border=True):
    view = st.selectbox("Research view", list(VIEWS), format_func=VIEWS.get, key="table_view")
    search = st.text_input(
        "Search parcel ID, GIS owner or classification", max_chars=200, key="table_search"
    )
    with st.container(horizontal=True, vertical_alignment="bottom"):
        st.session_state.setdefault("table_min", str(dataset.minimum_acres))
        lower = st.text_input("Minimum deeded acres (inclusive)", key="table_min")
        upper = st.text_input("Maximum deeded acres (optional, inclusive)", key="table_max")
    classes = sorted(
        {
            row.property_classification
            for row in dataset.rows
            if row.property_classification is not None
        }
    )
    if any(row.property_classification is None for row in dataset.rows):
        classes.append(None)
    chosen_classes = st.multiselect(
        "Property classification (empty means all)",
        list(range(len(classes))),
        format_func=lambda index: (
            classes[index] if classes[index] is not None else "Unknown classification"
        ),
        key="table_class",
    )
    with st.container(horizontal=True, vertical_alignment="bottom"):
        improvement = st.selectbox(
            "Improvement value",
            IMPROVEMENTS,
            key="table_improvement",
            format_func=lambda value: {
                "all": "All (including unknown)",
                "known": "Known",
                "unknown": "Unknown",
                "zero": "Known zero",
                "nonzero": "Known nonzero",
            }[value],
        )
        special = st.selectbox(
            "PILT/exempt classification",
            SPECIAL,
            key="table_special",
            format_func=lambda value: {
                "all": "All (including unknown)",
                "exclude": "Known other classification",
                "only": "PILT/exempt review only",
                "unknown": "Unknown classification",
            }[value],
        )
    with st.container(horizontal=True, vertical_alignment="bottom"):
        sort = st.selectbox(
            "Sort by",
            SORTS,
            key="table_sort",
            format_func=lambda value: {
                "parcel_id": "Parcel ID",
                "deeded_acres": "Deeded acres",
                "improvement_value": "Improvement value",
                "property_classification": "Classification",
                "owner_name": "GIS owner",
            }[value],
        )
        descending = st.toggle("Descending", key="table_desc")
        size = st.selectbox("Parcels per page", [25, 50, 100], key="table_size")

try:
    if any(type(index) is not int or not 0 <= index < len(classes) for index in chosen_classes):
        raise ValueError("Choose a listed classification")
    filters = TableFilters(
        view=view,
        search=search,
        minimum_acres=number(lower) if lower.strip() else None,
        maximum_acres=number(upper) if upper.strip() else None,
        classifications=tuple(classes[index] for index in chosen_classes),
        improvement=improvement,
        special=special,
        sort=sort,
        descending=descending,
    )
    if (filters, size) != st.session_state.get("table_signature"):
        st.session_state.table_page = 1
        st.session_state.table_signature = (filters, size)
    result = query(dataset, filters, page=st.session_state.get("table_page", 1), page_size=size)
except (ValueError, TypeError) as exc:
    st.session_state.open_parcel = None
    st.session_state.parcel_choice = None
    st.error(str(exc))
    st.stop()

st.subheader("Distinct view counts under these filters")
st.caption(
    "Counts apply the search/acreage/classification/improvement/PILT filters before the research-view choice; they are not additive."
)
for name, count in result.counts:
    st.text(f"{VIEWS[name]}: {count:,}")
st.text(f"Filtered view: {len(result.filtered):,} distinct parcels")
st.session_state.table_page = result.page
page = st.number_input(
    "Results page", min_value=1, max_value=result.pages, step=1, key="table_page"
)
st.text(f"Page {page} of {result.pages}")

if not result.filtered:
    st.info(
        "No parcels match this view and filters. This does not mean the county has no delinquent parcels."
    )
else:
    # Text-valued Decimals preserve exact source precision. Enabling column-only
    # selection disables client sorting; service controls define the full order.
    # No grid row index is ever interpreted as a parcel identity.
    st.caption(
        "Use Sort by for numeric order across all pages; unknowns sort last. Header clicks select columns only. Grid download/copy is disabled; contextual exports are not available yet."
    )
    st.dataframe(
        [
            {
                "Parcel ID": row.parcel_id,
                "Deeded acres": str(row.deeded_acres) if row.deeded_acres is not None else None,
                "Classification": row.property_classification,
                "Improvement value": str(row.improvement_value)
                if row.improvement_value is not None
                else None,
                "Tax periods (dated listing)": row.periods,
                "GIS owner": row.owner_name,
            }
            for row in result.rows
        ],
        hide_index=True,
        on_select="rerun",
        selection_mode="single-column",
        lazy=False,
        key="research_grid",
        alt="Filtered saved parcel research results, current page",
    )
    st.caption(
        "Blank cells mean unknown, not zero. Zero improvement value does not establish vacancy or buildability."
    )

ids = [row.parcel_id for row in result.filtered]
if st.session_state.get("parcel_choice") not in ids:
    if st.session_state.get("parcel_choice") is not None:
        st.info("The selected parcel is outside the filtered result; selection was cleared.")
    st.session_state.parcel_choice = None
    st.session_state.open_parcel = None
if (
    st.session_state.open_parcel is not None
    and selected_row(dataset, result, st.session_state.open_parcel) is None
):
    st.session_state.open_parcel = None
if len(result.filtered) > 2000:
    st.caption(
        "Large result: the parcel selector lists this page plus any existing selection. Search to narrow the options."
    )
parcel_choice = st.selectbox(
    "Parcel ID to inspect",
    selector_ids(result, st.session_state.parcel_choice),
    index=None,
    key="parcel_choice",
    placeholder="Choose a filtered parcel",
)
if (
    st.session_state.open_parcel is not None
    and st.session_state.open_parcel.parcel_id != parcel_choice
):
    st.session_state.open_parcel = None
if st.button("Open parcel summary", key="open_summary", disabled=parcel_choice not in ids):
    st.session_state.open_parcel = select_parcel(dataset, result, parcel_choice)
identity = st.session_state.open_parcel
if identity is not None:
    row = selected_row(dataset, result, identity)
    st.subheader("Selected parcel summary")
    st.text(f"Isanti · {loaded.key.run_id} · {row.parcel_id}")
    st.text(f"Deeded acres: {row.deeded_acres if row.deeded_acres is not None else 'Unknown'}")
    st.text(
        f"Classification: {row.property_classification if row.property_classification is not None else 'Unknown'}"
    )
    st.text(
        f"Improvement value: {row.improvement_value if row.improvement_value is not None else 'Unknown'}"
    )
    st.text(f"GIS owner: {row.owner_name if row.owner_name is not None else 'Unknown'}")
    st.text(f"Dated listing categories: {row.periods}")
    st.text("Current payment status: unknown. Tax debt is not calculated here.")
    st.caption(
        "Full source rows, year evidence and official links are ML-204; this summary uses only the loaded table observation."
    )
    st.button(
        "Back to results (keep filters)",
        key="back_results",
        on_click=lambda: st.session_state.update(open_parcel=None),
    )
