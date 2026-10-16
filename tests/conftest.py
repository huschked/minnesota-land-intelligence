"""Keep ordinary fixture tests from making accidental network requests."""

import json
import socket
import sys
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

    # Windows asyncio implements socketpair() with one loopback TCP connection.
    # AppTest needs that private self-wakeup channel, not general loopback/network
    # access. Keep every ordinary connect/DNS call blocked: only this no-address-
    # accepting pair factory can use the captured connect on its own new socket.
    if sys.platform == "win32" and request.node.get_closest_marker("ui") is not None:
        original_connect = socket.socket.connect

        def wakeup_pair():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen(1)
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    original_connect(client, listener.getsockname())
                    server, _ = listener.accept()
                    return server, client
                except BaseException:
                    client.close()
                    raise

        monkeypatch.setattr(socket, "socketpair", wakeup_pair)

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
def viewer_data(tmp_path, make_raw, fake_adapter):
    """Genuine completion graphs from small, explicitly synthetic local inputs."""
    from decimal import Decimal

    from mn_land.counties.isanti.review import build_review
    from mn_land.delinquency.pipeline import import_and_join_delinquency

    def make(*, held=False, empty=False):
        raw = make_raw(tmp_path / "raw", [] if empty else None)
        source = tmp_path / "viewer-source.csv"
        source.write_text(
            "PARID,OWN1,ASMTYR,TAXYR,TOTAMT\n"
            "020010200,Synthetic owner,2024,2025,100\n"
            "020010200,Synthetic owner,2025,2025,100\n",
            encoding="utf-8",
        )
        note = tmp_path / "viewer-years.md"
        note.write_text("Synthetic test convention evidence", encoding="utf-8")
        mapping = tmp_path / "viewer-mapping.json"
        mapping.write_text(json.dumps({
            "source_agency": "Isanti County - synthetic fixture",
            "dataset": "Synthetic test fixture",
            "publication_date": "2026-01-01",
            "delinquency_assertion": "mixed_unpaid_prior_and_overdue_current_year_taxes",
            "tax_year_convention": "isanti_assessment_year_plus_one",
            "year_semantics_reference": note.name,
            "supporting_documents": [note.name],
            "verification_hold_reason": "Synthetic hold <script>not markup</script>" if held else None,
            "columns": {"parcel_id": "PARID", "owner_name": "OWN1"},
        }), encoding="utf-8")
        joined = import_and_join_delinquency(
            source, mapping, Decimal(10), adapter=fake_adapter(),
            raw_root=tmp_path / "raw", processed_root=tmp_path / "processed",
            parcel_snapshot=raw,
        )
        review = build_review(joined.processed_snapshot_dir)
        return tmp_path / "processed", joined, review

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
