from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mn_land.config.retrieval import RetrievalPolicy
from mn_land.ingestion.source_checks import integer, inventory, metadata_contract, transfer_flag
from mn_land.provenance import build_provenance
from mn_land.utils.http import ArcGISError, JsonTransport, UrllibJsonTransport


class ArcGISClient:
    def __init__(
        self,
        service_url: str,
        layer_id: int,
        *,
        page_size: int = 2_000,
        transport: JsonTransport | None = None,
        policy: RetrievalPolicy | None = None,
        expected_layer_name: str | None = None,
    ) -> None:
        integer(layer_id, "layer_id", minimum=0)
        integer(page_size, "page_size", minimum=1)
        self.service_url = service_url.rstrip("/")
        self.layer_id = layer_id
        self.page_size = page_size
        self.policy = policy or getattr(transport, "policy", None) or RetrievalPolicy()
        if (
            policy is not None
            and isinstance(transport, UrllibJsonTransport)
            and transport.policy != policy
        ):
            raise ValueError("Client and transport retrieval policies must agree")
        self.transport = transport or UrllibJsonTransport(policy=self.policy)
        self.expected_layer_name = expected_layer_name

    @property
    def layer_url(self) -> str:
        return f"{self.service_url}/{self.layer_id}"

    def metadata(self) -> dict[str, Any]:
        return self.transport.get_json(self.layer_url, {"f": "json"})

    def count(self, where: str = "1=1") -> int:
        payload = self.transport.get_json(
            f"{self.layer_url}/query",
            {"f": "json", "where": where, "returnCountOnly": "true"},
        )
        return integer(payload.get("count"), "count", minimum=0)

    def fetch_all(
        self,
        *,
        out_fields: Sequence[str],
        raw_run_dir: Path,
        retrieved_at: datetime,
        where: str = "1=1",
        return_geometry: bool = False,
        metadata_validator: Callable[[object], None] | None = None,
    ) -> Iterable[dict[str, Any]]:
        if (
            not out_fields
            or isinstance(out_fields, str)
            or any(
                not isinstance(field, str) or not field.strip() or field == "*"
                for field in out_fields
            )
            or len(set(out_fields)) != len(out_fields)
        ):
            raise ValueError("Request explicit unique mapped fields")
        if return_geometry is not False:
            raise ValueError("Attribute acquisition does not request geometry")
        raw_run_dir.mkdir(parents=True, exist_ok=False)
        captures_http = isinstance(self.transport, UrllibJsonTransport)
        if captures_http:
            self.transport.begin_capture(raw_run_dir / "http")
        try:
            yield from self._fetch(
                out_fields,
                raw_run_dir,
                retrieved_at,
                where,
                metadata_validator,
                captures_http,
            )
        except (ArcGISError, ValueError) as exc:
            # Response bodies/parsed artifacts are retained already. Do not copy
            # arbitrary server strings/URLs into diagnostics. Run publication is ML-127.
            self._write_json(
                raw_run_dir / "retrieval_failure.json",
                {
                    "failure_type": type(exc).__name__,
                    "complete_acquisition": False,
                    "reason": str(exc)
                    if isinstance(exc, ArcGISError)
                    else "Metadata/schema validation failed; inspect retained evidence",
                    "policy": self.policy.to_dict(),
                },
            )
            raise
        finally:
            if captures_http:
                self.transport.end_capture()

    def _fetch(
        self,
        fields: Sequence[str],
        directory: Path,
        retrieved_at: datetime,
        where: str,
        validator: Callable[[object], None] | None,
        captures_http: bool,
    ) -> Iterable[dict[str, Any]]:
        observations: list[dict[str, Any]] = []

        def request(filename: str, params: dict[str, Any], *, query: bool = True) -> dict[str, Any]:
            first_attempt = getattr(self.transport, "attempt_count", 0) + 1
            before = datetime.now(UTC).isoformat()
            try:
                payload = self.transport.get_json(
                    f"{self.layer_url}/query" if query else self.layer_url,
                    params,
                )
            except ArcGISError:
                self._write_json(
                    directory / "failed_request.json",
                    {
                        "intended_artifact": filename,
                        "http_attempt_range": [first_attempt, self.transport.attempt_count]
                        if captures_http
                        else None,
                        "total_wait_seconds": getattr(self.transport, "total_wait", None),
                    },
                )
                raise
            self._write_json(directory / filename, payload)
            observations.append(
                {
                    "artifact": filename,
                    "started_at": before,
                    "finished_at": datetime.now(UTC).isoformat(),
                    "http_attempt_range": [first_attempt, self.transport.attempt_count]
                    if captures_http
                    else None,
                }
            )
            if not isinstance(payload, dict):
                raise ArcGISError(f"{filename}: expected an object")
            return payload

        def metadata(filename: str) -> dict[str, Any]:
            payload = request(filename, {"f": "json"}, query=False)
            if validator is not None:
                validator(payload)
            return metadata_contract(payload, self.layer_id, fields, self.expected_layer_name)

        initial_schema = metadata("layer_metadata.json")
        oid = initial_schema["object_id"]
        page_size = min(self.page_size, initial_schema["max_record_count"])

        def membership(label: str) -> tuple[int, set[int]]:
            count_payload = request(
                f"count_{label}.json",
                {
                    "f": "json",
                    "where": where,
                    "returnCountOnly": "true",
                },
            )
            expected = integer(count_payload.get("count"), f"count_{label}", minimum=0)
            if expected > self.policy.max_inventory_ids:
                raise ArcGISError("Count exceeds bounded inventory budget; no automatic batching")
            ids_payload = request(
                f"ids_{label}.json",
                {
                    "f": "json",
                    "where": where,
                    "returnIdsOnly": "true",
                },
            )
            return expected, inventory(
                ids_payload, expected, oid, self.policy.max_inventory_ids, label
            )

        expected, expected_ids = membership("start")
        offset, page_number = 0, 0
        seen: set[int] = set()
        previous = None
        while offset < expected:
            page_number += 1
            payload = request(
                f"page_{page_number:05d}.json",
                {
                    "f": "json",
                    "where": where,
                    "outFields": ",".join(fields),
                    "returnGeometry": "false",
                    "resultOffset": offset,
                    "resultRecordCount": page_size,
                    "orderByFields": f"{oid} ASC",
                },
            )
            features = payload.get("features")
            label = f"Page {page_number}"
            if not isinstance(features, list) or not features or len(features) > page_size:
                raise ArcGISError(
                    f"{label}: missing/empty/oversized features list before expected end"
                )
            flag = transfer_flag(payload, label)
            for number, feature in enumerate(features, 1):
                location = f"{label} record {number}"
                if not isinstance(feature, dict) or not isinstance(feature.get("attributes"), dict):
                    raise ArcGISError(f"{location}: feature/attributes must be objects")
                identity = integer(feature["attributes"].get(oid), f"{location} OID")
                if identity in seen:
                    raise ArcGISError(f"{location}: Duplicate object ID")
                if identity not in expected_ids:
                    raise ArcGISError(f"{location}: unexpected object ID outside inventory")
                if previous is not None and identity <= previous:
                    raise ArcGISError(f"{location}: out-of-order object ID")
                seen.add(identity)
                previous = identity
            offset += len(features)
            if (flag is True and offset >= expected) or (flag is False and offset < expected):
                raise ArcGISError(
                    f"{label}: transfer-limit flag contradicts inventory completeness"
                )
            yield from features
        final_count, final_ids = membership("end")
        final_schema = metadata("layer_metadata_end.json")
        if expected != final_count or expected_ids != final_ids:
            raise ArcGISError("Source count or ID inventory changed during retrieval")
        if initial_schema != final_schema:
            raise ArcGISError("Source schema/capabilities/edit token changed during retrieval")
        if seen != expected_ids or offset != expected:
            raise ArcGISError("Fetched IDs/count do not reconcile with inventory")

        def fingerprint(schema: dict[str, Any]) -> str:
            return hashlib.sha256(
                json.dumps(schema, sort_keys=True, allow_nan=False).encode()
            ).hexdigest()

        warnings = [] if expected else ["empty source; not evidence of paid/current taxes"]
        if initial_schema["edit_token"] is None:
            warnings.append(
                "same-ID attribute consistency unknown: no advertised lastEditDate token"
            )
        manifest = {
            "service_url": self.service_url,
            "layer_id": self.layer_id,
            "retrieved_at": retrieved_at.isoformat(),
            "where": where,
            "out_fields": list(fields),
            "return_geometry": False,
            "page_size": page_size,
            "configured_page_size": self.page_size,
            "pages": page_number,
            "record_count": offset,
            "retrieval_policy": self.policy.to_dict(),
            "http_evidence": "http" if captures_http else None,
            "http_evidence_limitation": None
            if captures_http
            else "injected JSON transport; original wire bytes unavailable",
            "attempts": getattr(self.transport, "attempt_count", None),
            "total_wait_seconds": getattr(self.transport, "total_wait", None),
            "source_checks": {
                "initial_count": expected,
                "final_count": final_count,
                "initial_fingerprint": fingerprint(initial_schema),
                "final_fingerprint": fingerprint(final_schema),
                "initial_edit_token": initial_schema["edit_token"],
                "final_edit_token": final_schema["edit_token"],
                "membership_reconciled": True,
                "transactional_snapshot": False,
                "observations": observations,
                "warnings": warnings,
            },
        }
        manifest["provenance"] = build_provenance(
            {
                "service_url": self.service_url,
                "layer_id": self.layer_id,
                "where": where,
                "out_fields": list(fields),
                "return_geometry": False,
                "page_size": page_size,
                "transport": type(self.transport).__qualname__,
                **self.policy.to_dict(),
            },
            outputs=[path for path in directory.rglob("*") if path.is_file()],
        )
        self._write_json(directory / "manifest.json", manifest)

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
