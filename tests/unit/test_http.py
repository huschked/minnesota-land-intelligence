import json
from io import BytesIO
from urllib.error import URLError

import pytest

from mn_land.utils.http import ArcGISError, UrllibJsonTransport


class Response(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_invalid_json_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("mn_land.utils.http.urlopen", lambda *a, **k: Response(b"not-json"))
    with pytest.raises(ArcGISError, match="Unable to retrieve"):
        UrllibJsonTransport(max_retries=1).get_json("https://example.test", {})


def test_network_error_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args, **kwargs):
        raise URLError("offline")
    monkeypatch.setattr("mn_land.utils.http.urlopen", fail)
    with pytest.raises(ArcGISError, match="offline"):
        UrllibJsonTransport(max_retries=1).get_json("https://example.test", {})


def test_arcgis_error_payload_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps({"error": {"message": "bad query"}}).encode()
    monkeypatch.setattr("mn_land.utils.http.urlopen", lambda *a, **k: Response(payload))
    with pytest.raises(ArcGISError, match="bad query"):
        UrllibJsonTransport(max_retries=1).get_json("https://example.test", {})
