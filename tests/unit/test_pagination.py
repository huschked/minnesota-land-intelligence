from pathlib import Path

import pytest

from mn_land.ingestion.arcgis import ArcGISClient
from mn_land.utils.http import ArcGISError


class FakeTransport:
    def __init__(self, features: list[dict]) -> None:
        self.features = features
        self.offsets: list[int] = []

    def get_json(self, url: str, params: dict) -> dict:
        if not url.endswith("/query"):
            return {
                "id": 0,
                "name": "Synthetic",
                "objectIdField": "OBJECTID",
                "maxRecordCount": 2,
                "capabilities": "Query",
                "advancedQueryCapabilities": {
                    "supportsPagination": True,
                    "supportsOrderBy": True,
                },
                "fields": [{"name": "OBJECTID", "type": "esriFieldTypeOID", "nullable": False}],
            }
        if params.get("returnCountOnly") == "true":
            return {"count": len(self.features)}
        if params.get("returnIdsOnly") == "true":
            return {
                "objectIdFieldName": "OBJECTID",
                "objectIds": [feature["attributes"]["OBJECTID"] for feature in self.features],
            }
        offset = int(params["resultOffset"])
        size = int(params["resultRecordCount"])
        self.offsets.append(offset)
        return {"features": self.features[offset : offset + size]}


def test_pagination_fetches_each_record_once(tmp_path: Path) -> None:
    features = [{"attributes": {"OBJECTID": i}} for i in range(1, 6)]
    transport = FakeTransport(features)
    client = ArcGISClient("https://example.test/FeatureServer", 0, page_size=2, transport=transport)
    records = list(
        client.fetch_all(
            out_fields=("OBJECTID",),
            raw_run_dir=tmp_path / "run",
            retrieved_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
    )
    assert records == features
    assert transport.offsets == [0, 2, 4]
    assert len(list((tmp_path / "run").glob("page_*.json"))) == 3


def test_duplicate_object_id_fails(tmp_path: Path) -> None:
    features = [{"attributes": {"OBJECTID": 1}}, {"attributes": {"OBJECTID": 1}}]
    client = ArcGISClient(
        "https://example.test/FeatureServer", 0, page_size=2, transport=FakeTransport(features)
    )
    with pytest.raises(ArcGISError, match="Duplicate"):
        list(
            client.fetch_all(
                out_fields=("OBJECTID",),
                raw_run_dir=tmp_path / "run",
                retrieved_at=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ),
            )
        )
