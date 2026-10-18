"""ML-124: observed differences, not payment, parcel lineage or source refresh."""
import json
import shutil
from copy import deepcopy
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from mn_land import cli, snapshot_diff
from mn_land.delinquency.pipeline import import_and_join_delinquency
from mn_land.provenance import sha256_file
from mn_land.runs import RunValidationError, RunWorkspace, read_json, validate_run, workspace_path
from mn_land.snapshot_diff import build_difference, compare_snapshots

FIXTURE = Path(__file__).parents[1] / "fixtures/isanti_parcel.json"
AS_OF = date(2026, 10, 17)


@pytest.fixture
def saved(tmp_path, fake_adapter, monkeypatch):
    # These reports deliberately use the fixed AS_OF date below. A real import
    # clock would turn their captures future-dated after UTC midnight, making the
    # same evidence/assertions depend on when/where CI happens to execute.
    class ImportClock(datetime):
        @classmethod
        def now(cls, tz=None):
            captured = datetime(2026, 10, 16, 12, tzinfo=UTC)
            return captured.astimezone(tz) if tz is not None else captured.replace(tzinfo=None)

    monkeypatch.setattr("mn_land.delinquency.pipeline.datetime", ImportClock)

    def make(
        rows=None, *, features=None, held=False, published="2026-10-13", min_acres=10,
        dataset="Synthetic dated listing", assertion=None, gis_date=datetime(2026, 10, 16, tzinfo=UTC),
    ):
        if rows is None:
            rows = ["020010200,2024,2025,100", "020010200,2025,2025,200"]
        adapter = fake_adapter(features)
        with RunWorkspace(tmp_path / "raw/isanti", "parcel_raw") as raw:
            list(adapter.fetch_parcels(raw.path, gis_date, directory_reserved=True))
            raw.publish()
        source = tmp_path / "source.csv"
        source.write_text("PARID,ASMTYR,TAXYR,TOTAMT\n" + "\n".join(rows) + "\n", encoding="utf-8")
        note = tmp_path / "years.md"
        note.write_text("Synthetic retained year evidence", encoding="utf-8")
        mapping = tmp_path / "mapping.json"
        payload = {
            "source_agency": "Isanti County - synthetic fixture", "dataset": dataset,
            "publication_date": published,
            "delinquency_assertion": "mixed_unpaid_prior_and_overdue_current_year_taxes",
            "tax_year_convention": "isanti_assessment_year_plus_one",
            "year_semantics_reference": note.name, "supporting_documents": [note.name],
            "columns": {"parcel_id": "PARID"},
            "verification_hold_reason": "Synthetic county accounting hold" if held else None,
        }
        if assertion is not None:
            payload.update(assertion)
        mapping.write_text(json.dumps(payload), encoding="utf-8")
        return import_and_join_delinquency(
            source, mapping, Decimal(min_acres), adapter=adapter,
            raw_root=tmp_path / "raw", processed_root=tmp_path / "processed",
            parcel_snapshot=raw.path,
        ).processed_snapshot_dir
    return make


def feature(parcel_id="02.001.0200", oid=101, **attributes):
    value = deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
    value["attributes"].update(PARCELID=parcel_id, OBJECTID=oid, **attributes)
    return value


def frozen(path):
    return {str(p.relative_to(path)): sha256_file(p) for p in path.rglob("*") if p.is_file()}


def difference(before, after, **kwargs):
    return build_difference(before, after, as_of=AS_OF, stale_after_days=30, **kwargs)


def test_same_listing_recaptured_is_unchanged_not_refreshed(saved):
    before, after = saved(), saved()
    manifest, changes = difference(before, after)
    assert manifest["summary"] == {"added": 0, "changed": 0, "missing": 0, "unchanged": 1}
    assert any("Same retained listing bytes" in warning for warning in manifest["warnings"])
    assert changes[0]["parcel_id"] == "020010200"
    assert changes[0]["current_payment_status"] == "unknown"
    assert changes[0]["before"]["views"] == {
        "prior_year_large": True, "current_year_overdue_large": True,
    }
    values = changes[0]["after"]["listing_rows"][0]["values"]
    assert values["total_taxes_and_penalties_due"] is None
    assert values["original_row"]["TOTAMT"] in ("100", "200")


