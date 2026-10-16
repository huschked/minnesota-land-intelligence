"""H06-H08: real urllib transport with fake responses and deterministic time."""

import hashlib
import json
import socket
import ssl
from datetime import UTC, datetime
from email.utils import formatdate
from http.client import IncompleteRead
from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from mn_land.config.retrieval import RetrievalPolicy
from mn_land.ingestion.arcgis import ArcGISClient
from mn_land.utils.http import ArcGISError, UrllibJsonTransport, _NoRedirect


class Clock:
    def __init__(self):
        self.now = 0.0
        self.waits = []

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds

    def transport(self, **config):
        return UrllibJsonTransport(
            policy=RetrievalPolicy(**config),
            monotonic=lambda: self.now,
            wall_time=lambda: 1700000000 + self.now,
            sleep=self.sleep,
        )


class Response(BytesIO):
    def __init__(self, body=b"{}", status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}


def install(monkeypatch, outcomes):
    calls = []
    iterator = iter(outcomes)

    def open_response(request, timeout):
        calls.append((request, timeout))
        value = next(iterator)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr("mn_land.utils.http.urlopen", open_response)
    return calls


@pytest.mark.parametrize("status", [400, 401, 403, 404, 405, 501])
def test_H06_permanent_HTTP_never_retried(monkeypatch, status):
    calls = install(
        monkeypatch,
        [
            HTTPError(
                "https://example.test?token=SECRET", status, "server SECRET", {}, BytesIO(b"denied")
            )
        ],
    )
    clock = Clock()
    with pytest.raises(ArcGISError, match=f"HTTP {status}") as error:
        clock.transport().get_json("https://example.test", {})
    assert len(calls) == 1 and clock.waits == []
    assert "SECRET" not in str(error.value)


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_H06_transient_HTTP_exact_attempts_backoff_timeout(monkeypatch, status):
    calls = install(monkeypatch, [Response(status=status) for _ in range(3)])
    clock = Clock()
    with pytest.raises(ArcGISError, match="attempts=3"):
        clock.transport(timeout_seconds=7).get_json("https://example.test", {})
    assert [timeout for _, timeout in calls] == [7, 7, 7]
    assert clock.waits == [1, 2]


@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError(),
        ConnectionResetError(),
        URLError(TimeoutError()),
        URLError(ConnectionRefusedError()),
        URLError(socket.gaierror(socket.EAI_AGAIN, "temporary")),
    ],
)
def test_H06_transient_connections_succeed_on_retry(monkeypatch, failure):
    calls = install(monkeypatch, [failure, Response(b'{"ok":true}')])
    clock = Clock()
    assert clock.transport().get_json("https://example.test", {}) == {"ok": True}
    assert len(calls) == 2 and clock.waits == [1]


@pytest.mark.parametrize(
    "failure",
    [
        URLError(ssl.SSLError("certificate")),
        URLError("unknown reason"),
        URLError(socket.gaierror(socket.EAI_NONAME, "missing host")),
    ],
)
def test_H06_unknown_or_permanent_network_not_retried(monkeypatch, failure):
    calls = install(monkeypatch, [failure])
    clock = Clock()
    with pytest.raises(ArcGISError):
        clock.transport().get_json("https://example.test", {})
    assert len(calls) == 1 and clock.waits == []


@pytest.mark.parametrize(
    "header,wait",
    [
        ("30", 30),
        (formatdate(1700000030, usegmt=True), 30),
        ("invalid", 1),
        (formatdate(1699999999, usegmt=True), 1),
        ("-1", 1),
        ("0", 1),
    ],
)
def test_H07_retry_after_delta_date_and_fallback(monkeypatch, header, wait):
    calls = install(
        monkeypatch, [Response(status=429, headers={"Retry-After": header}), Response()]
    )
    clock = Clock()
    clock.transport().get_json("https://example.test", {})
    assert len(calls) == 2 and clock.waits == [wait]


@pytest.mark.parametrize(
    "header", ["61", "9999999999999999999999999999999999999", formatdate(1700000061, usegmt=True)]
)
def test_H07_excessive_server_delay_stops_never_retries_early(monkeypatch, header):
    calls = install(monkeypatch, [Response(status=429, headers={"Retry-After": header})])
    clock = Clock()
    with pytest.raises(ArcGISError, match="Retry later"):
        clock.transport().get_json("https://example.test", {})
    assert len(calls) == 1 and clock.waits == []


def test_H07_cumulative_budget_spans_successive_requests(monkeypatch):
    calls = install(
        monkeypatch,
        [
            Response(status=429, headers={"Retry-After": "60"}),
            Response(),
            Response(status=503, headers={"Retry-After": "60"}),
        ],
    )
    clock = Clock()
    transport = clock.transport()
    transport.get_json("https://example.test", {})
    with pytest.raises(ArcGISError, match="Retry later"):
        transport.get_json("https://example.test", {})
    assert len(calls) == 3 and clock.waits == [60, 1]


