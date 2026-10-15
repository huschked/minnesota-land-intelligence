"""Bounded values-only CSV/XLSX reading with original source locations."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from io import BytesIO, TextIOWrapper
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from mn_land.config.input_limits import DEFAULT_INPUT_LIMITS, InputLimits
from mn_land.delinquency.errors import DelinquencyFileError

SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}


@dataclass(frozen=True, slots=True)
class SourceRow:
    values: dict[str, Any]
    number: int
    sheet: str | None = None
    line_start: int | None = None
    line_end: int | None = None


def check_file(path: Path, limits: InputLimits) -> None:
    if not path.is_file():
        raise DelinquencyFileError(f"file does not exist or is not a regular file: {path}")
    if path.stat().st_size > limits.max_file_bytes:
        raise DelinquencyFileError(
            f"file exceeds max_file_bytes={limits.max_file_bytes}: {path.name}"
        )


def read_input(path: Path, limits: InputLimits) -> bytes:
    check_file(path, limits)
    with path.open("rb") as handle:
        body = handle.read(limits.max_file_bytes + 1)
    if len(body) > limits.max_file_bytes:
        raise DelinquencyFileError(
            f"file exceeds max_file_bytes={limits.max_file_bytes}: {path.name}"
        )
    return body


def _cells(values: tuple | list, limits: InputLimits, location: str) -> None:
    if len(values) > limits.max_columns:
        raise DelinquencyFileError(f"{location}: exceeds max_columns={limits.max_columns}")
    for value in values:
        if isinstance(value, float) and not math.isfinite(value):
            raise DelinquencyFileError(f"{location}: non-finite numeric cell")
        if isinstance(value, str) and len(value.encode("utf-8")) > limits.max_cell_bytes:
            raise DelinquencyFileError(
                f"{location}: cell exceeds max_cell_bytes={limits.max_cell_bytes}"
            )


def _headers(values: tuple | list, limits: InputLimits, location: str) -> tuple[str, ...]:
    _cells(values, limits, location)
    if not values or any(not isinstance(value, str) or not value.strip() for value in values):
        raise DelinquencyFileError(f"{location}: headers must be nonblank text and unique")
    columns = tuple(value.strip() for value in values)
    if len(set(columns)) != len(columns):
        raise DelinquencyFileError(f"{location}: headers must be nonblank and unique")
    return columns


def _csv(body: bytes, limits: InputLimits) -> tuple[tuple[str, ...], list[SourceRow]]:
    previous_limit = csv.field_size_limit()
    # csv counts characters; the UTF-8 byte budget is checked separately below.
    csv.field_size_limit(limits.max_cell_bytes)
    try:
        with TextIOWrapper(BytesIO(body), encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            columns = _headers(next(reader, []), limits, "CSV header")
            rows = []
            previous_line = reader.line_num
            for number, values in enumerate(reader, start=2):
                if number - 1 > limits.max_records:
                    raise DelinquencyFileError(f"CSV record {number}: exceeds max_records")
                line_end = reader.line_num
                line_start = previous_line + 1
                previous_line = line_end
                _cells(values, limits, f"CSV record {number}")
                if not values:
                    continue
                if len(values) != len(columns):
                    raise DelinquencyFileError(
                        f"CSV record {number}, line {line_end}: expected {len(columns)} cells, got {len(values)}"
                    )
                rows.append(
                    SourceRow(
                        dict(zip(columns, values, strict=True)),
                        number,
                        line_start=line_start,
                        line_end=line_end,
                    )
                )
            return columns, rows
    finally:
        csv.field_size_limit(previous_limit)


def _archive(body: bytes, limits: InputLimits) -> None:
    with ZipFile(BytesIO(body)) as archive:
        members = archive.infolist()
        if len(members) > limits.max_archive_members:
            raise DelinquencyFileError("XLSX exceeds max_archive_members")
        if len({item.filename.casefold() for item in members}) != len(members):
            raise DelinquencyFileError("XLSX archive has duplicate member names")
        if sum(item.file_size for item in members) > limits.max_expanded_bytes:
            raise DelinquencyFileError("XLSX exceeds max_expanded_bytes")
        if any(item.filename.lower().endswith("vbaproject.bin") for item in members):
            raise DelinquencyFileError("macro-enabled workbook content is not supported")
        expanded = 0
        for item in members:
            tail = b""
            with archive.open(item) as member:
                while block := member.read(64 * 1024):
                    expanded += len(block)
                    if expanded > limits.max_expanded_bytes:
                        raise DelinquencyFileError("XLSX exceeds max_expanded_bytes")
                    if item.filename.lower().endswith((".xml", ".rels")):
                        probe = tail + block.replace(b"\x00", b"").upper()
                        if b"<!DOCTYPE" in probe or b"<!ENTITY" in probe:
                            raise DelinquencyFileError("XLSX XML DTDs/entities are not supported")
                        tail = probe[-16:]


def _xlsx(body: bytes, limits: InputLimits) -> tuple[tuple[str, ...], list[SourceRow]]:
    _archive(body, limits)
    try:
        from openpyxl import load_workbook
        from openpyxl.utils.exceptions import InvalidFileException
    except ImportError as exc:
        raise DelinquencyFileError("XLSX support requires the openpyxl package") from exc
    with BytesIO(body) as stream:
        try:
            workbook = load_workbook(stream, read_only=True, data_only=False, keep_links=False)
        except InvalidFileException as exc:
            raise DelinquencyFileError("invalid XLSX workbook") from exc
        try:
            return _worksheets(workbook, limits)
        finally:
            workbook.close()


def _worksheets(workbook: Any, limits: InputLimits) -> tuple[tuple[str, ...], list[SourceRow]]:
    selected: tuple[tuple[str, ...], list[SourceRow]] | None = None
    scanned = 0
    for sheet in workbook.worksheets:
        # Do not trust a forged worksheet dimension that would hide actual cells.
        sheet.reset_dimensions()
        entries = []
        for number, cells in enumerate(sheet.iter_rows(), start=1):
            scanned += 1
            if number - 1 > limits.max_records or scanned > limits.max_records + len(
                workbook.worksheets
            ):
                raise DelinquencyFileError(
                    "XLSX exceeds max_records (including blank worksheet rows)"
                )
            values = tuple(cell.value for cell in cells)
            location = f"XLSX sheet {sheet.title}, row {number}"
            _cells(values, limits, location)
            if any(cell.data_type in {"f", "e"} for cell in cells):
                raise DelinquencyFileError(
                    f"{location}: formula/error cells require a values-only export"
                )
            if any(value is not None for value in values):
                entries.append((number, values))
        if not entries:
            continue
        if selected is not None:
            raise DelinquencyFileError(
                "XLSX has multiple nonempty worksheets; explicit selection required"
            )
        if entries[0][0] != 1:
            raise DelinquencyFileError(f"XLSX sheet {sheet.title}: header must be row 1")
        columns = _headers(entries[0][1], limits, f"XLSX sheet {sheet.title} header")
        rows = []
        for number, values in entries[1:]:
            if len(values) > len(columns):
                raise DelinquencyFileError(f"XLSX sheet {sheet.title}, row {number}: extra cells")
            # Omitted trailing spreadsheet cells are explicit empty cells in the header's grid.
            padded = (*values, *((None,) * (len(columns) - len(values))))
            rows.append(SourceRow(dict(zip(columns, padded, strict=True)), number, sheet.title))
        selected = columns, rows
    if selected is None:
        raise DelinquencyFileError("XLSX worksheet is empty")
    return selected


def read_table(
    path: Path,
    limits: InputLimits = DEFAULT_INPUT_LIMITS,
) -> tuple[tuple[str, ...], list[SourceRow]]:
    try:
        body = read_input(path, limits)
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise DelinquencyFileError("unsupported file type; supported: CSV, XLSX")
        columns, rows = _csv(body, limits) if path.suffix.lower() == ".csv" else _xlsx(body, limits)
        if not rows:
            raise DelinquencyFileError("file contains no delinquency records")
        return columns, rows
    except DelinquencyFileError:
        raise
    except (
        OSError,
        UnicodeError,
        csv.Error,
        BadZipFile,
        ValueError,
        KeyError,
        RuntimeError,
        SyntaxError,
        EOFError,
        TypeError,
        IndexError,
    ) as exc:
        raise DelinquencyFileError(f"cannot read {path.name}: {type(exc).__name__}: {exc}") from exc
