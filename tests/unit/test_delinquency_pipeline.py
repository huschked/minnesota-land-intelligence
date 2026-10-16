import json
from decimal import Decimal
from pathlib import Path

from mn_land.counties.isanti import IsantiAdapter
from mn_land.delinquency.pipeline import import_and_join_delinquency
from mn_land.provenance import sha256_file

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_import_snapshots_joins_and_exports_without_overwrite(tmp_path: Path, make_raw) -> None:
    raw_root = tmp_path / "raw"
    make_raw(raw_root)
    stats = import_and_join_delinquency(
        FIXTURES / "isanti_delinquency.csv",
        FIXTURES / "isanti_delinquency_mapping.json",
        Decimal(10),
        adapter=IsantiAdapter(client=object()),
        raw_root=raw_root,
        processed_root=tmp_path / "processed",
    )
    assert stats.records_loaded == 1
    assert stats.exact_matches == 1
    assert stats.verified_candidates == 1
    assert (stats.raw_snapshot_dir / "source.csv").is_file()
    assert (stats.raw_snapshot_dir / "mapping.json").is_file()
    assert (stats.processed_snapshot_dir / "isanti_verified_delinquent_candidates.json").is_file()
    manifest = json.loads((stats.processed_snapshot_dir / "manifest.json").read_text())
    provenance = manifest["provenance"]
    assert provenance["configuration"]["minimum_acres"] == "10"
    assert str((Path(manifest["delinquency_snapshot"]) / "mapping.json").resolve()) in {
        artifact["path"] for artifact in provenance["inputs"]
    }
    for artifact in provenance["inputs"] + provenance["outputs"]:
        assert sha256_file(Path(artifact["path"])) == artifact["sha256"]
