"""Optional explicitly bound suitability evidence. No hidden disk/network reads."""
import json
from dataclasses import dataclass
from queue import SimpleQueue
from threading import Event

import streamlit as st

from mn_land.parcel_table import ParcelDataset, TableFilters
from mn_land.runs import RunValidationError
from mn_land.suitability_service import (
    SuitabilityObservation,
    SuitabilityPreview,
    SuitabilityService,
)


def clear_preview() -> None:
    if event := st.session_state.get("suit_revoked"):
        event.set()
    st.session_state.suit_preview = None
    st.session_state.suit_revoked = None


def clear_suitability() -> None:
    clear_preview()
    st.session_state.suit_loaded = None
    st.session_state.suit_error = None


def check_errors() -> None:
    errors = st.session_state.suit_errors
    while not errors.empty():
        event, message = errors.get_nowait()
        if event is st.session_state.suit_revoked:
            clear_suitability()
            st.session_state.suit_error = message


def render_selector(service: SuitabilityService, dataset: ParcelDataset) -> SuitabilityObservation | None:
    key = (dataset.overview.key, dataset.overview.completion_sha256)
    if st.session_state.get("suit_base") != key:
        clear_suitability()
        st.session_state.suit_base = key
        st.session_state.suit_catalog = None
        st.session_state.suit_choice = None
    if st.session_state.suit_catalog is None:
        try:
            st.session_state.suit_catalog = service.catalog()
        except RunValidationError as exc:
            st.session_state.suit_catalog = ()
            st.session_state.suit_error = str(exc)
    st.subheader("Optional saved suitability evidence")
    st.caption(
        "No suitability snapshot is selected automatically. Names below are unvalidated until Load. "
        "Loading reproduces the saved GIS evidence offline and may take time; filters reuse the loaded observation."
    )
    choice = st.selectbox("Saved suitability publication", st.session_state.suit_catalog,
                          index=None, key="suit_choice", placeholder="Choose compatible saved suitability")
    if st.button("Load suitability evidence", key="suit_load", disabled=choice is None):
        clear_suitability()
        try:
            with st.spinner("Reproducing saved suitability and binding candidate evidence…"):
                st.session_state.suit_loaded = service.load(choice, dataset)
        except RunValidationError as exc:
            st.session_state.suit_error = str(exc)
    if st.session_state.suit_error:
        st.error(st.session_state.suit_error)
    observation = st.session_state.suit_loaded
    if observation is not None:
        payload = observation.payload()
        counts = {status: sum(r["status"] == status for r in payload["records"])
                  for status in ("complete", "held")}
        st.text(f"Loaded suitability: {observation.run_id} · {counts['complete']} numeric · {counts['held']} held")
        if payload["context"]["map_review"]["method"] == "synthetic_fixture":
            st.warning("Synthetic suitability/map-review fixture — not actual county evidence.")
        st.caption("This is an in-memory observation, not continuous disk or current property-condition verification.")
        st.text("Estimated remaining acres follow a mapped-constraint policy, not legal buildability.")
    else:
        st.info("Suitability not loaded. Tax-snapshot acreage is deeded acreage, not assessed usable land.")
    return observation


def cells(observation: SuitabilityObservation | None, identity: str) -> dict:
    if observation is None:
        return {}
    record = observation.record(identity)
    return {"Suitability status": record["status"] if record else "not_assessed",
            "Measured GIS acres": record["measured_acres"] if record else None,
            "Estimated remaining acres": record["estimated_remaining_acres"] if record else None}


