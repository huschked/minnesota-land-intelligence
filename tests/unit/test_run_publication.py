"""R01-R07: exact inputs, fail-closed publication, and shared reader eligibility."""

import errno
import json
import runpy
import sys
import types
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from threading import Barrier

import pytest

from mn_land import cli, runs
from mn_land.config.settings import Settings
from mn_land.counties.isanti.review import build_review
from mn_land.delinquency import pipeline as joins
from mn_land.delinquency.file_loader import FileDelinquencySource
from mn_land.ingestion import pipeline as parcels
from mn_land.provenance import sha256_file
from mn_land.runs import (
    JOIN_OUTPUTS,
    PARCEL_OUTPUTS,
    REVIEW_OUTPUTS,
    RunValidationError,
    RunWorkspace,
    read_json,
    select_latest,
    validate_run,
    workspace_path,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    config = Settings(raw_dir=tmp_path / "raw", processed_dir=tmp_path / "processed")
    monkeypatch.setattr(parcels, "SETTINGS", config)
    monkeypatch.setattr(cli, "SETTINGS", config)
    return config


def import_fixture(settings):
    return joins.import_and_join_delinquency(
        FIXTURES / "isanti_delinquency.csv",
        FIXTURES / "isanti_delinquency_mapping.json",
        Decimal(10),
        raw_root=settings.raw_dir,
        processed_root=settings.processed_dir,
    )


def mixed_input(tmp_path, *, held=False):
    source = tmp_path / "mixed.csv"
    source.write_text(
        "PARID,OWN1,ASMTYR,TAXYR,TOTAMT\n020010200,Synthetic,2024,2025,100\n020010200,Synthetic,2023,2025,100\n020010200,Synthetic,2025,2025,100\n050080500,Synthetic,2024,2025,100\n030010100,Synthetic,2024,2025,100\n",
        encoding="utf-8",
    )
    mapping = tmp_path / "mapping.json"
    (tmp_path / "note.md").write_text("Synthetic retained convention evidence", encoding="utf-8")
    payload = {
        "source_agency": "Isanti County",
        "dataset": "Synthetic mixed source",
        "delinquency_assertion": "mixed_unpaid_prior_and_overdue_current_year_taxes",
        "tax_year_convention": "isanti_assessment_year_plus_one",
        "year_semantics_reference": "note.md",
        "supporting_documents": ["note.md"],
        "columns": {"parcel_id": "PARID", "owner_name": "OWN1"},
    }
    if held:
        payload["verification_hold_reason"] = "Synthetic hold pending county reconciliation"
    mapping.write_text(json.dumps(payload), encoding="utf-8")
    return source, mapping


def frozen_tree(path):
    return {
        item.relative_to(path).as_posix(): sha256_file(item)
        for item in path.rglob("*")
        if item.is_file()
    }


def assert_previous(old, before, pointer_before, kind):
    assert frozen_tree(old) == before
    assert (old.parent / "latest.json").read_bytes() == pointer_before
    assert select_latest(old.parent, kind).path == old
    for path in old.parent.iterdir():
        if path.is_dir() and path != old:
            with pytest.raises(RunValidationError):
                validate_run(path, kind)


def test_R01_originals_changed_during_normalization_do_not_change_captured_inputs(
    tmp_path, settings, make_raw, monkeypatch
):
    make_raw(settings.raw_dir)
    source, mapping = mixed_input(tmp_path)
    source_before, mapping_before = source.read_bytes(), mapping.read_bytes()
    original = FileDelinquencySource.load_records
    changed = False

    def edit_originals(self):
        nonlocal changed
        if not changed:
            changed = True
            source.write_text("mutable original replaced", encoding="utf-8")
            mapping.write_text("[]", encoding="utf-8")
        return original(self)

    monkeypatch.setattr(FileDelinquencySource, "load_records", edit_originals)
    stats = joins.import_and_join_delinquency(
        source,
        mapping,
        Decimal(10),
        raw_root=settings.raw_dir,
        processed_root=settings.processed_dir,
    )
    assert (stats.raw_snapshot_dir / "source.csv").read_bytes() == source_before
    assert (stats.raw_snapshot_dir / "mapping.json").read_bytes() == mapping_before
    run = validate_run(stats.processed_snapshot_dir, "delinquency_processed")
    assert (run.source("delinquency") / "source.csv").read_bytes() == source_before
    assert run.manifest["delinquency_records_loaded"] == 5


def test_R01_tamper_retained_file_during_validation_cannot_be_sealed(
    tmp_path, settings, monkeypatch
):
    source, mapping = mixed_input(tmp_path)
    original = FileDelinquencySource.load_records

    def tamper(self):
        records = original(self)
        self.path.write_text(
            self.path.read_text().replace("Synthetic", "Altered"), encoding="utf-8"
        )
        return records

    monkeypatch.setattr(FileDelinquencySource, "load_records", tamper)
    with pytest.raises(RunValidationError, match="hash mismatch"):
        joins.import_and_join_delinquency(
            source,
            mapping,
            Decimal(10),
            raw_root=settings.raw_dir,
            processed_root=settings.processed_dir,
        )
    root = workspace_path(settings.raw_dir / "isanti/delinquency")
    assert not (root / "latest.json").exists()
    assert len(list(root.glob("*/failure.json"))) == 1
    assert not list(root.glob("*/completion.json"))


def test_R01_page_changed_after_validation_fails_pinning(settings, make_raw, monkeypatch):
    source = make_raw(settings.raw_dir)
    original = runs.validate_run
    changed = False

    def tamper_after_validation(path, kind, **kwargs):
        nonlocal changed
        validated = original(path, kind, **kwargs)
        if path == source and not changed:
            changed = True
            page = source / "page_00001.json"
            page.write_bytes(page.read_bytes() + b" ")
        return validated

    monkeypatch.setattr(runs, "validate_run", tamper_after_validation)
    with (
        pytest.raises(RunValidationError, match="grew|changed"),
        RunWorkspace(settings.processed_dir / "isanti/parcels", "parcel_processed") as run,
    ):
        run.pin(source, "parcel")
    assert not (run.path / "completion.json").exists()
    assert (run.path / "failure.json").exists()


@pytest.mark.parametrize("name", PARCEL_OUTPUTS)
def test_R02_each_parcel_export_failure_preserves_previous_success(
    settings, fake_adapter, monkeypatch, name
):
    old = parcels.run_pipeline(fake_adapter(), Decimal(10)).processed_run_dir
    before, pointer = frozen_tree(old), (old.parent / "latest.json").read_bytes()
    original = Path.open

    def fail(self, mode="r", *args, **kwargs):
        if (
            self.name == name
            and self.parent.parent == old.parent
            and self.parent != old
            and mode == "x"
        ):
            raise OSError(errno.ENOSPC, "Synthetic disk full")
        return original(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail)
    with pytest.raises(OSError):
        parcels.run_pipeline(fake_adapter(), Decimal(10))
    assert_previous(old, before, pointer, "parcel_processed")


@pytest.mark.parametrize("name", JOIN_OUTPUTS)
def test_R02_each_join_export_failure_preserves_previous_success(
    settings, make_raw, monkeypatch, name
):
    make_raw(settings.raw_dir)
    old = import_fixture(settings).processed_snapshot_dir
    before, pointer = frozen_tree(old), (old.parent / "latest.json").read_bytes()
    original = Path.open

    def fail(self, mode="r", *args, **kwargs):
        if (
            self.name == name
            and self.parent.parent == old.parent
            and self.parent != old
            and mode == "x"
        ):
            raise PermissionError("Synthetic output denial")
        return original(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail)
    with pytest.raises(PermissionError):
        import_fixture(settings)
    assert_previous(old, before, pointer, "delinquency_processed")


@pytest.mark.parametrize("name", REVIEW_OUTPUTS)
def test_R02_each_review_export_failure_is_not_eligible(
    tmp_path, settings, make_raw, monkeypatch, name
):
    make_raw(settings.raw_dir)
    source, mapping = mixed_input(tmp_path)
    joined = joins.import_and_join_delinquency(
        source,
        mapping,
        Decimal(10),
        raw_root=settings.raw_dir,
        processed_root=settings.processed_dir,
    )
    old = build_review(joined.processed_snapshot_dir)
    before, pointer = frozen_tree(old), (old.parent / "latest.json").read_bytes()
    original = Path.open

    def fail(self, mode="r", *args, **kwargs):
        if (
            self.name == name
            and self.parent.parent == old.parent
            and self.parent != old
            and mode == "x"
        ):
            raise OSError("Synthetic review output failure")
        return original(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail)
    with pytest.raises(OSError):
        build_review(joined.processed_snapshot_dir)
    assert_previous(old, before, pointer, "review")


@pytest.mark.parametrize(
    "stage",
    [
        "normalization",
        "hash",
        "manifest",
        "completion_write",
        "completion_install",
        "pointer_update",
    ],
)
def test_R02_R05_publication_boundary_failures(settings, fake_adapter, monkeypatch, stage):
    old = parcels.run_pipeline(fake_adapter(), Decimal(10)).processed_run_dir
    before, pointer = frozen_tree(old), (old.parent / "latest.json").read_bytes()
    if stage == "normalization":

        def fail(*args, **kwargs):
            raise RuntimeError("Synthetic normalizer failure")

        monkeypatch.setattr(joins, "normalize_with_diagnostics", fail)
    elif stage == "hash":
        original_hash = runs.sha256_file

        def fail_hash(path):
            if (
                path.name == PARCEL_OUTPUTS[0]
                and path.parent.parent == old.parent
                and path.parent != old
            ):
                raise OSError("Synthetic hash read failure")
            return original_hash(path)

        monkeypatch.setattr(runs, "sha256_file", fail_hash)
    elif stage in {"manifest", "completion_write"}:
        original_write = runs.write_json if stage == "completion_write" else parcels.write_json

        def fail_write(path, payload):
            wanted = "completion.pending.json" if stage == "completion_write" else "manifest.json"
            if path.name == wanted and path.parent.parent == old.parent and path.parent != old:
                raise OSError("Synthetic record-write failure")
            return original_write(path, payload)

        monkeypatch.setattr(
            runs if stage == "completion_write" else parcels, "write_json", fail_write
        )
    else:
        original_replace = runs.os.replace

        def fail_replace(src, dst):
            if (
                stage == "completion_install"
                and dst.name == "completion.json"
                and dst.parent.parent == old.parent
                and dst.parent != old
            ) or (stage == "pointer_update" and dst == old.parent / "latest.json"):
                raise OSError(errno.EXDEV, "Synthetic cross-device/rename failure")
            return original_replace(src, dst)

        monkeypatch.setattr(runs.os, "replace", fail_replace)
    with pytest.raises((RuntimeError, OSError)):
        parcels.run_pipeline(fake_adapter(), Decimal(10))
    assert_previous(old, before, pointer, "parcel_processed")
    # Raw acquisition succeeded independently of the failed processed run.
    assert select_latest(settings.raw_dir / "isanti", "parcel_raw")
    if stage == "pointer_update":
        failed = next(path for path in old.parent.iterdir() if path.is_dir() and path != old)
        assert (failed / "completion.json").exists() and (failed / "failure.json").exists()


@pytest.mark.parametrize("part", ["mapping.json", "source.csv", "note.md"])
def test_R02_source_copy_failures_never_advance_raw_pointer(tmp_path, settings, monkeypatch, part):
    source, mapping = mixed_input(tmp_path)
    original = joins._copy_input

    def fail_copy(origin, target, limits):
        if target.name == part:
            raise OSError("Synthetic source-copy failure")
        return original(origin, target, limits)

    monkeypatch.setattr(joins, "_copy_input", fail_copy)
    with pytest.raises(OSError):
        joins.import_and_join_delinquency(
            source,
            mapping,
            Decimal(10),
            raw_root=settings.raw_dir,
            processed_root=settings.processed_dir,
        )
    root = workspace_path(settings.raw_dir / "isanti/delinquency")
    assert not list(root.glob("*/completion.json")) and not (root / "latest.json").exists()
    assert list(root.glob("*/failure.json"))


def test_R02_invalid_file_retains_original_bytes_and_bounded_failure(tmp_path, settings):
    source = tmp_path / "bad.csv"
    source.write_text(
        "Parcel ID,Taxpayer,Delinquent Year,Taxes/Penalties,Owner,Mailing Address\n020010200\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        joins.import_and_join_delinquency(
            source,
            FIXTURES / "isanti_delinquency_mapping.json",
            Decimal(10),
            raw_root=settings.raw_dir,
            processed_root=settings.processed_dir,
        )
    failure = next(workspace_path(settings.raw_dir).glob("isanti/delinquency/*/failure.json"))
    assert (failure.parent / "source.csv").read_bytes() == source.read_bytes()
    assert read_json(failure)["stage"] == "validate_retained_import"
    assert read_json(failure)["location"] == str(failure.parent)
    assert failure.stat().st_size < 16384


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "hash",
        "inventory",
        "kind",
        "county",
        "status",
        "version",
        "boolean",
        "provenance",
    ],
)
def test_R03_R06_readers_reject_invalid_completion(settings, make_raw, mutation):
    old = make_raw(settings.raw_dir)
    new = make_raw(settings.raw_dir)
    marker = new / "completion.json"
    record = read_json(marker)
    if mutation == "missing":
        (new / "page_00001.json").rename(new / "unlisted-page.json")
    elif mutation == "hash":
        (new / "page_00001.json").write_text("{}")
    elif mutation == "inventory":
        record["artifacts"].pop()
    elif mutation == "boolean":
        record["artifacts"][0]["bytes"] = True
    elif mutation == "provenance":
        record["provenance"] = {}
    else:
        key = "schema_version" if mutation == "version" else mutation
        record[key] = "invalid"
    if mutation not in {"missing", "hash"}:
        marker.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(RunValidationError):
        joins.load_parcel_snapshot(object(), new)
    diagnostics = []
    assert select_latest(new.parent, "parcel_raw", diagnostics=diagnostics).path == old
    assert diagnostics


