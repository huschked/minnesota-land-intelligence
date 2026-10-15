import json
from decimal import Decimal
from pathlib import Path

from mn_land.counties.isanti import IsantiAdapter
from mn_land.delinquency.pipeline import import_and_join_delinquency
from mn_land.provenance import sha256_file

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_import_snapshots_joins_and_exports_without_overwrite(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    parcel_snapshot = raw_root / "isanti" / "2026-08-23T000000Z"
    parcel_snapshot.mkdir(parents=True)
    parcel_record = json.loads((FIXTURES / "isanti_parcel.json").read_text(encoding="utf-8"))
    (parcel_snapshot / "page_00001.json").write_text(
        json.dumps({"features": [parcel_record]}), encoding="utf-8"
    )
    (parcel_snapshot / "manifest.json").write_text(
        json.dumps({"retrieved_at": "2026-08-23T00:00:00+00:00", "record_count": 1}),
        encoding="utf-8",
    )
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
    assert str((stats.raw_snapshot_dir / "mapping.json").resolve()) in {
        artifact["path"] for artifact in provenance["inputs"]
    }
    for artifact in provenance["inputs"] + provenance["outputs"]:
        assert sha256_file(Path(artifact["path"])) == artifact["sha256"]
