import csv
import json
from decimal import Decimal
from pathlib import Path

from mn_land.counties.isanti.review import build_review, duplicate_profile, review_bucket


def test_review_classification_preserves_unknown_and_special_cases() -> None:
    assert review_bucket({"improvement_value": None}) == "unknown_improvement_review"
    assert review_bucket({"improvement_value": "0"}) == "zero_improvement_value_review"
    assert review_bucket({
        "property_classification": "PILT-Payment In-Lieu of Taxes",
        "improvement_value": "0",
    }) == "PILT_or_exempt_review"
    assert review_bucket({
        "property_classification": "2B-Rural Vacant Land/Non-Productive - Non Homestead",
        "improvement_value": "0",
    }) == "rural_vacant_classification_review"


def test_duplicate_profile_compares_money_without_adding_or_selecting_owners() -> None:
    rows = [
        {"TAXYR": "2025", "TOTAMT": "1,250.50", "OWN1": "Owner A"},
        {"TAXYR": "2025", "TOTAMT": "1250.50", "OWN1": "Owner B"},
    ]
    profile = duplicate_profile(rows)
    assert profile["distinct_fiscal_value_sets"] == 1
    assert profile["distinct_owner_texts"] == 2
    assert profile["fiscal_review"] == "identical_fiscal_values_do_not_sum"
    rows[1]["TOTAMT"] = ""
    assert duplicate_profile(rows)["distinct_fiscal_value_sets"] == 2


def test_review_uses_recorded_snapshot_and_keeps_original_outputs(tmp_path: Path) -> None:
    parcel_snapshot = tmp_path / "parcels/2026-01-01"
    parcel_snapshot.mkdir(parents=True)
    fixture = Path(__file__).parents[1] / "fixtures/isanti_parcel.json"
    record = json.loads(fixture.read_text(encoding="utf-8"))
    (parcel_snapshot / "manifest.json").write_text(json.dumps({
        "retrieved_at": "2026-01-01T00:00:00+00:00", "record_count": 1,
    }))
    (parcel_snapshot / "page_00001.json").write_text(json.dumps({"features": [record]}))
    # A later snapshot deliberately has no records. It must not replace the original.
    later = tmp_path / "parcels/2026-02-01"
    later.mkdir()
    (later / "manifest.json").write_text(json.dumps({
        "retrieved_at": "2026-02-01T00:00:00+00:00", "record_count": 0,
    }))
    raw = tmp_path / "raw"
    raw.mkdir()
    with (raw / "source.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["PARID", "OWN1", "TAXYR"])
        writer.writeheader()
        writer.writerow({"PARID": "020010200", "OWN1": "Test", "TAXYR": "2025"})
    snapshot = tmp_path / "processed"
    snapshot.mkdir()
    (snapshot / "manifest.json").write_text(json.dumps({
        "delinquency_snapshot": str(raw), "parcel_snapshot": str(parcel_snapshot),
        "minimum_acres": "10",
    }))
    path = snapshot / "isanti_verified_delinquent_candidates.json"
    path.write_text(json.dumps([{
        "parcel_id": "02.001.0200", "deeded_acres": "25.5", "owner_name": "Test",
        "property_classification": "AGRICULTURAL", "improvement_value": "0",
        "assessed_value": None, "delinquency_source_row": 2,
        "delinquency_original_row": {"PARID": "020010200", "OWN1": "Test", "TAXYR": "2025"},
    }]))
    before = path.read_bytes()
    output = build_review(snapshot, Decimal(10))
    summary = json.loads((output / "summary.json").read_text())
    assert summary["large_listing_matches"] == 1
    assert summary["unmatched_distinct_parcels"] == 0
    assert summary["manual_verification_status"] == "pending"
    assert summary["delinquency_status_changes"] == 0
    assert summary["provenance"]["configuration"]["command"] == "review-delinquency"
    assert len(summary["provenance"]["outputs"]) == 7
    assert path.read_bytes() == before
    comparison_dir = snapshot / "review/2026-01-02"
    comparison_dir.mkdir(parents=True)
    (comparison_dir / "official_report_comparison.json").write_text(json.dumps({
        "operational_status": "HOLD_COUNTY_RECONCILIATION_REQUIRED",
    }))
    held_output = build_review(snapshot, Decimal(10))
    held_summary = json.loads((held_output / "summary.json").read_text())
    assert held_summary["manual_verification_status"] == "reports_compared_unreconciled"
    with (held_output / "isanti_land_review.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["county_verification_status"] == "hold_county_reconciliation_required"