def test_H07_successful_requests_paced_and_elapsed_time_counts(monkeypatch):
    install(monkeypatch, [Response(), Response(), Response()])
    clock = Clock()
    transport = clock.transport(min_request_spacing=2)
    transport.get_json("https://example.test", {})
    transport.get_json("https://example.test", {})
    clock.now += 3
    transport.get_json("https://example.test", {})
    assert clock.waits == [2]


@pytest.mark.parametrize(
    "key",
    [
        "timeout_seconds",
        "min_request_spacing",
        "backoff_seconds",
        "max_single_wait",
        "max_total_wait",
    ],
)
@pytest.mark.parametrize("bad", [0, -1, True, "3", float("nan"), float("inf")])
def test_H07_invalid_finite_config(key, bad):
    with pytest.raises(ValueError):
        RetrievalPolicy(**{key: bad})


@pytest.mark.parametrize("key", ["max_attempts", "max_body_bytes", "max_inventory_ids"])
@pytest.mark.parametrize("bad", [0, -1, True, 1.5, "3"])
def test_H07_invalid_integer_config(key, bad):
    with pytest.raises(ValueError):
        RetrievalPolicy(**{key: bad})


@pytest.mark.parametrize("body", [b"invalid", b"\xff", b'{"incomplete":'])
def test_H08_invalid_JSON_retried_with_original_evidence(monkeypatch, tmp_path, body):
    calls = install(monkeypatch, [Response(body), Response()])
    clock = Clock()
    transport = clock.transport()
    transport.begin_capture(tmp_path / "http")
    assert transport.get_json("https://example.test?secret=SECRET", {}) == {}
    first = json.loads((tmp_path / "http/attempt_00001.evidence.json").read_text())
    assert first["body"]["sha256"] == hashlib.sha256(body).hexdigest()
    assert (tmp_path / "http/attempt_00001.body").read_bytes() == body
    assert "parsed" not in first and first["outcome"] == "invalid JSON"
    assert len(calls) == 2 and clock.waits == [1]
    assert "SECRET" not in json.dumps(first)


@pytest.mark.parametrize(
    "body", [b"[]", b"null", b"true", b'{"a":NaN}', b'{"a":Infinity}', b'{"a":"\\ud800"}']
)
def test_H08_invalid_schema_or_nonfinite_not_retried(monkeypatch, tmp_path, body):
    calls = install(monkeypatch, [Response(body)])
    transport = Clock().transport()
    transport.begin_capture(tmp_path / "http")
    with pytest.raises(ArcGISError):
        transport.get_json("https://example.test", {})
    assert len(calls) == 1
    assert (tmp_path / "http/attempt_00001.body").read_bytes() == body


@pytest.mark.parametrize(
    "code,retry",
    [
        (400, False),
        (401, False),
        (403, False),
        (498, False),
        (499, False),
        (500, False),
        (999, False),
        (True, False),
        ("503", False),
        (429, True),
        (503, True),
        (504, True),
    ],
)
def test_H08_ArcGIS_errors_explicit_allowlist(monkeypatch, code, retry):
    body = json.dumps({"error": {"code": code, "message": "SECRET"}}).encode()
    calls = install(monkeypatch, [Response(body), Response()])
    clock = Clock()
    if retry:
        assert clock.transport().get_json("https://example.test", {}) == {}
    else:
        with pytest.raises(ArcGISError) as error:
            clock.transport().get_json("https://example.test", {})
        assert "SECRET" not in str(error.value)
    assert len(calls) == (2 if retry else 1)


@pytest.mark.parametrize("body,success", [(b"{}", True), (b"{} ", False)])
def test_H08_body_budget_exact_boundary(monkeypatch, tmp_path, body, success):
    calls = install(monkeypatch, [Response(body)])
    transport = Clock().transport(max_body_bytes=2)
    transport.begin_capture(tmp_path / "http")
    if success:
        assert transport.get_json("https://example.test", {}) == {}
    else:
        with pytest.raises(ArcGISError, match="body byte budget"):
            transport.get_json("https://example.test", {})
    assert len(calls) == 1
    record = json.loads((tmp_path / "http/attempt_00001.evidence.json").read_text())
    assert record["body"]["bytes"] == 2
    assert record["body_truncated"] is not success


def test_H08_truncated_HTTP_body_retry_and_close(monkeypatch, tmp_path):
    class Partial(Response):
        def read(self, size):
            raise IncompleteRead(b'{"partial":', 50)

    response = Partial()
    install(monkeypatch, [response, Response()])
    transport = Clock().transport()
    transport.begin_capture(tmp_path / "http")
    assert transport.get_json("https://example.test", {}) == {}
    assert response.closed
    record = json.loads((tmp_path / "http/attempt_00001.evidence.json").read_text())
    assert record["body_incomplete"]
    assert (tmp_path / "http/attempt_00001.body").read_bytes() == b'{"partial":'