def test_year_rollover_is_source_based_and_retains_charge_year(saved):
    before = saved(["020010200,2025,2025,100"])
    after = saved(["020010200,2025,2026,100"], published="2027-01-10")
    manifest, rows = difference(before, after)
    assert manifest["before"]["report_payable_years"] == [2026]
    assert manifest["after"]["report_payable_years"] == [2027]
    left = rows[0]["before"]["listing_rows"][0]["values"]
    right = rows[0]["after"]["listing_rows"][0]["values"]
    assert left["taxes_payable_year"] == right["taxes_payable_year"] == 2026
    assert left["tax_period_status"] == "overdue_current_year"
    assert right["tax_period_status"] == "prior_year_unpaid"
    assert rows[0]["change"] == "changed"
    assert any("rollover" in warning for warning in manifest["warnings"])


def test_missing_listing_still_shows_gis_observation_and_old_status(saved):
    before, after = saved(), saved(["020010299,2024,2025,50"])
    manifest, rows = difference(before, after)
    row = next(row for row in rows if row["parcel_id"] == "020010200")
    assert manifest["summary"]["missing"] == 1
    assert row["before"]["dated_join_statuses"] == ["verified_delinquent"]
    assert row["after"]["listing_observed"] is False
    assert len(row["after"]["gis_records"]) == 1
    assert row["after"]["dated_join_statuses"] == ["not_observed_in_listing"]
    assert row["current_payment_status"] == "unknown"


def test_parent_disappears_children_appear_without_inferred_split_or_retirement(saved):
    before = saved()
    after = saved(
        ["020010201,2024,2025,50", "020010202,2024,2025,50"],
        features=[feature("02.001.0201", 201), feature("02.001.0202", 202)],
    )
    manifest, rows = difference(before, after)
    assert manifest["summary"] == {"added": 2, "changed": 0, "missing": 1, "unchanged": 0}
    assert manifest["normalized_gis_id_changes"]["missing"] == ["020010200"]
    assert manifest["normalized_gis_id_changes"]["added"] == ["020010201", "020010202"]
    assert all(row["identity_relationship"] == "not_inferred" for row in rows)
    assert all(row["current_payment_status"] == "unknown" for row in rows)


def test_source_hold_removes_candidate_not_listing_and_does_not_clear_old_status(saved):
    before, after = saved(), saved(held=True)
    manifest, rows = difference(before, after)
    row = rows[0]
    assert manifest["after"]["source_hold"] == "Synthetic county accounting hold"
    assert row["change"] == "changed"  # never missing merely because candidate export is empty
    assert row["after"]["listing_observed"]
    assert row["before"]["dated_join_statuses"] == ["verified_delinquent"]
    assert row["after"]["dated_join_statuses"] == ["unverified"]
    assert not row["after"]["views"]["prior_year_large"]
    assert any("source hold retained" in warning for warning in manifest["warnings"])


def test_stale_future_and_unknown_dates_are_distinct_not_repaired_by_capture(saved):
    before, after = saved(published=None), saved(published="2026-11-01")
    manifest, _ = difference(before, after)
    assert manifest["before"]["freshness"]["listing_publication"]["state"] == "unknown"
    assert manifest["after"]["freshness"]["listing_publication"]["state"] == "future_dated"
    old = saved(published="2020-01-01")
    manifest, rows = difference(old, old)
    assert manifest["after"]["freshness"]["listing_publication"]["state"] == "stale"
    assert manifest["after"]["freshness"]["listing_capture"]["state"] == "within_policy"
    assert rows[0]["after"]["dated_join_statuses"] == ["verified_delinquent"]


@pytest.mark.parametrize("age,state", [(30, "within_policy"), (31, "stale"), (-1, "future_dated")])
def test_freshness_boundary_is_explicit(age, state):
    from datetime import timedelta
    source = (AS_OF - timedelta(days=age)).isoformat()
    assert snapshot_diff._age(source, AS_OF, 30)["state"] == state


