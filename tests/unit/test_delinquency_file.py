from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from mn_land.delinquency.file_loader import (
    DELINQUENCY_ASSERTION,
    DelinquencyFileError,
    DelinquencyMapping,
    FileDelinquencySource,
    inspect_delinquency_file,
    parse_money,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_csv_inspection_and_ingestion_preserve_lineage_and_nulls() -> None:
    file_path = FIXTURES / "isanti_delinquency.csv"
    mapping = DelinquencyMapping.from_json(FIXTURES / "isanti_delinquency_mapping.json")
    inspection = inspect_delinquency_file(file_path)
    record = FileDelinquencySource(file_path, mapping).load_records()[0]

    assert inspection.row_count == 1
    assert inspection.potential_mapping["parcel_id"] == "Parcel ID"
    assert record.parcel_id == "02-001-0200"
    assert record.normalized_parcel_id == "020010200"
    assert record.delinquent_years == (2025,)
    assert record.total_taxes_and_penalties_due == Decimal("1250.50")
    assert record.delinquent_tax_amount is None
    assert record.penalty_amount is None
    assert record.source_row_number == 2
    assert record.source_metadata.original_identifier == "02-001-0200"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("$1,250.50", Decimal("1250.50")),
        ("1250.50", Decimal("1250.50")),
        ("1,250", Decimal(1250)),
        (None, None),
        ("  ", None),
    ],
)
def test_money_parsing(raw: object, expected: Decimal | None) -> None:
    assert parse_money(raw) == expected


def test_xlsx_inspection_and_ingestion(tmp_path: Path) -> None:
    path = tmp_path / "official.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Parcel ID", "Taxpayer", "Delinquent Year", "Taxes/Penalties"])
    sheet.append(["01.001.0201", None, 2025, 1250.5])
    workbook.save(path)
    mapping = DelinquencyMapping(
        source_agency="Isanti County Auditor-Treasurer",
        dataset="Test",
        columns={
            "parcel_id": "Parcel ID",
            "taxpayer_name": "Taxpayer",
            "delinquent_years": "Delinquent Year",
            "total_taxes_and_penalties_due": "Taxes/Penalties",
        },
        delinquency_assertion=DELINQUENCY_ASSERTION,
    )
    inspection = inspect_delinquency_file(path)
    record = FileDelinquencySource(path, mapping).load_records()[0]
    assert inspection.file_type == "xlsx"
    assert record.taxpayer_name is None
    assert record.total_taxes_and_penalties_due == Decimal("1250.5")


def test_unsupported_file_and_missing_mapped_column_fail(tmp_path: Path) -> None:
    bad = tmp_path / "list.pdf"
    bad.write_bytes(b"not a supported import")
    with pytest.raises(DelinquencyFileError, match="unsupported"):
        inspect_delinquency_file(bad)
    mapping = DelinquencyMapping(
        "Isanti County", "Test", {"parcel_id": "Wrong Column"}, DELINQUENCY_ASSERTION
    )
    with pytest.raises(DelinquencyFileError, match="absent"):
        FileDelinquencySource(FIXTURES / "isanti_delinquency.csv", mapping).load_records()