@pytest.mark.parametrize(
    "name",
    ["../outside", "C:/outside", "/absolute", "a\\b", "a/../b", "NUL", "a:stream", "a//b", "a/./b"],
)
def test_R06_malicious_manifest_paths_fail_closed(settings, make_raw, name):
    path = make_raw(settings.raw_dir)
    marker = path / "completion.json"
    completion = read_json(marker)
    completion["artifacts"][0]["path"] = name
    marker.write_text(json.dumps(completion), encoding="utf-8")
    with pytest.raises(RunValidationError):
        validate_run(path, "parcel_raw")


def test_R06_legacy_is_read_only_deliberate_and_not_auto_certified(
    tmp_path, fake_adapter, capsys, settings
):
    path = settings.raw_dir / "isanti/legacy"
    path.mkdir(parents=True)
    (path / "manifest.json").write_text(
        json.dumps({"retrieved_at": "2026-01-01T00:00:00+00:00", "record_count": 1})
    )
    (path / "page_00001.json").write_bytes(
        b'{"features":[' + (FIXTURES / "isanti_parcel.json").read_bytes() + b"]}"
    )
    before = frozen_tree(path)
    with pytest.raises(RunValidationError):
        joins.load_latest_parcel_snapshot(fake_adapter(), path.parent)
    diagnostics = []
    records, errors, _ = joins.load_parcel_snapshot(
        fake_adapter(), path, allow_legacy=True, diagnostics=diagnostics
    )
    assert len(records) == 1 and errors == 0 and "legacy/unverified" in diagnostics[0]["reason"]
    assert frozen_tree(path) == before and not (path / "completion.json").exists()
    assert cli.main(["status", "--county", "isanti"]) == 0
    output = capsys.readouterr().out
    assert "NO ELIGIBLE COMPLETE RUN" in output and "Legacy/unverified" in output


