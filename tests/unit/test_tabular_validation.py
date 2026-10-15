"""F04-F09: bounded CSV/XLSX formats and trustworthy row locations."""

import builtins
import hashlib
import json
import re
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from openpyxl import Workbook

from mn_land.config.input_limits import InputLimits
from mn_land.delinquency.file_loader import (
    DELINQUENCY_ASSERTION,
    MIXED_UNPAID_ASSERTION,
    DelinquencyFileError,
    DelinquencyMapping,
    FileDelinquencySource,
    read_tabular_file,
)
from mn_land.delinquency.tabular import read_table


def mapping() -> DelinquencyMapping:
    return DelinquencyMapping(
        "Isanti County",
        "Synthetic",
        {
            "parcel_id": "ID",
            "total_taxes_and_penalties_due": "Due",
        },
        DELINQUENCY_ASSERTION,
    )


def book(path: Path, rows: list[list]) -> Path:
    workbook = Workbook()
    for values in rows:
        workbook.active.append(values)
    workbook.save(path)
    workbook.close()
    return path


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"ID,Due\n",
        b"ID,ID\na,b\n",
        b" ID ,ID\na,b\n",
        b",Due\na,b\n",
        b"ID,Due\n020010200\n",
        b"ID,Due\n020010200,1,extra\n",
        b'ID,Due\n"unfinished',
        b"ID,Due\n020010200,\xff\n",
    ],
)
def test_F04_bad_CSV_is_a_domain_error(tmp_path, body) -> None:
    path = tmp_path / "source.csv"
    path.write_bytes(body)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(DelinquencyFileError):
        read_table(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_F04_BOM_quotes_multiline_and_blank_rows_keep_lineage(tmp_path) -> None:
    path = tmp_path / "source.CSV"
    path.write_text(
        '\ufeff ID ,Owner,Due\n020010200,"A, B\nC",\n\n020010201,Other,0\n',
        encoding="utf-8",
        newline="",
    )
    columns, rows = read_table(path)
    assert columns == ("ID", "Owner", "Due")
    assert rows[0].values["Owner"] == "A, B\nC"
    assert (rows[0].number, rows[0].line_start, rows[0].line_end) == (2, 2, 3)
    assert (rows[1].number, rows[1].line_start, rows[1].line_end) == (4, 5, 5)
    records = FileDelinquencySource(path, mapping()).load_records()
    assert records[0].normalized_parcel_id == "020010200"
    assert records[0].total_taxes_and_penalties_due is None
    assert records[1].source_row_number == 4
    assert records[1].total_taxes_and_penalties_due == 0
    assert records[0].source_metadata.source_line_end == 3


@pytest.mark.parametrize("identity", [20010200, 20010200.0, 1.234e8, True])
def test_F05_XLSX_numeric_identifiers_are_rejected_even_with_padding_format(
    tmp_path, identity
) -> None:
    path = tmp_path / "source.xlsx"
    workbook = Workbook()
    workbook.active.append(["ID", "Due"])
    workbook.active.append([identity, 100])
    workbook.active["A2"].number_format = "000000000"
    workbook.save(path)
    workbook.close()
    with pytest.raises(DelinquencyFileError, match="text"):
        FileDelinquencySource(path, mapping()).load_records()


def test_F06_mixed_typed_years_and_F07_blank_sheet_rows(tmp_path) -> None:
    path = book(
        tmp_path / "source.xlsx",
        [
            ["ID", "Due", "ASMTYR", "TAXYR"],
            ["020010200", 125.5, 2024, 2025],
            [None, None, None, None],
            ["020010201", None, 2025, 2025],
        ],
    )
    mixed = replace(
        mapping(),
        delinquency_assertion=MIXED_UNPAID_ASSERTION,
        tax_year_convention="isanti_assessment_year_plus_one",
        year_semantics_reference="note.md",
        supporting_documents=("note.md",),
    )
    records = FileDelinquencySource(path, mixed).load_records()
    assert records[0].taxes_payable_year == 2025
    assert records[0].total_taxes_and_penalties_due == Decimal("125.5")
    assert records[1].source_row_number == 4
    assert records[1].source_metadata.source_sheet == "Sheet"
    assert records[1].tax_period_status.value == "overdue_current_year"
    assert records[0].original_row["ASMTYR"] == 2024
    json.dumps(records[0].source_metadata.to_dict())


@pytest.mark.parametrize("value", ["=100+25", "#DIV/0!"])
def test_F07_formulas_and_errors_are_not_silently_null(tmp_path, value) -> None:
    path = book(tmp_path / "source.xlsx", [["ID", "Due"], ["020010200", value]])
    with pytest.raises(DelinquencyFileError, match="formula/error"):
        read_table(path)


def test_F07_cached_formula_is_also_rejected(tmp_path) -> None:
    original = book(tmp_path / "original.xlsx", [["ID", "Due"], ["020010200", "=100+25"]])
    source = BytesIO(original.read_bytes())
    path = tmp_path / "cached.xlsx"
    with ZipFile(source) as archive, ZipFile(path, "w") as output:
        for name in archive.namelist():
            content = archive.read(name)
            if name == "xl/worksheets/sheet1.xml":
                content = re.sub(rb"<v\s*(?:/>|>\s*</v>)", b"<v>125</v>", content)
                assert b"<v>125</v>" in content
            output.writestr(name, content)
    with pytest.raises(DelinquencyFileError, match="formula/error"):
        read_table(path)


@pytest.mark.parametrize("hidden", [False, True])
def test_F07_multiple_data_sheets_require_selection(tmp_path, hidden) -> None:
    path = tmp_path / "source.xlsx"
    workbook = Workbook()
    workbook.active.append(["ID"])
    second = workbook.create_sheet("Second")
    second.append(["ID"])
    if hidden:
        second.sheet_state = "hidden"
    workbook.save(path)
    workbook.close()
    with pytest.raises(DelinquencyFileError, match="multiple"):
        read_table(path)


def test_F07_active_empty_sheet_does_not_hide_the_only_data_sheet(tmp_path) -> None:
    path = tmp_path / "source.xlsx"
    workbook = Workbook()
    second = workbook.create_sheet("County rows")
    second.append(["ID", "Due"])
    second.append(["020010200", None])
    workbook.save(path)
    workbook.close()
    assert (
        FileDelinquencySource(path, mapping()).load_records()[0].source_metadata.source_sheet
        == "County rows"
    )


def test_F07_workbook_closes_on_validation_failure(tmp_path, monkeypatch) -> None:
    import openpyxl

    path = book(tmp_path / "source.xlsx", [["ID"], ["=1"]])
    original = openpyxl.load_workbook
    closed = []

    def load(*args, **kwargs):
        workbook = original(*args, **kwargs)
        close = workbook.close

        def tracked_close():
            closed.append(True)
            close()

        monkeypatch.setattr(workbook, "close", tracked_close)
        return workbook

    monkeypatch.setattr(openpyxl, "load_workbook", load)
    with pytest.raises(DelinquencyFileError):
        read_table(path)
    assert closed == [True]


@pytest.mark.parametrize(
    "parameter", ["max_file_bytes", "max_records", "max_columns", "max_cell_bytes"]
)
def test_F09_CSV_limit_exact_boundary_and_overflow(tmp_path, parameter) -> None:
    path = tmp_path / "source.csv"
    path.write_bytes(b"ID,Due\n020010200,1\n")
    thresholds = {
        "max_file_bytes": path.stat().st_size,
        "max_records": 1,
        "max_columns": 2,
        "max_cell_bytes": 9,
    }
    limit = thresholds[parameter]
    assert read_table(path, InputLimits(**{parameter: limit}))[1]
    if limit > 1:
        with pytest.raises(DelinquencyFileError):
            read_table(path, InputLimits(**{parameter: limit - 1}))
    else:
        path.write_bytes(b"ID,Due\n020010200,1\n020010201,2\n")
        with pytest.raises(DelinquencyFileError, match="max_records"):
            read_table(path, InputLimits(max_records=1))


@pytest.mark.parametrize("parameter", ["max_expanded_bytes", "max_archive_members"])
def test_F09_XLSX_archive_budgets(tmp_path, parameter) -> None:
    path = book(tmp_path / "source.xlsx", [["ID", "Due"], ["020010200", None]])
    with ZipFile(path) as archive:
        boundary = (
            sum(item.file_size for item in archive.infolist())
            if parameter == "max_expanded_bytes"
            else len(archive.infolist())
        )
    assert read_table(path, InputLimits(**{parameter: boundary}))[1]
    with pytest.raises(DelinquencyFileError, match=parameter):
        read_table(path, InputLimits(**{parameter: boundary - 1}))


@pytest.mark.parametrize(
    "suffix,content",
    [(".xls", b"legacy"), (".xlsm", b"macro"), (".xlsx", b"corrupt"), (".csv", b"ID\n")],
)
def test_F09_unsupported_corrupt_and_empty_data_fail(tmp_path, suffix, content) -> None:
    path = tmp_path / ("source" + suffix)
    path.write_bytes(content)
    with pytest.raises(DelinquencyFileError):
        read_tabular_file(path)


def test_F09_XLSX_dependency_failure_is_clear(tmp_path, monkeypatch) -> None:
    path = book(tmp_path / "source.xlsx", [["ID"], ["020010200"]])
    original = builtins.__import__

    def missing(name, *args, **kwargs):
        if name == "openpyxl":
            raise ImportError("Synthetic absent dependency")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing)
    with pytest.raises(DelinquencyFileError, match="openpyxl"):
        read_table(path)


