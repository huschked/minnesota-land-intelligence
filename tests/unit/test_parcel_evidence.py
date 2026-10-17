"""U05-U07: source lineage, year distinctions, no sums and strict county URLs."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO

import pytest

from mn_land.config.input_limits import InputLimits
from mn_land.counties.isanti.evidence import REPORT_BASE, public_link, report_link
from mn_land.counties.isanti.mappings import SERVICE_URL
from mn_land.delinquency.errors import DelinquencyFileError
from mn_land.delinquency.tabular import SourceRow, read_table_bytes
from mn_land.parcel_details import project_details
from mn_land.parcel_table import ParcelIdentity, ParcelRow

PIN = "02.001.0200"
GOOD = f"{REPORT_BASE}?PIN={PIN}"


@pytest.fixture
def evidence():
    raw = [
        SourceRow(
            {
                "PARID": "020010200",
                "OWN1": "Listing A",
                "ASMTYR": "2024",
                "TAXYR": "2025",
                "TOTAMT": "100",
                "PRIVATE_EXTRA": "C:/do-not-display",
            },
            2,
            line_start=2,
            line_end=2,
        ),
        SourceRow(
            {
                "PARID": "020010200",
                "OWN1": "Listing B",
                "ASMTYR": "2024",
                "TAXYR": "2025",
                "TOTAMT": "100",
            },
            3,
            line_start=3,
            line_end=3,
        ),
        SourceRow(
            {
                "PARID": "020010200",
                "OWN1": "Listing A",
                "ASMTYR": "2025",
                "TAXYR": "2025",
                "TOTAMT": "0",
            },
            4,
            line_start=4,
            line_end=4,
        ),
    ]

    def record(row):
        year = int(row.values["ASMTYR"])
        return {
            "source_row_number": row.number,
            "source_metadata": {"source_sheet": row.sheet},
            "original_row": deepcopy(row.values),
            "assessment_year": year,
            "taxes_payable_year": year + 1,
            "tax_period_status": "prior_year_unpaid" if year < 2025 else "overdue_current_year",
        }

    base = {
        "parcel_id": PIN,
        "owner_mailing_address": None,
        "land_value": "150000",
        "improvement_value": "0",
        "assessed_value": None,
        "legal_description": "Literal GIS legal text",
        "delinquent_tax_amount": None,
        "penalty_amount": None,
        "total_taxes_and_penalties_due": None,
        "balance_aggregation_status": "unaggregated_source_observations",
    }
    prior = {
        **base,
        "delinquency_status": "verified_delinquent",
        "assessment_years": [2024],
        "taxes_payable_years": [2025],
        "delinquency_source_records": [record(row) for row in raw[:2]],
    }
    current = {
        **base,
        "delinquency_status": "overdue_current_year",
        "assessment_years": [2025],
        "taxes_payable_years": [2026],
        "delinquency_source_records": [record(raw[2])],
    }
    return {
        "identity": ParcelIdentity("Isanti", "review/saved", "a" * 64, PIN),
        "parcel": ParcelRow(
            PIN,
            Decimal(25),
            "Other",
            Decimal(0),
            "GIS owner",
            True,
            True,
            "zero_improvement_value_review",
        ),
        "prior": [prior],
        "current": [current],
        "source_rows": raw,
        "mapping": {
            "columns": {"parcel_id": "PARID", "owner_name": "OWN1"},
            "tax_year_convention": "isanti_assessment_year_plus_one",
        },
        "context": (("Run", "saved"),),
        "gis_url": f"{SERVICE_URL}/0",
        "checked_at": datetime(2026, 10, 17, tzinfo=UTC),
        "synthetic": False,
        "year_evidence": ("years.md", "b" * 64),
    }


def test_rows_years_owners_unknowns_and_repeat_values_remain_separate(evidence):
    detail = project_details(**evidence)
    assert [row.number for row in detail.rows] == [2, 3, 4]
    assert [row.owner_text for row in detail.rows] == ["Listing A", "Listing B", "Listing A"]
    assert detail.parcel.owner_name == "GIS owner"
    assert [
        (row.assessment_year, row.payable_year, row.report_payable_year) for row in detail.rows
    ] == [(2024, 2025, 2026), (2024, 2025, 2026), (2025, 2026, 2026)]
    assert all(amount is None for period in detail.periods for _, amount in period.money)
    assert dict(detail.rows[2].fields)["TOTAMT"] == "0"
    assert detail.rows[0].omitted_columns == 1
    assert "C:/do-not-display" not in repr(detail)
    assert len(detail.links) == 2
    assert not detail.sample_findings
    with pytest.raises(FrozenInstanceError):
        detail.identity = None


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "raw_changed",
        "year_changed",
        "duplicate_id",
        "money_claim",
        "extra_money",
        "duplicate_reference",
        "summary_years",
        "duplicate_years",
    ],
)
def test_incomplete_conflicting_or_promoted_evidence_fails_closed(evidence, change):
    if change == "missing":
        evidence["prior"][0]["delinquency_source_records"].pop()
    elif change == "raw_changed":
        evidence["prior"][0]["delinquency_source_records"][0]["original_row"]["TOTAMT"] = "101"
    elif change == "year_changed":
        evidence["prior"][0]["delinquency_source_records"][0]["taxes_payable_year"] = 2030
    elif change == "duplicate_id":
        evidence["prior"] *= 2
    elif change == "money_claim":
        evidence["prior"][0]["total_taxes_and_penalties_due"] = "200"
    elif change == "duplicate_reference":
        records = evidence["prior"][0]["delinquency_source_records"]
        records.append(deepcopy(records[0]))
    elif change == "summary_years":
        evidence["prior"][0]["assessment_years"] = [2023]
    elif change == "duplicate_years":
        evidence["prior"][0]["taxes_payable_years"] = [2025, 2025]
    else:
        evidence["current"][0]["penalty_amount"] = "0"  # unknown mapping is not a known zero
    with pytest.raises(ValueError):
        project_details(**evidence)


def test_synthetic_no_public_links_and_sample_only_selected_parcel_and_years(evidence):
    evidence["synthetic"] = True
    evidence["comparison"] = {
        "findings": [
            {
                "parcel_id": "020010200",
                "verification_result": "positive_outstanding_for_listed_prior_year",
                "listed_taxes_payable_years": "2025",
                "county_report_pdf": "C:/private/report.pdf",
            },
            {
                "parcel_id": "020010201",
                "verification_result": "other",
                "listed_taxes_payable_years": "2025",
            },
        ]
    }
    detail = project_details(**evidence)
    assert not detail.links
    assert len(detail.sample_findings) == 1
    assert detail.sample_findings[0].payable_years == (2025,)
    assert detail.sample_findings[0].aligns_with_selected_prior_years is True
    assert "C:/private" not in repr(detail)
    assert any("verification date" in warning for warning in detail.warnings)
    evidence["comparison"]["findings"][0]["listed_taxes_payable_years"] = "2023"
    assert project_details(**evidence).sample_findings[0].aligns_with_selected_prior_years is False


def test_source_sheet_locations_and_reviewed_single_mapped_amount(evidence):
    evidence["source_rows"] = [
        replace(evidence["source_rows"][2], sheet="County sheet", line_start=None, line_end=None)
    ]
    evidence["prior"] = []
    record = evidence["current"][0]["delinquency_source_records"][0]
    record["source_metadata"]["source_sheet"] = "County sheet"
    evidence["mapping"]["columns"]["penalty_amount"] = "TOTAMT"
    evidence["current"][0]["penalty_amount"] = "0"
    detail = project_details(**evidence)
    assert detail.rows[0].sheet == "County sheet"
    assert dict(detail.periods[0].money)["penalty_amount"] == Decimal(0)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "file:///C:/secret",
        "http://gis.co.isanti.mn.us/ParcelReports/PublicParcelReport.ashx?PIN=020010200",
        "https://gis.co.isanti.mn.us.evil.test/ParcelReports/PublicParcelReport.ashx?PIN=020010200",
        "https://gis.co.isanti.mn.us@evil.test/ParcelReports/PublicParcelReport.ashx?PIN=020010200",
        "https://u:p@gis.co.isanti.mn.us/ParcelReports/PublicParcelReport.ashx?PIN=020010200",
        "https://gis.co.isanti.mn.us:443/ParcelReports/PublicParcelReport.ashx?PIN=020010200",
        f"{REPORT_BASE}?PIN=020010201",
        f"{REPORT_BASE}?PIN=020010200&extra=x",
        f"{REPORT_BASE}?PIN=020010200&PIN=020010200",
        f"{REPORT_BASE}?PIN=%3002010200",
        f"{REPORT_BASE}?PIN=020010200#x",
        GOOD + "\n",
        "//gis.co.isanti.mn.us/ParcelReports/PublicParcelReport.ashx?PIN=020010200",
        "https://gis.co.isanti.mn.us/../private?PIN=020010200",
        SERVICE_URL + "/0?f=json",
        "https://gis.co.isanti.mn.us\\evil.test/ParcelReports/PublicParcelReport.ashx?PIN=020010200",
        None,
    ],
)
def test_external_url_allowlist_rejects_unsafe_or_unbound_destinations(url):
    assert public_link(url, PIN) is None


def test_only_exact_reviewed_report_and_layer_links_are_allowed():
    assert public_link(GOOD, PIN) == GOOD
    assert report_link(PIN) == GOOD
    assert public_link(SERVICE_URL + "/0", PIN) == SERVICE_URL + "/0"


def test_captured_byte_table_reader_preserves_csv_rows_and_enforces_budget():
    body = b'PARID,OWN1\n020010200,"line one\nline two"\n'
    _, rows = read_table_bytes(body, ".csv")
    assert rows[0].values["PARID"] == "020010200"
    assert rows[0].line_start == 2 and rows[0].line_end == 3
    with pytest.raises(DelinquencyFileError, match="max_file_bytes"):
        read_table_bytes(body, ".csv", replace(InputLimits(), max_file_bytes=2))


def test_captured_xlsx_bytes_are_values_only_and_keep_sheet_row_identity():
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = "County sheet"
    sheet.append(["PARID", "OWN1"])
    sheet.append(["020010200", "=1+1"])
    buffer = BytesIO()
    book.save(buffer)
    with pytest.raises(DelinquencyFileError, match="values-only"):
        read_table_bytes(buffer.getvalue(), ".xlsx")
    sheet["B2"] = "Literal owner"
    buffer = BytesIO()
    book.save(buffer)
    _, rows = read_table_bytes(buffer.getvalue(), ".xlsx")
    assert rows[0].sheet == "County sheet" and rows[0].number == 2
    assert rows[0].values["OWN1"] == "Literal owner"
