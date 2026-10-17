"""Literal-text parcel evidence renderer; no disk reads or county requests."""

import streamlit as st

from mn_land.parcel_details import ParcelDetails


def display(value: object) -> str:
    return "Unknown / not recorded" if value is None else str(value)


def render_details(detail: ParcelDetails) -> None:
    st.subheader("Parcel source evidence")
    st.text(f"Evidence integrity checked at: {detail.checked_at.isoformat()}")
    st.caption(
        "A saved in-memory observation, not continuous file or payment verification. Details include all contributing periods, independent of the table's period filter."
    )
    st.text(f"Dated listing membership: {detail.parcel.periods}")
    st.text(
        "Why this research bucket: "
        + {
            "zero_improvement_value_review": "Recorded zero improvement assessment (not proof of vacancy).",
            "rural_vacant_classification_review": "Recorded rural vacant/nonproductive classification (not proof of buildability).",
            "PILT_or_exempt_review": "Recorded PILT/exempt classification requires separate review.",
            "unknown_improvement_review": "Improvement value is unknown; no vacancy conclusion.",
            "positive_improvement_value_review": "Recorded nonzero improvement value; no suitability conclusion.",
        }.get(detail.parcel.bucket, "Review the recorded property observations.")
    )
    for label, value in detail.attributes:
        st.text(f"{label}: {display(value)}")
    for warning in detail.warnings:
        st.text(warning)
    st.subheader("Dated tax-period evidence")
    for period in detail.periods:
        with st.container(border=True):
            st.text(f"Category: {period.category} · Recorded status: {period.status}")
            st.text(
                f"Charge assessment years: {', '.join(map(str, period.assessment_years)) or 'Unknown'}"
            )
            st.text(
                f"Taxes payable years: {', '.join(map(str, period.payable_years)) or 'Unknown'}"
            )
            st.text(f"Source row references: {', '.join(map(str, period.source_rows))}")
            for field, amount in period.money:
                st.text(f"Recorded canonical {field}: {display(amount)}")
            st.text(f"Balance aggregation: {period.aggregation_status}")
    st.subheader("Reviewed year convention")
    st.text(f"Convention: {display(detail.year_convention)}")
    st.text(f"Retained year-evidence document: {display(detail.year_evidence_name)}")
    st.text(f"Year-evidence SHA-256: {display(detail.year_evidence_sha256)}")
    st.caption(
        "Evidence identity is provided without serving local files or correspondence. Source dates such as EFFDATE/LTRDT are raw observations, not inferred balance-effective dates."
    )
    st.subheader("All contributing listing rows")
    st.text(
        f"Distinct source-row identities: {len(detail.rows)}. Repeated fiscal values are retained, not summed."
    )
    pages = max(1, (len(detail.rows) + 9) // 10)
    st.session_state.source_page = min(st.session_state.get("source_page", 1), pages)
    page = st.number_input(
        "Source rows page", min_value=1, max_value=pages, step=1, key="source_page"
    )
    st.text(f"Source page {page} of {pages}; 10 rows per page")
    for row in detail.rows[(page - 1) * 10 : page * 10]:
        with st.container(border=True):
            st.text(
                f"Source record: {row.number} · Sheet: {display(row.sheet)} · CSV lines: {display(row.line_start)}–{display(row.line_end)}"
            )
            st.text(
                f"Listing owner text ({row.owner_field or 'no reviewed owner mapping'}): {display(row.owner_text)}"
            )
            st.text(
                f"Charge assessment year: {display(row.assessment_year)} · Charge payable year: {display(row.payable_year)} · Report payable year: {display(row.report_payable_year)}"
            )
            st.text(f"Recorded row category: {row.period}")
            st.caption(
                "Raw source fields below — monetary abbreviations are not verified accounting definitions."
            )
            for field, value in row.fields:
                st.text(f"{field}: {display(value)}")
            if row.omitted_columns:
                st.text(
                    f"Additional unreviewed columns not displayed: {row.omitted_columns}. Retained input bytes are unchanged."
                )
    st.subheader("Parcel-specific sampled report evidence")
    if not detail.sample_findings:
        st.text(
            "No parcel-specific report comparison is retained in this selected snapshot. Historical samples elsewhere are not applied."
        )
    for finding in detail.sample_findings:
        st.text(f"Retained finding for this parcel: {finding.result}")
        st.text(f"Recorded sample payable years: {display(finding.payable_years)}")
        st.text(
            f"Recorded years match the selected prior-year set: {display(finding.aligns_with_selected_prior_years)}"
        )
        st.text(
            "This is retained sample evidence only, not independently established source-hash binding, verification of every parcel/year, or current payment status."
        )
    st.subheader("Official public references")
    st.caption(
        "Opens an external record only when clicked. Its contents may be newer than the saved snapshot; no report is embedded or fetched here."
    )
    if not detail.links:
        st.text(
            "No allowlisted public links are available for this observation. Synthetic links are disabled; local listing/evidence files are not served."
        )
    for label, url in detail.links:
        st.link_button(label, url)
    with st.expander("Saved evidence lineage"):
        for label, value in detail.source_context:
            st.text(f"{label}: {display(value)}")