def test_R03_manifest_only_cannot_be_empty_success(tmp_path, fake_adapter):
    path = tmp_path / "legacy"
    path.mkdir()
    (path / "manifest.json").write_text('{"retrieved_at":"2026-01-01T00:00:00+00:00"}')
    with pytest.raises(RunValidationError):
        joins.load_parcel_snapshot(fake_adapter(), path, allow_legacy=True)


@pytest.mark.parametrize("script", ["verify_isanti_review.py", "compare_isanti_reports.py"])
def test_R06_optional_report_tools_validate_review_before_work(tmp_path, monkeypatch, script):
    pdf_module = types.ModuleType("pypdf")
    pdf_module.PdfReader = lambda *args, **kwargs: pytest.fail("PDF read before review validation")
    errors = types.ModuleType("pypdf.errors")
    errors.PdfReadError = ValueError
    monkeypatch.setitem(sys.modules, "pypdf", pdf_module)
    monkeypatch.setitem(sys.modules, "pypdf.errors", errors)
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    runs.write_json(evidence / "manifest.json", {"review_dir": str(legacy)})
    argument, target = (
        ("--review-dir", legacy) if script.startswith("verify") else ("--evidence-dir", evidence)
    )
    monkeypatch.setattr(sys, "argv", [script, argument, str(target)])
    module = runpy.run_path(str(Path(__file__).parents[2] / "scripts" / script))
    with pytest.raises(RunValidationError):
        module["main"]()
    assert list(legacy.iterdir()) == []
    assert not (evidence / "comparison").exists()


