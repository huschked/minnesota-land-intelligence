import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from mn_land.counties.isanti import IsantiAdapter
from mn_land.counties.isanti.delinquency import classify_assessment_years
from mn_land.delinquency.exporters import export_join_result
from mn_land.delinquency.join import join_delinquency_records
from mn_land.models import DelinquencyRecord, DelinquencyStatus, SourceMetadata, TaxPeriodStatus


@pytest.mark.parametrize(
    ("assessment", "payable", "period"),
    [("2022", 2023, TaxPeriodStatus.PRIOR_YEAR_UNPAID),
     ("2023", 2024, TaxPeriodStatus.PRIOR_YEAR_UNPAID),
     ("2024", 2025, TaxPeriodStatus.PRIOR_YEAR_UNPAID),
     ("2025", 2026, TaxPeriodStatus.OVERDUE_CURRENT_YEAR)],
)
def test_county_confirmed_year_convention(assessment, payable, period) -> None:
    assert classify_assessment_years(assessment, "2025") == (int(assessment), payable, 2026, period)


@pytest.mark.parametrize("assessment", [None, "", "2026", "2025.0", "25"])
def test_missing_or_future_year_is_not_guessed(assessment) -> None:
    with pytest.raises(ValueError):
        classify_assessment_years(assessment, "2025")


def source_record(assessment: str, row: int) -> DelinquencyRecord:
    year, payable, report_payable, status = classify_assessment_years(assessment, "2025")
    source = SourceMetadata("Isanti County", "Synthetic", "test.csv", None, datetime.now(UTC))
    return DelinquencyRecord(
        "Isanti", "020010200", "020010200", None, "Synthetic owner", None,
        (payable,) if status == TaxPeriodStatus.PRIOR_YEAR_UNPAID else None,
        None, None, None, source, row,
        {"ASMTYR": assessment, "TAXYR": "2025", "TOTAMT": "100"},
        assessment_year=year, taxes_payable_year=payable,
        report_taxes_payable_year=report_payable, tax_period_status=status,
    )


def test_multiple_years_support_status_without_aggregating_balances(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[1] / "fixtures/isanti_parcel.json"
    parcel = IsantiAdapter(client=object()).normalize_parcel(
        json.loads(fixture.read_text()), datetime.now(UTC)
    )
    records = [source_record("2023", 2), source_record("2024", 3), source_record("2025", 4)]
    result = join_delinquency_records([parcel], records)
    assert len(result.verified_matches) == 1
    assert len(result.duplicate_records["020010200"]) == 3
    outputs, count = export_join_result(result, tmp_path / "outputs", Decimal(10))
    assert count == 1
    prior = json.loads(outputs[1].read_text())[0]
    assert prior["delinquent_years"] == [2024, 2025]
    assert prior["assessment_years"] == [2023, 2024]
    assert prior["total_taxes_and_penalties_due"] is None
    assert prior["source_record_count"] == 2
    assert prior["delinquency_original_row"] is None
    assert [r["source_row_number"] for r in prior["delinquency_source_records"]] == [2, 3]
    current_path = next(p for p in outputs if p.name == "isanti_overdue_current_year_parcels.json")
    current = json.loads(current_path.read_text())[0]
    assert current["taxes_payable_years"] == [2026]
    assert current["delinquent_years"] is None
    assert current["delinquency_status"] == "overdue_current_year"
    held = join_delinquency_records([parcel], [replace(r, verification_hold_reason="Hold") for r in records])
    assert held.matches[0].status == DelinquencyStatus.UNVERIFIED
    assert not held.verified_matches
