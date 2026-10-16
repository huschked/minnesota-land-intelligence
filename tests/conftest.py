"""Keep ordinary fixture tests from making accidental network requests."""

import json
import socket
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest

_phase_maxima: dict[str, tuple[float, str]] = {}


def pytest_sessionstart(session: pytest.Session) -> None:
    _phase_maxima.clear()


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.duration > _phase_maxima.get(report.when, (-1.0, ""))[0]:
        _phase_maxima[report.when] = (report.duration, report.nodeid)


def pytest_terminal_summary(terminalreporter) -> None:
    if _phase_maxima:
        terminalreporter.write_sep("-", "slowest test by phase (seconds)")
        for phase in ("setup", "call", "teardown"):
            if phase in _phase_maxima:
                duration, nodeid = _phase_maxima[phase]
                terminalreporter.write_line(f"{phase}: {duration:.4f}s {nodeid}")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--real-test-git", action="store_true",
        help="Benchmark with real Git identity in every fixture; dedicated provenance tests always do.",
    )


@pytest.fixture(autouse=True)
def synthetic_git_identity(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not launch Git three times per synthetic pipeline provenance record.

    Only the external Git identity is mocked. Source/artifact/configuration hashes,
    runtime inspection and every production validator still execute normally.
    Dedicated provenance and live tests opt out; benchmarks can opt out globally.
    """
    if (
        request.config.getoption("--real-test-git")
        or request.node.get_closest_marker("real_git") is not None
        or request.node.get_closest_marker("integration") is not None
    ):
        return
    monkeypatch.setattr(
        "mn_land.provenance._git_identity",
        lambda root: {"revision": None, "dirty": None, "status": "synthetic_test_fixture"},
    )


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
