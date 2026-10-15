"""F08 plus end-to-end preservation, validation, and review-location regressions."""

import csv
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from mn_land.cli import main
from mn_land.counties.isanti.review import build_review
from mn_land.delinquency.file_loader import DelinquencyFileError, DelinquencyMapping
from mn_land.delinquency.pipeline import import_and_join_delinquency
from mn_land.provenance import sha256_file

FIXTURES = Path(__file__).parents[1] / "fixtures"


def parcel_snapshot(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    snapshot = raw / "isanti" / "2026-01-01"
    snapshot.mkdir(parents=True)
    (snapshot / "manifest.json").write_text(
        json.dumps(
            {
                "retrieved_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
                "record_count": 1,
            }
        ),
        encoding="utf-8",
    )
    source = json.loads((FIXTURES / "isanti_parcel.json").read_text(encoding="utf-8"))
    (snapshot / "page_00001.json").write_text(json.dumps({"features": [source]}), encoding="utf-8")
    return raw


def test_F08_nested_evidence_is_not_flattened_and_bytes_remain_unchanged(tmp_path) -> None:
    payload = json.loads((FIXTURES / "isanti_delinquency_mapping.json").read_text(encoding="utf-8"))
    payload["supporting_documents"] = ["first/note.md", "second/note.md"]
    for index, name in enumerate(payload["supporting_documents"]):
        path = tmp_path / name
        path.parent.mkdir()
        path.write_text(f"Synthetic note {index}", encoding="utf-8")
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(json.dumps(payload), encoding="utf-8")
    source_path = FIXTURES / "isanti_delinquency.csv"
    before = sha256_file(mapping_path), sha256_file(source_path)
    stats = import_and_join_delinquency(
        source_path,
        mapping_path,
        Decimal(10),
        raw_root=parcel_snapshot(tmp_path),
        processed_root=tmp_path / "processed",
    )
    assert (sha256_file(mapping_path), sha256_file(source_path)) == before
    assert sha256_file(stats.raw_snapshot_dir / "mapping.json") == before[0]
    assert sha256_file(stats.raw_snapshot_dir / "source.csv") == before[1]
    for name in payload["supporting_documents"]:
        assert (stats.raw_snapshot_dir / "supporting" / name).read_bytes() == (
            tmp_path / name
        ).read_bytes()
    reloaded = DelinquencyMapping.from_json(
        stats.raw_snapshot_dir / "mapping.json",
        supporting_root=stats.raw_snapshot_dir / "supporting",
    )
    assert reloaded.supporting_documents == tuple(payload["supporting_documents"])
    manifest = json.loads((stats.processed_snapshot_dir / "manifest.json").read_text())
    assert manifest["input_limits"]["max_records"] == 100_000
    assert manifest["parcel_normalization_diagnostics"][0]["severity"] == "warning"


def test_F08_unsafe_mapping_fails_before_any_raw_copy(tmp_path) -> None:
    payload = json.loads((FIXTURES / "isanti_delinquency_mapping.json").read_text(encoding="utf-8"))
    payload["supporting_documents"] = ["../outside.md"]
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DelinquencyFileError):
        import_and_join_delinquency(
            FIXTURES / "isanti_delinquency.csv",
            mapping,
            Decimal(10),
            raw_root=tmp_path / "raw",
            processed_root=tmp_path / "processed",
        )
    assert not (tmp_path / "raw").exists()


@pytest.mark.parametrize("format", ["csv", "xlsx"])
def test_F04_F06_review_keeps_original_source_row_locations(tmp_path, format) -> None:
    raw = parcel_snapshot(tmp_path)
    source = tmp_path / f"source.{format}"
    payload = {
        "source_agency": "Isanti County",
        "dataset": "Synthetic mixed source",
        "delinquency_assertion": "mixed_unpaid_prior_and_overdue_current_year_taxes",
        "tax_year_convention": "isanti_assessment_year_plus_one",
        "year_semantics_reference": "note.md",
        "supporting_documents": ["note.md"],
        "columns": {"parcel_id": "PARID", "owner_name": "OWN1"},
    }
    (tmp_path / "note.md").write_text("Synthetic convention evidence", encoding="utf-8")
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps(payload), encoding="utf-8")
    rows = [
        ["PARID", "OWN1", "ASMTYR", "TAXYR"],
        ["020010200", "Synthetic", 2024, 2025],
        [],
        ["020010200", "Synthetic", 2023, 2025],
    ]
    if format == "xlsx":
        workbook = Workbook()
        for row in rows:
            workbook.active.append(row)
        workbook.save(source)
        workbook.close()
    else:
        with source.open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerows(rows)
    stats = import_and_join_delinquency(
        source, mapping, Decimal(10), raw_root=raw, processed_root=tmp_path / "processed"
    )
    before = sha256_file(stats.raw_snapshot_dir / f"source.{format}")
    output = build_review(stats.processed_snapshot_dir)
    with (output / "isanti_duplicate_group_review.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        review_rows = list(csv.DictReader(handle))
    assert review_rows[0]["source_row_numbers"] == "2;4"
    assert sha256_file(stats.raw_snapshot_dir / f"source.{format}") == before
    candidate = json.loads(
        (stats.processed_snapshot_dir / "isanti_verified_delinquent_candidates.json").read_text()
    )[0]
    assert candidate["total_taxes_and_penalties_due"] is None
    assert candidate["taxes_payable_years"] == [2024, 2025]


def test_F02_CLI_returns_clear_schema_error_without_a_traceback(monkeypatch, caplog) -> None:
    def fail(*args):
        raise ValueError("Synthetic source schema changed")

    monkeypatch.setattr("mn_land.cli.run_pipeline", fail)
    assert main(["find-candidates", "--county", "isanti"]) == 2
    assert "schema changed" in caplog.text
