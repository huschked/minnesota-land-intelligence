from __future__ import annotations

import json
import time
from collections.abc import Mapping
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ArcGISError(RuntimeError):
    """A clear, source-facing ArcGIS failure."""


class JsonTransport(Protocol):
    def get_json(self, url: str, params: Mapping[str, Any]) -> dict[str, Any]: ...


class UrllibJsonTransport:
    def __init__(self, timeout: float = 30.0, max_retries: int = 3) -> None:
        self.timeout = timeout
        self.max_retries = max_retries

    def get_json(self, url: str, params: Mapping[str, Any]) -> dict[str, Any]:
        target = f"{url}?{urlencode(params)}"
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                request = Request(target, headers={"User-Agent": "mn-land-intelligence/0.2"})
                with urlopen(request, timeout=self.timeout) as response:
                    payload = json.load(response)
                if not isinstance(payload, dict):
                    raise ArcGISError("ArcGIS returned a non-object JSON response")
                if "error" in payload:
                    raise ArcGISError(f"ArcGIS error: {payload['error']}")
                return payload
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt + 1 < self.max_retries:
                    time.sleep(0.5 * (2**attempt))
        raise ArcGISError(f"Unable to retrieve {url}: {last_error}") from last_error