def test_R06_interrupted_new_protocol_cannot_downgrade_to_legacy(tmp_path, fake_adapter):
    with RunWorkspace(tmp_path, "parcel_raw") as run:
        runs.write_json(
            run.path / "manifest.json",
            {"record_count": 0, "retrieved_at": "2026-01-01T00:00:00+00:00"},
        )
    with pytest.raises(RunValidationError, match="cannot use legacy"):
        joins.load_parcel_snapshot(fake_adapter(), run.path, allow_legacy=True)
    with pytest.raises(RunValidationError):
        select_latest(tmp_path, "parcel_raw")


@pytest.mark.parametrize(
    "pointer", [{"run_id": "../outside"}, {"run_id": "C:/outside"}, {"run_id": "missing"}, []]
)
def test_R06_invalid_pointers_fall_back_without_external_reads(settings, make_raw, pointer):
    source = make_raw(settings.raw_dir)
    (source.parent / "latest.json").write_text(json.dumps(pointer), encoding="utf-8")
    diagnostics = []
    assert select_latest(source.parent, "parcel_raw", diagnostics=diagnostics).path == source
    assert "invalid/stale latest" in diagnostics[0]["reason"]


def test_R06_symlink_artifact_cannot_escape_run(tmp_path, settings, make_raw, monkeypatch):
    source = make_raw(settings.raw_dir)
    outside = workspace_path(tmp_path / "outside.txt")
    outside.write_text("Synthetic outside evidence", encoding="utf-8")
    try:
        (source / "escape.txt").symlink_to(outside)
    except OSError:
        pytest.skip(
            "This local Windows account cannot create symlinks; hosted CI exercises this case"
        )
    opened = []
    original = Path.open

    def watch(self, *args, **kwargs):
        opened.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", watch)
    with pytest.raises(RunValidationError):
        validate_run(source, "parcel_raw")
    assert outside not in opened