def render_details(observation: SuitabilityObservation | None, identity: str) -> None:
    if observation is None:
        return
    record = observation.record(identity)
    st.subheader("Mapped suitability evidence")
    if record is None:
        st.info("Not assessed by this suitability snapshot. No zero constraint or remaining-acre value is inferred.")
        return
    if record["status"] == "held":
        st.warning("Held suitability: combined and remaining acres are unknown, not zero.")
        for reason in record["holds"]:
            st.text(reason)
        st.caption("A zero geometric evidence gap does not override panel/date/classification holds.")
    for name in ("measured_acres", "saved_deeded_acres", "new_gis_deeded_acres", "mapped_wetland_acres",
                 "mapped_water_acres", "sfha_acres", "floodway_acres", "annual_chance_0_2pct_acres",
                 "combined_constraint_acres", "shared_water_sfha_acres", "estimated_remaining_acres", "evidence_gap_m2"):
        value = record[name]
        st.text(f"{name}: {value if value is not None else 'Unknown / held'}")
    context = observation.payload()["context"]
    st.text("Shared water/SFHA area is counted once. Deepwater/riverine are distinct water constraints.")
    st.text("Wetland imagery/delivery and flood panel/study dates (raw invalid dates remain unknown):")
    for name in ("wetland_project_contexts", "flood_panel_contexts", "flood_study_contexts"):
        st.text(f"{name}: {json.dumps(record[name], ensure_ascii=False)}")
    with st.expander("Suitability lineage, policy and map-review limits"):
        st.text(f"Suitability completion SHA-256: {observation.completion_sha256}")
        st.text(f"Constraint run: {context['constraint_run_id']} · {context['constraint_completion_sha256']}")
        st.text(json.dumps(context["source_dates"], ensure_ascii=False))
        st.text(json.dumps(context["constraint_policy"], ensure_ascii=False))
        st.text(context["map_review"]["findings"])
        if limits := context["map_review"].get("tolerances_and_limits"):
            st.text(json.dumps(limits, ensure_ascii=False))
        for warning in context["warnings"]:
            st.text(warning)


@dataclass(frozen=True)
class SuitabilityDownload:
    service: SuitabilityService
    preview: SuitabilityPreview
    format: str
    revoked: Event
    errors: SimpleQueue

    def __call__(self) -> bytes:
        try:
            if self.revoked.is_set():
                raise RunValidationError("Suitability preview expired; preview again")
            body = self.service.download(self.preview, self.format)
            if self.revoked.is_set():
                raise RunValidationError("Suitability preview expired during download")
            return body
        except RunValidationError as exc:
            self.errors.put((self.revoked, str(exc)))
            raise


def render_exports(service: SuitabilityService, observation: SuitabilityObservation | None,
                   dataset: ParcelDataset, filters: TableFilters) -> None:
    if observation is None:
        clear_preview()
        return
    st.header("Suitability export")
    scope = st.selectbox("Suitability export scope", ("filtered", "selected"),
                         format_func=lambda v: "All filtered parcels" if v == "filtered" else "Selected parcel only",
                         key="suit_scope")
    selected = st.session_state.get("parcel_choice") if scope == "selected" else None
    signature = (observation, dataset.overview.key, dataset.overview.completion_sha256, filters, scope, selected)
    if st.session_state.get("suit_signature") != signature:
        clear_preview()
        st.session_state.suit_signature = signature
    if st.button("Preview suitability export", key="suit_preview_button",
                 disabled=scope == "selected" and selected is None):
        clear_preview()
        try:
            with st.spinner("Revalidating suitability export…"):
                st.session_state.suit_preview = service.prepare(observation, dataset, filters,
                                                               scope=scope, selected=selected)
            st.session_state.suit_revoked = Event()
        except RunValidationError as exc:
            clear_suitability()
            st.session_state.suit_error = str(exc)
            st.rerun()
    preview = st.session_state.suit_preview
    if preview is None:
        st.info("Preview first. Filters, selection, scope, reload or evidence changes revoke the preview. Downloads revalidate on click.")
        return
    payload = json.loads(preview.document)
    for status in ("complete", "held", "not_assessed"):
        st.text(f"Export {status}: {sum(r['status'] == status for r in payload['records'])}")
    st.text(payload["context"]["csv_import_note"])
    st.text("CSV \\N and JSON null mean unknown, never zero. JSON preserves canonical value types.")
    st.text(f"Preview fingerprint: {preview.fingerprint}")
    for format in ("csv", "json"):
        st.download_button(f"Download suitability {format.upper()}",
            data=SuitabilityDownload(service, preview, format, st.session_state.suit_revoked,
                                     st.session_state.suit_errors),
            file_name=f"isanti-suitability-{observation.run_id}-{preview.fingerprint[:12]}.{format}",
            mime="text/csv" if format == "csv" else "application/json",
            key=f"suit_download_{format}_{preview.fingerprint}", on_click="rerun")
    st.button("Check suitability export status", key="suit_export_status")
