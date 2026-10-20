"""Bounded dated JSON/wire capture and strict offline request-sequence replay."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from mn_land.config.retrieval import RetrievalPolicy
from mn_land.geometry import GeometryError
from mn_land.provenance import sha256_file
from mn_land.runs import read_json, safe_path, write_json
from mn_land.utils.http import ArcGISError, UrllibJsonTransport

POLICY = RetrievalPolicy(max_body_bytes=64 * 1024 * 1024, max_inventory_ids=20_000,
                         max_total_wait=600)
MAX_REQUESTS = 128
MAX_CAPTURE_BYTES = 512 * 1024 * 1024


def capture_budget(path: Path) -> None:
    if sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) > MAX_CAPTURE_BYTES:
        raise GeometryError("Spatial capture exceeds aggregate byte budget")


class SpatialCapture:
    def __init__(self, path: Path, transport=None) -> None:
        self.path = path
        self.transport = transport or UrllibJsonTransport(policy=POLICY)
        self.wire = isinstance(self.transport, UrllibJsonTransport)
        if self.wire and self.transport.policy != POLICY:
            raise GeometryError("Spatial transport must use the reviewed retrieval policy")
        self.records = []

    def __enter__(self):
        self.path.mkdir(exist_ok=False)
        if self.wire:
            self.transport.begin_capture(self.path / "http")
        return self

    def __exit__(self, *args):
        if self.wire:
            self.transport.end_capture()

    def request(self, url: str, params: dict) -> dict:
        number = len(self.records) + 1
        if number > MAX_REQUESTS:
            raise GeometryError("Spatial logical request budget exceeded")
        record = {"number": number, "url": url, "params": params,
                  "started_at": datetime.now(UTC).isoformat(),
                  "first_http_attempt": getattr(self.transport, "attempt_count", 0) + 1}
        self.records.append(record)
        write_json(self.path / f"request_{number:03d}.json", record)
        try:
            payload = self.transport.get_json(url, params)
        except ArcGISError as exc:
            record["failure"] = "body_budget" if "body byte budget" in str(exc) else "retrieval"
            raise
        else:
            record["response"] = f"response_{number:03d}.json"
            write_json(self.path / record["response"], payload)
            if not isinstance(payload, dict):
                raise GeometryError("Spatial response must be an object")
            return payload
        finally:
            record["finished_at"] = datetime.now(UTC).isoformat()
            record["last_http_attempt"] = getattr(self.transport, "attempt_count", None)
            write_json(self.path / f"receipt_{number:03d}.json", record)
            capture_budget(self.path)


class SpatialReplay:
    def __init__(self, path: Path, manifest: dict) -> None:
        self.path, self.records = path, manifest["requests"]
        self.wire = manifest["wire_bytes_retained"]
        self.position = self.last_attempt = 0
        self.previous = datetime.fromisoformat(manifest["capture_started_at"])
        self.finish = datetime.fromisoformat(manifest["capture_finished_at"])
        if type(self.wire) is not bool or self.previous.tzinfo is None or (
            self.finish.tzinfo is None or self.previous > self.finish
        ):
            raise GeometryError("Invalid spatial capture identity/times")
        if not isinstance(self.records, list) or not 0 < len(self.records) <= MAX_REQUESTS:
            raise GeometryError("Invalid spatial request inventory")
        capture_budget(path)

    def request(self, url: str, params: dict) -> dict:
        self.position += 1
        number = self.position
        if number > len(self.records):
            raise GeometryError("Missing spatial request evidence")
        record = self.records[number - 1]
        if record != read_json(safe_path(self.path, f"receipt_{number:03d}.json")) or (
            record["number"] != number or record["url"] != url or record["params"] != params
        ):
            raise GeometryError("Spatial URL/params/receipt sequence differs from contract")
        intended = read_json(safe_path(self.path, f"request_{number:03d}.json"))
        if any(record.get(k) != v for k, v in intended.items()):
            raise GeometryError("Changed spatial intended request")
        start = datetime.fromisoformat(record["started_at"])
        end = datetime.fromisoformat(record["finished_at"])
        if start.tzinfo is None or end.tzinfo is None or not self.previous <= start <= end <= self.finish:
            raise GeometryError("Invalid spatial request chronology")
        self.previous = end
        if record.get("failure"):
            if record["failure"] != "body_budget":
                raise GeometryError("Failed spatial request is not complete acquisition")
            if self.wire:
                self._wire(record, None)
            raise ArcGISError("Response exceeds configured body byte budget")
        name = f"response_{number:03d}.json"
        if record.get("response") != name:
            raise GeometryError("Unsafe spatial response reference")
        payload = read_json(safe_path(self.path, name))
        if self.wire:
            self._wire(record, payload)
        return payload

    def _wire(self, record: dict, payload: dict | None) -> None:
        first, last = record["first_http_attempt"], record["last_http_attempt"]
        if type(first) is not int or type(last) is not int or first != self.last_attempt + 1 or (
            not first <= last < first + POLICY.max_attempts
        ):
            raise GeometryError("Invalid spatial HTTP attempt range")

        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise GeometryError("Duplicate native spatial JSON member")
                result[key] = value
            return result

        for number in range(first, last + 1):
            stem = f"attempt_{number:05d}"
            evidence = read_json(safe_path(self.path, f"http/{stem}.evidence.json"))
            if evidence["attempt"] != number - first + 1:
                raise GeometryError("Invalid spatial retry ordinal")
            info = evidence.get("body")
            body = None
            if info:
                file = safe_path(self.path, f"http/{stem}.body")
                if info["file"] != stem + ".body" or not (
                    file.stat().st_size == info["bytes"] <= POLICY.max_body_bytes
                    and sha256_file(file) == info["sha256"]
                ):
                    raise GeometryError("Spatial wire body budget/hash differs")
                body = file.read_bytes()
            if number == last:
                if payload is None:
                    if evidence.get("body_truncated") is not True:
                        raise GeometryError("Split spatial batch lacks wire byte-budget evidence")
                elif (
                    body is None or evidence.get("status") != 200
                    or evidence.get("outcome") != "success"
                    or evidence.get("body_incomplete") is not False
                    or evidence.get("body_truncated") is not False
                    or json.loads(body, object_pairs_hook=unique) != payload
                ):
                    raise GeometryError("Spatial normalized response differs from successful wire body")
        self.last_attempt = last

    def complete(self) -> None:
        if self.position != len(self.records) or self.wire and (
            len(list((self.path / "http").glob("*.evidence.json"))) != self.last_attempt
        ):
            raise GeometryError("Unreconciled spatial requests/attempts")
