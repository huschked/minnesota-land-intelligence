import csv
import json
from decimal import Decimal
from pathlib import Path

from mn_land.counties.isanti.review import build_review, duplicate_profile, review_bucket
from mn_land.delinquency.pipeline import import_and_join_delinquency


def test_review_classification_preserves_unknown_and_special_cases() -> None:
    assert review_bucket({"improvement_value": None}) == "unknown_improvement_review"
    assert review_bucket({"improvement_value": "0"}) == "zero_improvement_value_review"
    assert (
        review_bucket(
            {
                "property_classification": "PILT-Payment In-Lieu of Taxes",
                "improvement_value": "0",
            }
        )
        == "PILT_or_exempt_review"
    )
    assert (
        review_bucket(
            {
                "property_classification": "2B-Rural Vacant Land/Non-Productive - Non Homestead",
                "improvement_value": "0",
            }
        )
        == "rural_vacant_classification_review"
    )


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


def test_review_uses_recorded_snapshot_and_keeps_original_outputs(tmp_path: Path, make_raw) -> None:
    raw = tmp_path / "raw"
    make_raw(raw)
    source = tmp_path / "source.csv"
    source.write_text("PARID,OWN1,TAXYR\n020010200,Test,2025\n", encoding="utf-8")
    mapping = tmp_path / "mapping.json"
    mapping.write_text(
        json.dumps(
            {
                "source_agency": "Isanti County",
                "dataset": "Synthetic",
                "delinquency_assertion": "each_row_represents_delinquent_parcel",
                "columns": {"parcel_id": "PARID", "owner_name": "OWN1"},
            }
        )
    )
    stats = import_and_join_delinquency(
        source,
        mapping,
        Decimal(10),
        raw_root=raw,
        processed_root=tmp_path / "processed",
    )
    # A newer complete empty acquisition must not replace the join's pinned source.
    make_raw(raw, [])
    snapshot = stats.processed_snapshot_dir
    path = snapshot / "isanti_verified_delinquent_candidates.json"
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
    comparison_dir = tmp_path / "comparison"
    comparison_dir.mkdir(parents=True)
    (comparison_dir / "official_report_comparison.json").write_text(
        json.dumps(
            {
                "operational_status": "HOLD_COUNTY_RECONCILIATION_REQUIRED",
            }
        )
    )
    held_output = build_review(
        snapshot, Decimal(10), comparison_path=comparison_dir / "official_report_comparison.json"
    )
    held_summary = json.loads((held_output / "summary.json").read_text())
    assert held_summary["manual_verification_status"] == "reports_compared_unreconciled"
    with (held_output / "isanti_land_review.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["county_verification_status"] == "hold_county_reconciliation_required"
