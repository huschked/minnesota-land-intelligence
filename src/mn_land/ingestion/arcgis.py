from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

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
    ) -> None:
        self.service_url = service_url.rstrip("/")
        self.layer_id = layer_id
        self.page_size = page_size
        self.transport = transport or UrllibJsonTransport()

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
        count = payload.get("count")
        if not isinstance(count, int):
            raise ArcGISError("ArcGIS count response did not contain an integer count")
        return count

    def fetch_all(
        self,
        *,
        out_fields: Sequence[str],
        raw_run_dir: Path,
        retrieved_at: datetime,
        where: str = "1=1",
        return_geometry: bool = False,
    ) -> Iterable[dict[str, Any]]:
        raw_run_dir.mkdir(parents=True, exist_ok=False)
        metadata = self.metadata()
        self._write_json(raw_run_dir / "layer_metadata.json", metadata)
        expected = self.count(where)
        object_id = metadata.get("objectIdField") or "OBJECTID"
        offset = 0
        page_number = 0
        seen: set[Any] = set()
        retrieved = 0
        while offset < expected:
            params = {
                "f": "json",
                "where": where,
                "outFields": ",".join(out_fields),
                "returnGeometry": str(return_geometry).lower(),
                "resultOffset": offset,
                "resultRecordCount": self.page_size,
                "orderByFields": f"{object_id} ASC",
            }
            payload = self.transport.get_json(f"{self.layer_url}/query", params)
            page_number += 1
            self._write_json(raw_run_dir / f"page_{page_number:05d}.json", payload)
            features = payload.get("features")
            if not isinstance(features, list):
                raise ArcGISError(f"Page {page_number} has no features list")
            if not features and retrieved < expected:
                raise ArcGISError(
                    f"Pagination stopped early: expected {expected}, retrieved {retrieved}"
                )
            for feature in features:
                feature_id = feature.get("attributes", {}).get(object_id)
                if feature_id in seen:
                    raise ArcGISError(f"Duplicate object ID during pagination: {feature_id}")
                seen.add(feature_id)
                retrieved += 1
                yield feature
            offset += len(features)
        if retrieved != expected:
            raise ArcGISError(f"Source reported {expected} records but {retrieved} were retrieved")
        manifest = {
            "service_url": self.service_url,
            "layer_id": self.layer_id,
            "retrieved_at": retrieved_at.isoformat(),
            "where": where,
            "out_fields": list(out_fields),
            "return_geometry": return_geometry,
            "page_size": self.page_size,
            "pages": page_number,
            "record_count": retrieved,
        }
        manifest["provenance"] = build_provenance(
            {
                "service_url": self.service_url,
                "layer_id": self.layer_id,
                "where": where,
                "out_fields": list(out_fields),
                "return_geometry": return_geometry,
                "page_size": self.page_size,
                "transport": type(self.transport).__qualname__,
                "timeout_seconds": getattr(self.transport, "timeout", None),
                "max_retries": getattr(self.transport, "max_retries", None),
            },
            outputs=[raw_run_dir / "layer_metadata.json", *raw_run_dir.glob("page_*.json")],
        )
        self._write_json(raw_run_dir / "manifest.json", manifest)

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
