import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from mn_land import __version__, provenance
from mn_land.config.settings import Settings
from mn_land.counties.isanti import IsantiAdapter
from mn_land.counties.isanti.schema import EXPECTED_ALIASES, EXPECTED_TYPES
from mn_land.ingestion.arcgis import ArcGISClient
from mn_land.ingestion.pipeline import run_pipeline
from mn_land.provenance import build_provenance, sha256_file


def test_provenance_hashes_effective_configuration_and_artifact_bytes(tmp_path: Path) -> None:
    artifact = tmp_path / "source.json"
    artifact.write_bytes(b"original")
    first = build_provenance({"b": 2, "a": "10"}, inputs=[artifact], outputs=[artifact])
    reordered = build_provenance({"a": "10", "b": 2})
    changed = build_provenance({"a": "11", "b": 2})
    assert first["schema_version"] == 1
    assert first["configuration_sha256"] == reordered["configuration_sha256"]
    assert first["configuration_sha256"] != changed["configuration_sha256"]
    assert (
        first["inputs"]
        == first["outputs"]
        == [{"path": str(artifact.resolve()), "sha256": hashlib.sha256(b"original").hexdigest()}]
    )
    assert first["code"]["package_version"] == __version__
    assert "provenance.py" in first["code"]["python_source_files"]
    assert any(d["name"] == "openpyxl" for d in first["runtime"]["installed_distributions"])
    assert first["runtime"]["constraints_sha256"] == sha256_file(
        provenance.PROJECT_ROOT / "constraints-dev.txt"
    )
    json.dumps(first, allow_nan=False)
    artifact.write_bytes(b"changed")
    assert sha256_file(artifact) != first["inputs"][0]["sha256"]


def test_missing_artifact_is_not_silently_omitted(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_provenance({}, inputs=[tmp_path / "missing"])


@pytest.mark.parametrize("dirty", [True, False])
def test_git_revision_and_dirty_state_are_independent(monkeypatch, tmp_path, dirty) -> None:
    def run(args, **kwargs):
        assert "--no-optional-locks" in args
        assert kwargs["timeout"] == 5
        if "--show-toplevel" in args:
            value = str(tmp_path)
        elif "status" in args:
            value = "?? new-file.py" if dirty else ""
        else:
            value = "a" * 40
        return subprocess.CompletedProcess(args, 0, stdout=value)

    monkeypatch.setattr(subprocess, "run", run)
    assert provenance._git_identity(tmp_path) == {
        "revision": "a" * 40,
        "dirty": dirty,
        "status": "available",
    }


@pytest.mark.parametrize("error", [FileNotFoundError(), subprocess.TimeoutExpired("git", 5)])
def test_unavailable_git_is_explicitly_unknown(monkeypatch, tmp_path, error) -> None:
    def run(*args, **kwargs):
        raise error

    monkeypatch.setattr(subprocess, "run", run)
    assert provenance._git_identity(tmp_path) == {
        "revision": None,
        "dirty": None,
        "status": "unavailable",
    }


def test_unborn_head_does_not_claim_a_revision(monkeypatch, tmp_path) -> None:
    def run(args, **kwargs):
        if "--show-toplevel" in args:
            return subprocess.CompletedProcess(args, 0, stdout=str(tmp_path))
        if "status" in args:
            return subprocess.CompletedProcess(args, 0, stdout="?? src/")
        raise subprocess.CalledProcessError(128, args)

    monkeypatch.setattr(subprocess, "run", run)
    assert provenance._git_identity(tmp_path) == {
        "revision": None,
        "dirty": True,
        "status": "unavailable",
    }


def test_unrelated_enclosing_repository_is_not_claimed(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kw: subprocess.CompletedProcess(
            args,
            0,
            stdout=str(tmp_path.parent),
        ),
    )
    assert provenance._git_identity(tmp_path)["revision"] is None


def test_offline_parcel_pipeline_records_output_and_source_hashes(tmp_path, monkeypatch) -> None:
    from mn_land.ingestion import pipeline

    record = json.loads(
        (Path(__file__).parents[1] / "fixtures/isanti_parcel.json").read_text(encoding="utf-8")
    )

    class Transport:
        def get_json(self, url, params):
            if not url.endswith("/query"):
                return {
                    "id": 0,
                    "name": "TaxParcels_Public",
                    "maxRecordCount": 2000,
                    "capabilities": "Query",
                    "advancedQueryCapabilities": {
                        "supportsPagination": True,
                        "supportsOrderBy": True,
                    },
                    "objectIdField": "OBJECTID",
                    "fields": [
                        {
                            "name": name,
                            "type": kind,
                            "nullable": name != "OBJECTID",
                            "alias": EXPECTED_ALIASES.get(name, name),
                        }
                        for name, kind in EXPECTED_TYPES.items()
                    ],
                }
            if params.get("returnCountOnly"):
                return {"count": 1}
            if params.get("returnIdsOnly"):
                return {
                    "objectIdFieldName": "OBJECTID",
                    "objectIds": [record["attributes"]["OBJECTID"]],
                }
            return {"features": [record]}

    monkeypatch.setattr(
        pipeline,
        "SETTINGS",
        Settings(
            raw_dir=tmp_path / "raw",
            processed_dir=tmp_path / "processed",
        ),
    )
    adapter = IsantiAdapter(
        client=ArcGISClient(
            "https://example.test/FeatureServer",
            0,
            transport=Transport(),
        )
    )
    stats = run_pipeline(adapter, __import__("decimal").Decimal(10))
    manifest = json.loads((stats.raw_run_dir / "manifest.json").read_text())
    assert manifest["provenance"]["configuration"]["service_url"].startswith("https://example")
    assert len(manifest["provenance"]["outputs"]) == 7
    execution = json.loads((stats.raw_run_dir / "execution.json").read_text())
    assert execution["configuration"]["minimum_acres"] == "10"
    assert len(execution["outputs"]) == 4
    for artifact in execution["outputs"] + execution["inputs"]:
        assert artifact["sha256"] == sha256_file(Path(artifact["path"]))