def test_R06_available_legacy_hashes_are_enforced(tmp_path, fake_adapter):
    source = tmp_path / "legacy"
    source.mkdir()
    page = source / "page_00001.json"
    page.write_bytes(b'{"features":[' + (FIXTURES / "isanti_parcel.json").read_bytes() + b"]}")
    runs.write_json(
        source / "manifest.json",
        {
            "record_count": 1,
            "retrieved_at": "2026-01-01T00:00:00+00:00",
            "provenance": {"outputs": [{"path": str(page), "sha256": sha256_file(page)}]},
        },
    )
    page.write_text("{}", encoding="utf-8")
    with pytest.raises(RunValidationError, match="Legacy available artifact hash mismatch"):
        joins.load_parcel_snapshot(fake_adapter(), source, allow_legacy=True)


@pytest.mark.parametrize(
    "mutation", ["retrieved", "output_count", "partition", "diagnostics", "boolean"]
)
def test_R04_rehashed_but_inconsistent_accounting_is_not_complete(settings, fake_adapter, mutation):
    stats = parcels.run_pipeline(fake_adapter(), Decimal(10))
    path = stats.processed_run_dir
    marker = path / "completion.json"
    completion = read_json(marker)
    name = "manifest.json" if mutation in {"retrieved", "boolean"} else "accounting.json"
    payload = read_json(path / name)
    if mutation == "boolean":
        payload["retrieved"] = True
    elif mutation == "retrieved":
        payload["retrieved"] += 1
    elif mutation == "output_count":
        completion["row_counts"][PARCEL_OUTPUTS[0]] += 1
    elif mutation == "partition":
        payload["quarantined_source_ids"] = payload["normalized_source_ids"]
    else:
        payload["normalized_source_ids"] = []
    (path / name).write_text(json.dumps(payload), encoding="utf-8")
    for entry in completion["artifacts"]:
        if entry["path"] == name:
            entry.update(bytes=(path / name).stat().st_size, sha256=sha256_file(path / name))
    marker.write_text(json.dumps(completion), encoding="utf-8")
    with pytest.raises(RunValidationError):
        validate_run(path, "parcel_processed")