def test_timestamp_age_uses_utc_and_decimal_conversion_does_not_round():
    assert snapshot_diff._age("2026-10-17T23:30:00-05:00", AS_OF, 30, timestamp=True)["state"] == "future_dated"
    value = Decimal("123456789012345678901234567890.1200")
    assert snapshot_diff._json_value(value) == "123456789012345678901234567890.12"
    assert snapshot_diff._json_value(Decimal("0.00")) == "0"
    assert snapshot_diff._json_value(None) is None


def test_reordered_source_rows_do_not_create_false_changes_but_locations_remain(saved):
    before = saved()
    after = saved(["020010200,2025,2025,200", "020010200,2024,2025,100"])
    manifest, rows = difference(before, after)
    assert manifest["summary"]["unchanged"] == 1
    assert rows[0]["before"]["listing_rows"] != rows[0]["after"]["listing_rows"]
    assert all("source_row_number" in row for row in rows[0]["after"]["listing_rows"])


def test_repeated_rows_preserve_multiplicity_and_raw_amount_changes_without_summing(saved):
    before = saved(["020010200,2024,2025,100"] * 2)
    after = saved(["020010200,2024,2025,100", "020010200,2024,2025,150"])
    _, rows = difference(before, after)
    assert rows[0]["change"] == "changed"
    assert "listing_rows" in rows[0]["changed_fields"]
    for side in ("before", "after"):
        assert len(rows[0][side]["listing_rows"]) == 2
        assert all(row["values"]["total_taxes_and_penalties_due"] is None for row in rows[0][side]["listing_rows"])


def test_below_threshold_unmatched_and_duplicate_gis_ids_are_not_hidden(saved):
    before = saved(features=[feature(DEEDEDACRES=1)])
    after = saved(features=[])
    manifest, rows = difference(before, after)
    assert manifest["before"]["view_counts"]["prior_year_large"] == 0
    assert manifest["summary"]["changed"] == 1
    assert rows[0]["after"]["dated_join_statuses"] == ["unmatched"]
    ambiguous = saved(features=[feature(oid=101), feature(oid=102)])
    _, rows = difference(before, ambiguous)
    assert rows[0]["after"]["dated_join_statuses"] == ["ambiguous"]
    assert len(rows[0]["after"]["gis_records"]) == 2


@pytest.mark.parametrize("change", ["threshold", "mapping"])
def test_incompatible_profiles_rejected(saved, change):
    before = saved()
    after = saved(min_acres=20) if change == "threshold" else saved(assertion={"source_url": "https://example.test/new"})
    with pytest.raises(RunValidationError, match="incompatible"):
        difference(before, after)


def test_backward_dates_warn_and_no_reordering_occurs(saved):
    before, after = saved(published="2026-10-13"), saved(published="2026-01-01", gis_date=datetime(2025, 1, 1, tzinfo=UTC))
    manifest, _ = difference(before, after)
    assert manifest["before"]["join_run_id"] == before.name
    assert manifest["after"]["join_run_id"] == after.name
    assert sum("moved backward" in warning for warning in manifest["warnings"]) == 2


def test_report_is_complete_portable_deterministic_and_inputs_unchanged(saved, tmp_path, monkeypatch):
    before, after = saved(), saved()
    baseline = frozen(tmp_path / "raw"), frozen(tmp_path / "processed")

    def prohibited(*args, **kwargs):
        pytest.fail("Offline comparison attempted acquisition, latest selection, replay or reimport")

    monkeypatch.setattr("mn_land.counties.isanti.IsantiAdapter.fetch_parcels", prohibited)
    monkeypatch.setattr("mn_land.runs.select_latest", prohibited)
    monkeypatch.setattr("mn_land.delinquency.pipeline.replay_delinquency", prohibited)
    monkeypatch.setattr("mn_land.delinquency.pipeline.import_and_join_delinquency", prohibited)
    first = compare_snapshots(before, after, as_of=AS_OF, processed_root=tmp_path / "reports")
    second = compare_snapshots(before, after, as_of=AS_OF, processed_root=tmp_path / "reports")
    assert first != second
    assert (first / "changes.json").read_bytes() == (second / "changes.json").read_bytes()
    assert (frozen(tmp_path / "raw"), frozen(tmp_path / "processed")) == baseline
    assert validate_run(first, "comparison").completion["row_counts"] == {"changes.json": 1}
    moved = workspace_path(tmp_path / "portable" / first.name)
    shutil.copytree(first, moved)
    (tmp_path / "raw").rename(tmp_path / "unavailable_raw")
    (tmp_path / "processed").rename(tmp_path / "unavailable_processed")
    assert validate_run(moved, "comparison")