def test_H08_mismatched_content_length_retries(monkeypatch):
    calls = install(monkeypatch, [Response(headers={"Content-Length": "99"}), Response()])
    assert Clock().transport().get_json("https://example.test", {}) == {}
    assert len(calls) == 2


def test_H08_timeout_mid_body_retains_received_prefix(monkeypatch, tmp_path):
    class Partial(Response):
        def read(self, size):
            if self.tell() > 0:
                raise TimeoutError()
            return super().read(size)

    install(monkeypatch, [Partial(b'{"prefix":'), Response()])
    transport = Clock().transport()
    transport.begin_capture(tmp_path / "http")
    assert transport.get_json("https://example.test", {}) == {}
    assert (tmp_path / "http/attempt_00001.body").read_bytes() == b'{"prefix":'


def test_H08_redirects_are_not_silently_followed():
    assert (
        _NoRedirect().redirect_request(None, None, 302, "Moved", {}, "https://other.test") is None
    )


def test_H08_permanent_HTTP_JSON_retains_parsed_hash(monkeypatch, tmp_path):
    install(monkeypatch, [Response(b'{"error":{"code":403}}', status=403)])
    transport = Clock().transport()
    transport.begin_capture(tmp_path / "http")
    with pytest.raises(ArcGISError):
        transport.get_json("https://example.test", {})
    evidence = json.loads((tmp_path / "http/attempt_00001.evidence.json").read_text())
    assert (
        evidence["parsed"]["sha256"]
        == hashlib.sha256((tmp_path / "http" / evidence["parsed"]["file"]).read_bytes()).hexdigest()
    )


def test_H08_acquisition_failure_keeps_attempts_and_intended_artifact(monkeypatch, tmp_path):
    install(monkeypatch, [Response(status=429, headers={"Retry-After": "999"})])
    transport = Clock().transport()
    client = ArcGISClient("https://example.test", 0, transport=transport)
    with pytest.raises(ArcGISError, match="Retry later"):
        list(
            client.fetch_all(
                out_fields=("OID",), raw_run_dir=tmp_path / "run", retrieved_at=datetime.now(UTC)
            )
        )
    assert transport._capture_dir is None
    request = json.loads((tmp_path / "run/failed_request.json").read_text())
    assert request["http_attempt_range"] == [1, 1]
    assert request["intended_artifact"] == "layer_metadata.json"
    failure = json.loads((tmp_path / "run/retrieval_failure.json").read_text())
    assert "Retry later" in failure["reason"]
    assert not (tmp_path / "run/manifest.json").exists()


def test_H08_full_real_transport_acquisition_hashes_and_request_associations(monkeypatch, tmp_path):
    metadata = {
        "id": 0,
        "name": "Synthetic",
        "objectIdField": "OID",
        "capabilities": "Query",
        "maxRecordCount": 2,
        "advancedQueryCapabilities": {"supportsPagination": True, "supportsOrderBy": True},
        "fields": [{"name": "OID", "type": "esriFieldTypeOID", "nullable": False}],
    }
    ids = {"objectIdFieldName": "OID", "objectIds": [1]}
    responses = [
        metadata,
        {"count": 1},
        ids,
        {"features": [{"attributes": {"OID": 1}}]},
        {"count": 1},
        ids,
        metadata,
    ]
    calls = install(monkeypatch, [Response(json.dumps(payload).encode()) for payload in responses])
    transport = Clock().transport()
    client = ArcGISClient("https://example.test", 0, transport=transport)
    run = tmp_path / "run"
    assert (
        len(
            list(
                client.fetch_all(
                    out_fields=("OID",),
                    raw_run_dir=run,
                    retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
                )
            )
        )
        == 1
    )
    assert len(calls) == 7 and transport._capture_dir is None
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["attempts"] == 7 and manifest["total_wait_seconds"] == 6
    assert len(manifest["provenance"]["outputs"]) == 28
    for artifact in manifest["provenance"]["outputs"]:
        from pathlib import Path

        assert hashlib.sha256(Path(artifact["path"]).read_bytes()).hexdigest() == artifact["sha256"]
    for index, observation in enumerate(manifest["source_checks"]["observations"], 1):
        assert observation["http_attempt_range"] == [index, index]
        evidence = json.loads((run / f"http/attempt_{index:05d}.evidence.json").read_text())
        for field in ("body", "parsed"):
            assert (
                evidence[field]["sha256"]
                == hashlib.sha256((run / "http" / evidence[field]["file"]).read_bytes()).hexdigest()
            )
