from __future__ import annotations

import errno
import hashlib
import json
import socket
import ssl
import time
from collections.abc import Callable, Mapping
from email.utils import parsedate_to_datetime
from http.client import IncompleteRead
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from mn_land.config.retrieval import RetrievalPolicy

TRANSIENT_HTTP = frozenset({408, 429, 500, 502, 503, 504})
# Conservative application-code allowlist. ArcGIS 500 can describe invalid queries;
# unknown/vendor codes fail closed rather than inheriting HTTP retry semantics.
TRANSIENT_ARCGIS = frozenset({429, 503, 504})


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A redirect is another request and potentially another source. Do not
        # silently follow it outside our pacing/evidence/authoritative-source checks.
        return None


def urlopen(request: Request, *, timeout: float) -> Any:
    return build_opener(_NoRedirect()).open(request, timeout=timeout)


class ArcGISError(RuntimeError):
    """A source-facing failure, without echoing URLs, bodies or server messages."""


class JsonTransport(Protocol):
    def get_json(self, url: str, params: Mapping[str, Any]) -> dict[str, Any]: ...


class UrllibJsonTransport:
    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        *,
        policy: RetrievalPolicy | None = None,
        monotonic: Callable[[], float] | None = None,
        wall_time: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.policy = policy or RetrievalPolicy(timeout_seconds=timeout, max_attempts=max_retries)
        self.timeout = self.policy.timeout_seconds
        self.max_retries = self.policy.max_attempts  # Historical name means TOTAL attempts.
        self._clock = monotonic or time.monotonic
        self._wall_time = wall_time or time.time
        self._sleep = sleep or time.sleep
        self._capture_dir: Path | None = None
        self._last_started: float | None = None
        self._attempt_number = 0
        self.total_wait = 0.0

    def begin_capture(self, directory: Path) -> None:
        if self._capture_dir is not None:
            raise ArcGISError("Concurrent capture on one transport is not supported")
        directory.mkdir(exist_ok=False)
        self._capture_dir = directory
        self._attempt_number = 0
        self.total_wait = 0.0
        # Keep pacing across adjacent runs on the same transport instance.

    def end_capture(self) -> None:
        self._capture_dir = None

    @property
    def attempt_count(self) -> int:
        return self._attempt_number

    def _wait(self, delay: float) -> None:
        if (
            delay > self.policy.max_single_wait
            or self.total_wait + delay > self.policy.max_total_wait
        ):
            raise ArcGISError("Retry later: required wait exceeds retrieval wait budget")
        if delay > 0:
            self._sleep(delay)
            self.total_wait += delay

    def _retry_after(self, value: str | None) -> float:
        if not value:
            return 0.0
        value = value.strip()
        if value.isascii() and value.isdigit():
            return float(value) if len(value) < 16 else float("inf")
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                return 0.0
            return max(0.0, parsed.timestamp() - self._wall_time())
        except (ValueError, TypeError, OverflowError):
            return 0.0

    def _read_body(self, response: Any) -> tuple[bytes, bool, bool]:
        chunks = bytearray()
        incomplete = False
        while len(chunks) <= self.policy.max_body_bytes:
            try:
                chunk = response.read(min(65536, self.policy.max_body_bytes + 1 - len(chunks)))
            except IncompleteRead as exc:
                chunks.extend(exc.partial[: self.policy.max_body_bytes + 1 - len(chunks)])
                incomplete = True
                break
            except (TimeoutError, ConnectionError):
                # Keep bytes already received if a connection fails mid-stream.
                incomplete = True
                break
            if not chunk:
                break
            chunks.extend(chunk)
        oversized = len(chunks) > self.policy.max_body_bytes
        body = bytes(chunks[: self.policy.max_body_bytes])
        length = (getattr(response, "headers", {}) or {}).get("Content-Length")
        if length is not None:
            length_text = str(length)
            if (
                not length_text.isascii()
                or not length_text.isdigit()
                or len(length_text) > 20
                or int(length_text) != len(body)
            ):
                incomplete = True
        return body, oversized, incomplete

    def _retain(self, body: bytes | None, payload: Any, record: dict) -> None:
        if self._capture_dir is None:
            return
        stem = f"attempt_{self._attempt_number:05d}"
        if body is not None:
            path = self._capture_dir / f"{stem}.body"
            with path.open("xb") as handle:
                handle.write(body)
            record["body"] = {
                "file": path.name,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        if record.get("parsed_json"):
            encoded = (
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
                + "\n"
            ).encode()
            path = self._capture_dir / f"{stem}.parsed.json"
            with path.open("xb") as handle:
                handle.write(encoded)
            record["parsed"] = {"file": path.name, "sha256": hashlib.sha256(encoded).hexdigest()}
        with (self._capture_dir / f"{stem}.evidence.json").open("x", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, allow_nan=False)

    @staticmethod
    def _transient_network(exc: Exception) -> bool:
        reason = exc.reason if isinstance(exc, URLError) else exc
        if isinstance(reason, ssl.SSLError):
            return False
        if isinstance(reason, socket.gaierror):
            return reason.errno == socket.EAI_AGAIN
        if isinstance(reason, OSError) and reason.errno in {
            errno.ETIMEDOUT,
            errno.ENETDOWN,
            errno.ENETUNREACH,
            errno.EHOSTUNREACH,
            errno.ECONNRESET,
            errno.ECONNREFUSED,
            errno.ECONNABORTED,
            errno.EPIPE,
        }:
            return True
        return isinstance(reason, (TimeoutError, ConnectionError))

    def get_json(self, url: str, params: Mapping[str, Any]) -> dict[str, Any]:
        target = f"{url}?{urlencode(params)}"
        retry_delay = 0.0
        for attempt in range(self.max_retries):
            pacing = (
                0.0
                if self._last_started is None
                else max(
                    0.0, self.policy.min_request_spacing - (self._clock() - self._last_started)
                )
            )
            delay = max(pacing, retry_delay)
            self._wait(delay)
            self._last_started = self._clock()
            self._attempt_number += 1
            body, payload = None, None
            record = {
                "attempt": attempt + 1,
                "wait_seconds": delay,
                "timeout_seconds": self.timeout,
                "status": None,
            }
            retry = False
            server_delay = 0.0
            reason = "response failure"
            try:
                request = Request(target, headers={"User-Agent": "mn-land-intelligence/0.2"})
                try:
                    response = urlopen(request, timeout=self.timeout)
                except HTTPError as exc:
                    response = exc
                with response:
                    status = getattr(response, "status", None) or getattr(response, "code", 200)
                    record["status"] = status
                    headers = getattr(response, "headers", {}) or {}
                    server_delay = self._retry_after(headers.get("Retry-After"))
                    body, oversized, incomplete = self._read_body(response)
                record.update(body_truncated=oversized, body_incomplete=incomplete)
                if oversized:
                    raise ArcGISError("Response exceeds configured body byte budget")
                parsed_ok = False
                if not incomplete:
                    try:
                        payload = json.loads(body)
                        json.dumps(payload, allow_nan=False, ensure_ascii=False).encode("utf-8")
                        parsed_ok = True
                        record["parsed_json"] = True
                    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError):
                        payload = None
                    except ValueError as exc:
                        payload = None
                        if status == 200:
                            raise ArcGISError("Invalid numeric/Unicode JSON response") from exc
                if status != 200:
                    retry = status in TRANSIENT_HTTP
                    reason = f"HTTP {status}"
                elif incomplete:
                    retry, reason = True, "incomplete HTTP body"
                elif not parsed_ok:
                    # Malformed JSON gets the bounded retry path.
                    retry, reason = True, "invalid JSON"
                else:
                    if not isinstance(payload, dict):
                        raise ArcGISError("ArcGIS returned a non-object JSON response")
                    if "error" not in payload:
                        record["outcome"] = "success"
                        return payload
                    error = payload["error"]
                    code = error.get("code") if isinstance(error, dict) else None
                    retry = type(code) is int and code in TRANSIENT_ARCGIS
                    reason = f"ArcGIS error code {code if type(code) is int else 'unknown'}"
            except (URLError, OSError) as exc:
                retry = self._transient_network(exc)
                reason = f"network failure ({type(exc).__name__})"
            except ArcGISError as exc:
                record["outcome"] = str(exc)
                raise
            finally:
                record.setdefault("outcome", reason)
                self._retain(body, payload, record)
            if not retry or attempt + 1 == self.max_retries:
                raise ArcGISError(f"Unable to retrieve: {reason}; attempts={attempt + 1}")
            retry_delay = max(server_delay, self.policy.backoff_seconds * (2**attempt))
        raise AssertionError("Validated attempt budget cannot be empty")
