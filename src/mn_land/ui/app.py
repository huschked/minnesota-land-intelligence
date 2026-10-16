"""ML-202 selector shell. Run through mn-land-viewer for enforced local settings."""
import streamlit as st

from mn_land.config import settings
from mn_land.review_service import ReviewService
from mn_land.runs import RunValidationError

st.set_page_config(page_title="Minnesota land review", layout="centered")
st.title("Minnesota land review")
st.caption("Read-only saved evidence · Snapshot selector")
st.text("Choose a saved result to inspect its source dates, counts and limitations.")
st.caption("Parcel tables, filters, details and contextual exports are not built yet.")

service = ReviewService(settings.SETTINGS.processed_dir)
st.session_state.setdefault("catalog", None)
st.session_state.setdefault("loaded", None)
st.session_state.setdefault("load_error", None)

reload_clicked = st.button("Reload local snapshots", key="reload")
if reload_clicked or st.session_state.catalog is None:
    with st.spinner("Checking saved local evidence…"):
        st.session_state.catalog = service.catalog()
        if st.session_state.loaded is not None:
            try:
                st.session_state.loaded = service.revalidate(st.session_state.loaded)
                st.session_state.load_error = None
            except RunValidationError as exc:
                st.session_state.loaded = None
                st.session_state.load_error = str(exc)
    tokens = {entry.key.token for entry in st.session_state.catalog.entries}
    if st.session_state.get("snapshot_choice") not in tokens:
        st.session_state.snapshot_choice = None

catalog = st.session_state.catalog
for notice in catalog.notices:
    st.text(notice)
if not any(entry.eligible for entry in catalog.entries):
    st.warning("No eligible complete result is available. This is not a zero-candidate result.")
    st.text("Legacy runs stay unverified. Prepare new eligible data outside this viewer; see ML-130.")

entries = {entry.key.token: entry for entry in catalog.entries}
choice = st.selectbox(
    "Saved result", options=list(entries), index=None,
    format_func=lambda token: entries[token].label if token in entries else "Invalid selection",
    key="snapshot_choice", placeholder="Choose a join or review snapshot",
)
entry = entries.get(choice)  # A widget allowlist is UX, not server-side validation.
if entry is not None:
    st.text(entry.reason)
if st.button("Load selected snapshot", key="load", disabled=entry is None or not entry.eligible):
    # Clear first: a failed load must not leave the former result looking current.
    st.session_state.loaded = None
    st.session_state.load_error = None
    try:
        with st.spinner("Validating the selected source graph…"):
            st.session_state.loaded = service.load(entry.key)
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
st.caption("This is an in-memory observation at that time, not continuous disk or tax verification.")
st.text(f"Completion SHA-256: {loaded.completion_sha256}")

with st.container(border=True):
    st.subheader("Source dates")
    st.text(f"Listing agency: {loaded.listing_agency}")
    st.text(f"Listing dataset: {loaded.listing_dataset}")
    st.text(f"Listing publication: {loaded.listing_publication_date or 'Unknown'}")
    st.text(f"Listing file captured: {loaded.listing_captured_at.isoformat()}")
    st.text(f"GIS captured: {loaded.gis_captured_at.isoformat()}")
    st.text(f"Report verification date: {loaded.report_verification_date or 'Unknown / not recorded'}")
    st.text(f"Result completed: {loaded.created_at.isoformat()}")
    st.text(f"Manual report verification: {loaded.manual_verification}")

st.subheader("Holds and limitations")
if loaded.holds:
    st.warning("Active source hold — review the retained evidence before relying on candidates.")
    for hold in loaded.holds:
        st.text(hold)  # Source text must never become Markdown, HTML or an automatic URL fetch.
else:
    st.text("No active source hold recorded. This does not establish current balances or availability.")
for warning in loaded.warnings:
    st.text(warning)

with st.container(border=True):
    st.subheader("Recorded counts")
    st.text(f"Imported candidate minimum: {loaded.minimum_acres} deeded acres")
    for label, count in loaded.counts:
        st.text(f"{label}: {count:,}")
    if dict(loaded.counts)["Prior-year large parcels"] == 0:
        st.info("Valid completed result with no prior-year large candidates; see holds and other counts.")
    st.subheader("Unknown fields in the prior-year candidate view")
    for label, count in loaded.unknown_counts:
        st.text(f"{label}: {count:,} unknown")
    st.text("Access, usable/buildable acreage, zoning, resale value and profit: not assessed.")

st.subheader("Pinned source identities")
st.text(f"Join: {loaded.join_id}")
st.text(f"GIS: {loaded.parcel_id}")
st.text(f"GIS source: {loaded.gis_layer}")
st.text(f"Listing import: {loaded.import_id}")
st.caption("Reload checks local files only. No county request, replay or source edit is performed.")
