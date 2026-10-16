"""Keep ordinary fixture tests from making accidental network requests."""

import json
import socket
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def block_network_for_offline_tests(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if request.node.get_closest_marker("integration") is not None:
        return

    def blocked(*args: object, **kwargs: object) -> None:
        pytest.fail(
            "Network access is disabled for offline tests. Mock the transport, "
            "or mark an intentional live-source test with @pytest.mark.integration."
        )

    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


@pytest.fixture
def fake_adapter():
    from mn_land.counties.isanti import IsantiAdapter
    from mn_land.counties.isanti.schema import EXPECTED_ALIASES, EXPECTED_TYPES
    from mn_land.ingestion.arcgis import ArcGISClient

    def make(records=None):
        if records is None:
            records = [
                json.loads(
                    (Path(__file__).parent / "fixtures/isanti_parcel.json").read_text(
                        encoding="utf-8"
                    )
                )
            ]
        records = deepcopy(records)

        class Transport:
            def get_json(self, url, params):
                if not url.endswith("/query"):
                    return {
                        "id": 0,
                        "name": "TaxParcels_Public",
                        "objectIdField": "OBJECTID",
                        "maxRecordCount": 2000,
                        "capabilities": "Query",
                        "advancedQueryCapabilities": {
                            "supportsPagination": True,
                            "supportsOrderBy": True,
                        },
                        "fields": [
                            {
                                "name": name,
                                "type": kind,
                                "nullable": name != "OBJECTID",
                                "alias": EXPECTED_ALIASES[name],
                            }
                            for name, kind in EXPECTED_TYPES.items()
                        ],
                    }
                if params.get("returnCountOnly"):
                    return {"count": len(records)}
                if params.get("returnIdsOnly"):
                    return {
                        "objectIdFieldName": "OBJECTID",
                        "objectIds": [record["attributes"]["OBJECTID"] for record in records],
                    }
                offset, size = params["resultOffset"], params["resultRecordCount"]
                return {"features": records[offset : offset + size]}

        return IsantiAdapter(
            ArcGISClient("https://example.test/FeatureServer", 0, transport=Transport())
        )

    return make


@pytest.fixture
def make_raw(fake_adapter):
    from mn_land.runs import RunWorkspace

    def make(root, records=None):
        adapter = fake_adapter(records)
        with RunWorkspace(root / "isanti", "parcel_raw") as run:
            list(
                adapter.fetch_parcels(
                    run.path, datetime(2026, 1, 1, tzinfo=UTC), directory_reserved=True
                )
            )
            run.publish()
        return run.path

    return make