def test_R05_same_identity_reservation_is_exclusive(tmp_path):
    barrier = Barrier(2)

    def reserve():
        barrier.wait()
        try:
            with RunWorkspace(tmp_path, "parcel_raw", run_id="same"):
                return True
        except FileExistsError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: reserve(), range(2))) == [False, True]
    assert not (tmp_path / "same/failure.json").exists()


def test_R07_empty_candidates_are_complete_and_flat_outputs_untouched(settings, fake_adapter):
    settings.processed_dir.mkdir()
    flat = settings.processed_dir / "isanti_candidates.csv"
    flat.write_text("Existing historical flat export", encoding="utf-8")
    stats = parcels.run_pipeline(fake_adapter(), Decimal(1000))
    validated = validate_run(stats.processed_run_dir, "parcel_processed")
    assert set(validated.completion["row_counts"]) == set(PARCEL_OUTPUTS)
    assert validated.manifest["candidates"] == 0
    assert flat.read_text() == "Existing historical flat export"
    assert (
        select_latest(stats.processed_run_dir.parent, "parcel_processed").path
        == stats.processed_run_dir
    )


@pytest.mark.parametrize("held", [False, True])
def test_R04_R07_disjoint_rows_quarantine_overlap_and_holds(
    tmp_path, settings, fake_adapter, monkeypatch, held
):
    good = json.loads((FIXTURES / "isanti_parcel.json").read_text())
    duplicate = deepcopy(good)
    duplicate["attributes"].update(OBJECTID=102, PARCELID="030010100")
    duplicate2 = deepcopy(duplicate)
    duplicate2["attributes"]["OBJECTID"] = 103
    invalid = deepcopy(good)
    invalid["attributes"].update(OBJECTID=104, PARCELID=None)
    stats = parcels.run_pipeline(fake_adapter([good, duplicate, duplicate2, invalid]), Decimal(10))
    validated = validate_run(stats.processed_run_dir, "parcel_processed")
    assert validated.manifest["retrieved"] == 4 and validated.manifest["quarantined"] == 1
    error = read_json(stats.processed_run_dir / "normalization_diagnostics.json")[0]
    assert error["source_record_id"] == 104 and error["feature_number"] == 4
    source, mapping = mixed_input(tmp_path, held=held)
    joined = joins.import_and_join_delinquency(
        source,
        mapping,
        Decimal(10),
        raw_root=settings.raw_dir,
        processed_root=settings.processed_dir,
    )
    validated_join = validate_run(joined.processed_snapshot_dir, "delinquency_processed")
    accounting = read_json(joined.processed_snapshot_dir / "accounting.json")
    assert (
        accounting["matched"] == [2, 3, 4]
        and accounting["unmatched"] == [5]
        and accounting["ambiguous"] == [6]
    )
    assert accounting["duplicate_review"] == [2, 3, 4]
    assert accounting["prior_year"] == [2, 3, 5, 6] and accounting["current_year"] == [4]
    assert set(validated_join.completion["row_counts"]) == set(JOIN_OUTPUTS)
    prior = read_json(joined.processed_snapshot_dir / JOIN_OUTPUTS[1])
    current = read_json(joined.processed_snapshot_dir / "isanti_overdue_current_year_parcels.json")
    assert len(prior) == len(current) == (0 if held else 1)
    if not held:
        assert prior[0]["parcel_id"] == current[0]["parcel_id"]
        assert [row["source_row_number"] for row in prior[0]["delinquency_source_records"]] == [
            2,
            3,
        ]
        assert [row["source_row_number"] for row in current[0]["delinquency_source_records"]] == [4]
        assert prior[0]["total_taxes_and_penalties_due"] is None
    review = build_review(joined.processed_snapshot_dir)
    assert set(validate_run(review, "review").completion["row_counts"]) == set(REVIEW_OUTPUTS)