def test_F09_XML_entities_are_rejected_before_workbook_loading(tmp_path) -> None:
    path = tmp_path / "unsafe.xlsx"
    with ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", '<!DOCTYPE x [<!ENTITY y "bad">]><x>&y;</x>')
    with pytest.raises(DelinquencyFileError, match="entities"):
        read_table(path)


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_F09_limit_configuration_must_be_positive_integer(value) -> None:
    with pytest.raises(ValueError):
        InputLimits(max_records=value)


def test_F06_unmapped_date_cells_remain_typed_JSON_safe_evidence(tmp_path) -> None:
    path = book(
        tmp_path / "source.xlsx",
        [
            ["ID", "Due", "Unmapped date"],
            ["020010200", 1, datetime(2026, 10, 14, 12, 30)],
        ],
    )
    record = FileDelinquencySource(path, mapping()).load_records()[0]
    assert record.original_row["Unmapped date"] == {
        "source_cell_type": "datetime",
        "iso8601": "2026-10-14T12:30:00",
    }
    json.dumps(record.original_row, allow_nan=False)


def test_F09_byte_budget_checks_actual_read_not_only_stat(tmp_path, monkeypatch) -> None:
    from mn_land.delinquency import tabular

    path = tmp_path / "growing.csv"
    path.write_bytes(b"ID\n020010200\n")
    monkeypatch.setattr(tabular, "check_file", lambda *args: None)
    with pytest.raises(DelinquencyFileError, match="max_file_bytes"):
        read_table(path, InputLimits(max_file_bytes=4))


