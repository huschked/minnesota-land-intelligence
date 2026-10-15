import csv
import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from mn_land.counties.isanti import IsantiAdapter
from mn_land.delinquency.exporters import export_join_result
from mn_land.delinquency.file_loader import DelinquencyMapping, FileDelinquencySource
from mn_land.delinquency.join import join_delinquency_records


def test_real_schema_retains_raw_amounts_and_separates_periods(tmp_path: Path) -> None:
    project = Path(__file__).parents[2]
    mapping = DelinquencyMapping.from_json(
        project / "docs/counties/isanti-delinquency-2026-10-13.mapping.json"
    )
    assert "delinquent_years" not in mapping.columns
    assert mapping.tax_year_convention == "isanti_assessment_year_plus_one"
    path = tmp_path / "synthetic.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["PARID", "OWN1", "TAXYR", "ASMTYR", "TOTAMT", "EFFDATE", "LEGAL"]
        )
        writer.writeheader()
        writer.writerows([
            {
                "PARID": "020010200", "OWN1": "Synthetic owner", "TAXYR": "2025", "ASMTYR": "2024",
                "TOTAMT": "1250.50", "EFFDATE": "7-Oct-26", "LEGAL": "Line 1\nLine 2",
            },
            {"PARID": "020010201", "OWN1": "Owner A", "TAXYR": "2025", "ASMTYR": "2025"},
            {"PARID": "020010201", "OWN1": "Owner B", "TAXYR": "2025", "ASMTYR": "2025"},
        ])
    records = FileDelinquencySource(path, mapping).load_records()
    assert not any(record.verification_hold_reason for record in records)
    fixture = project / "tests/fixtures/isanti_parcel.json"
    parcel = IsantiAdapter(client=object()).normalize_parcel(
        json.loads(fixture.read_text(encoding="utf-8")), datetime.now(UTC)
    )
    result = join_delinquency_records(
        [parcel, replace(parcel, parcel_id="02.001.0201")], records
    )
    outputs, count = export_join_result(result, tmp_path / "exports", Decimal(10))
    assert count == 1
    data = json.loads(outputs[1].read_text(encoding="utf-8"))[0]
    assert data["delinquency_original_row"]["TOTAMT"] == "1250.50"
    assert data["delinquency_original_row"]["LEGAL"] == "Line 1\nLine 2"
    assert data["total_taxes_and_penalties_due"] is None
    assert data["delinquent_years"] == [2025]
    assert data["delinquency_source_metadata"]["original_identifier"] == "020010200"
    current = next(path for path in outputs if path.name == "isanti_overdue_current_year_parcels.csv")
    with current.open(encoding="utf-8", newline="") as handle:
        issues = list(csv.DictReader(handle))
    assert len(issues) == 1
    assert issues[0]["delinquency_source_row"] == "3;4"
    assert issues[0]["delinquency_status"] == "overdue_current_year"
    assert issues[0]["delinquent_years"] == ""