def test_failed_report_preserves_previous_success_and_pointer(saved, tmp_path, monkeypatch):
    before, after = saved(), saved()
    first = compare_snapshots(before, after, as_of=AS_OF, processed_root=tmp_path / "reports")
    baseline, pointer = frozen(first), (first.parent / "latest.json").read_bytes()
    original = snapshot_diff.write_json

    def failed(path, payload):
        if path.name == "changes.json":
            raise OSError("Synthetic disk failure")
        original(path, payload)

    monkeypatch.setattr(snapshot_diff, "write_json", failed)
    with pytest.raises(OSError):
        compare_snapshots(before, after, as_of=AS_OF, processed_root=tmp_path / "reports")
    assert frozen(first) == baseline
    assert (first.parent / "latest.json").read_bytes() == pointer
    assert len(list(first.parent.glob("*/failure.json"))) == 1


def test_input_corruption_legacy_and_nested_output_fail_closed(saved, tmp_path):
    before = saved()
    with pytest.raises(RunValidationError, match="inside"):
        compare_snapshots(before, before, as_of=AS_OF, processed_root=before / "nested")
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RunValidationError):
        difference(before, legacy)
    (before / "accounting.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RunValidationError):
        difference(before, before)


def test_complete_older_join_without_fingerprints_stays_unknown(saved):
    before = saved()
    manifest = read_json(before / "manifest.json")
    del manifest["reproducibility"], manifest["selection"]
    (before / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    completion = read_json(before / "completion.json")
    for entry in completion["artifacts"]:
        if entry["path"] == "manifest.json":
            entry.update(bytes=(before / "manifest.json").stat().st_size, sha256=sha256_file(before / "manifest.json"))
    (before / "completion.json").write_text(json.dumps(completion), encoding="utf-8")
    assert validate_run(before, "delinquency_processed")
    baseline = frozen(before)
    with pytest.raises(RunValidationError, match="recorded, reproducible"):
        difference(before, before)
    assert frozen(before) == baseline


@pytest.mark.parametrize("alteration", ["paid", "warnings"])
def test_resealed_claim_is_rejected_by_content_validation(saved, tmp_path, alteration):
    before = saved()
    result = compare_snapshots(before, before, as_of=AS_OF, processed_root=tmp_path / "reports")
    artifact = "changes.json" if alteration == "paid" else "manifest.json"
    payload = read_json(result / artifact)
    if alteration == "paid":
        payload[0]["current_payment_status"] = "paid"
    else:
        payload["warnings"] = []
    (result / artifact).write_text(json.dumps(payload), encoding="utf-8")
    completion = read_json(result / "completion.json")
    for entry in completion["artifacts"]:
        if entry["path"] == artifact:
            entry.update(bytes=(result / artifact).stat().st_size, sha256=sha256_file(result / artifact))
    (result / "completion.json").write_text(json.dumps(completion), encoding="utf-8")
    with pytest.raises(RunValidationError, match="Comparison content"):
        validate_run(result, "comparison")


def test_cli_is_explicit_offline_and_reports_limitations(saved, tmp_path, capsys):
    before = saved()
    assert cli.main([
        "compare-snapshots", "--county", "isanti", "--before", str(before),
        "--after", str(before), "--as-of", AS_OF.isoformat(), "--output-root", str(tmp_path / "reports"),
    ]) == 0
    assert "Missing is not paid" in capsys.readouterr().out
    assert cli.main([
        "compare-snapshots", "--county", "isanti", "--before", str(before),
        "--after", str(before), "--as-of", AS_OF.isoformat(), "--stale-after-days", "-1",
    ]) == 2


@pytest.mark.parametrize("days", [-1, True, 36501])
def test_invalid_policy_rejected_without_output(tmp_path, days):
    with pytest.raises(RunValidationError, match="stale-after-days"):
        compare_snapshots(tmp_path, tmp_path, as_of=AS_OF, stale_after_days=days)