def test_F09_XLSX_record_budget_counts_blank_gaps(tmp_path) -> None:
    path = book(tmp_path / "source.xlsx", [["ID"], [None], ["020010200"]])
    with pytest.raises(DelinquencyFileError, match="max_records"):
        read_table(path, InputLimits(max_records=1))


def test_F07_underreported_dimensions_do_not_hide_formulas(tmp_path) -> None:
    original = book(tmp_path / "original.xlsx", [["ID", "Due"], ["020010200", "=1"]])
    path = tmp_path / "forged.xlsx"
    with ZipFile(original) as archive, ZipFile(path, "w") as output:
        for name in archive.namelist():
            content = archive.read(name)
            if name == "xl/worksheets/sheet1.xml":
                content = content.replace(b'ref="A1:B2"', b'ref="A1:A1"')
            output.writestr(name, content)
    with pytest.raises(DelinquencyFileError, match="formula/error"):
        read_table(path)


def test_F09_cell_budget_is_UTF8_bytes_and_CSV_setting_is_restored(tmp_path) -> None:
    import csv

    path = tmp_path / "unicode.csv"
    path.write_bytes("ID,O\n01,éé\n".encode())
    original_limit = csv.field_size_limit()
    assert read_table(path, InputLimits(max_cell_bytes=4))[1]
    assert csv.field_size_limit() == original_limit
    with pytest.raises(DelinquencyFileError, match="max_cell_bytes"):
        read_table(path, InputLimits(max_cell_bytes=3))
    assert csv.field_size_limit() == original_limit
