"""Explicit worklist previews and click-time validated deferred downloads."""

from dataclasses import dataclass
from queue import SimpleQueue
from threading import Event

import streamlit as st

from mn_land.parcel_table import ParcelDataset, TableFilters, query, select_parcel
from mn_land.review_service import ReviewService
from mn_land.runs import RunValidationError
from mn_land.worklists import CSV_POLICY, Worklist


@dataclass(frozen=True)
class DownloadJob:
    service: ReviewService
    preview: Worklist
    format: str
    revoked: Event
    errors: SimpleQueue

    def __call__(self) -> bytes:
        # Streamlit invokes data callables on a separate thread. Do not read or
        # mutate session state there; captured immutable requests + Event/Queue only.
        try:
            if self.revoked.is_set():
                raise RunValidationError("Preview expired. Preview the current selection again.")
            body = self.service.download_export(self.preview, self.format)
            if self.revoked.is_set():
                raise RunValidationError("Preview expired during download; no file supplied.")
            return body
        except RunValidationError as exc:
            self.errors.put((self.revoked, str(exc)))
            raise


def clear_export() -> None:
    revoked = st.session_state.get("export_revoked")
    if revoked is not None:
        revoked.set()
    st.session_state.export_preview = None
    st.session_state.export_revoked = None


def check_export_errors() -> str | None:
    errors = st.session_state.export_errors
    active = st.session_state.export_revoked
    message = None
    while not errors.empty():
        revoked, error = errors.get_nowait()
        if active is not None and revoked is active:
            message = error
    return message


def render_worklists(service: ReviewService, dataset: ParcelDataset, filters: TableFilters) -> None:
    st.header("Research worklist export")
    st.caption(
        "Export all filtered parcels across pages or the selected parcel. Snapshot-wide issues/accounting entries are included separately, regardless of candidate filters; they are not purchase candidates."
    )
    scope = st.selectbox(
        "Candidate export scope",
        ("filtered", "selected"),
        format_func=lambda value: (
            "All filtered parcels" if value == "filtered" else "Selected parcel only"
        ),
        key="export_scope",
    )
    result = query(dataset, filters)
    choice = st.session_state.get("parcel_choice")
    identity = None
    if scope == "selected" and any(row.parcel_id == choice for row in result.filtered):
        identity = select_parcel(dataset, result, choice)
    signature = (
        dataset.overview.key,
        dataset.overview.completion_sha256,
        filters,
        scope,
        identity,
        choice,
    )
    if signature != st.session_state.get("export_signature"):
        clear_export()
        st.session_state.export_signature = signature
        st.session_state.issue_page = 1
    if st.button(
        "Preview contextual export",
        key="preview_export",
        disabled=scope == "selected" and identity is None,
    ):
        clear_export()
        try:
            with st.spinner("Revalidating saved worklist and issue evidence…"):
                st.session_state.export_preview = service.prepare_export(
                    dataset, filters, scope=scope, identity=identity
                )
            st.session_state.export_revoked = Event()
            st.session_state.issue_page = 1
        except RunValidationError as exc:
            st.session_state.loaded = None
            st.session_state.parcels = None
            st.session_state.open_parcel = None
            st.session_state.parcel_details = None
            st.session_state.load_error = str(exc)
            st.rerun()
    preview = st.session_state.export_preview
    if preview is None:
        st.info(
            "Preview first. Changing filters, sort, scope, selection or loaded evidence invalidates the previous preview. Paging does not change the exported set."
        )
        return
    payload = preview.payload()
    context = payload["context"]
    st.text(f"Candidate parcels to export: {context['candidate_count']}")
    st.text(f"Snapshot-wide issue/accounting entries: {context['issue_row_count']}")
    st.text(f"Snapshot: {context['snapshot']} · SHA-256: {context['completion_sha256']}")
    st.text(f"Preview fingerprint: {preview.fingerprint}")
    st.text(f"Preview integrity checked at: {preview.checked_at.isoformat()}")
    st.text(
        f"Candidate scope: {scope} · Selected ID: {context['selected_parcel_id'] or 'not applicable'}"
    )
    st.text(f"Filters and service order: {context['filters']}")
    st.text(context["ordering"])
    for field in (
        "listing_publication_date",
        "listing_captured_at",
        "GIS_captured_at",
        "report_verification_date",
    ):
        st.text(f"{field}: {context[field] or 'Unknown / not recorded'}")
    for warning in context["holds"] + context["warnings"]:
        st.text(warning)
    st.text(CSV_POLICY)
    st.caption(
        "Both formats contain context, distinct candidate records and separate issues. Downloads revalidate again on click. If refused, no stale file is supplied; Reload and preview again. Check export status to display a deferred error."
    )
    with st.expander("Preview candidate order (first 10 IDs)"):
        for row in payload["candidates"][:10]:
            st.text(row["parcel_id"])
    with st.expander("Snapshot-wide issues and source accounting"):
        st.text(
            f"Entry counts (overlapping categories, not unique parcels): {context['issue_counts']}"
        )
        st.caption(
            "Saved CSV issue blanks become null; other issue CSV values remain source text. Full diagnostic reasons/paths are withheld; artifact name and record ordinal identify retained evidence."
        )
        issues = payload["issues"]
        pages = max(1, (len(issues) + 24) // 25)
        st.session_state.issue_page = min(st.session_state.get("issue_page", 1), pages)
        page = st.number_input(
            "Issue entries page", min_value=1, max_value=pages, step=1, key="issue_page"
        )
        for issue in issues[(page - 1) * 25 : page * 25]:
            with st.container(border=True):
                st.text(
                    f"{issue['kind']} · {issue['artifact']} · saved record {issue['record_ordinal']}"
                )
                for field, value in issue["fields"].items():
                    st.text(f"{field}: {value if value is not None else 'Unknown / not recorded'}")
    for format in ("csv", "json"):
        st.download_button(
            f"Download contextual {format.upper()}",
            data=DownloadJob(
                service,
                preview,
                format,
                st.session_state.export_revoked,
                st.session_state.export_errors,
            ),
            file_name=f"isanti-research-{dataset.overview.key.run_id}-{preview.fingerprint[:12]}.{format}",
            mime="text/csv" if format == "csv" else "application/json",
            key=f"download_{format}_{preview.fingerprint}",
            on_click="rerun",
        )
    st.button("Check export status", key="export_status")
