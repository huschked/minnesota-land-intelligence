"""Read-only, explicitly loaded suitability observations and contextual downloads."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

from mn_land.counties.isanti.delinquency import normalize_parcel_id
from mn_land.enrichment import CSV_FIELDS, require, serialize
from mn_land.parcel_table import ParcelDataset, TableFilters, query
from mn_land.review_service import ReviewService
from mn_land.runs import (
    RunValidationError,
    read_artifact_json,
    safe_path,
    validate_run,
    workspace_path,
)
from mn_land.worklists import canonical


@dataclass(frozen=True, slots=True)
class SuitabilityObservation:
    run_id: str
    completion_sha256: str
    document: str

    def payload(self) -> dict:
        return json.loads(self.document)

    def record(self, identity: str) -> dict | None:
        key = normalize_parcel_id(identity)
        return next((r for r in self.payload()["records"] if r["parcel_id"] == key), None)


@dataclass(frozen=True, slots=True)
class SuitabilityPreview:
    observation: SuitabilityObservation
    dataset: ParcelDataset
    filters: TableFilters
    scope: str
    selected: str | None
    document: str

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.document.encode()).hexdigest()


class SuitabilityService:
    def __init__(self, processed_root: Path):
        self.root = workspace_path(processed_root)

    def catalog(self) -> tuple[str, ...]:
        """Names only. Catalog entries are explicitly UNVALIDATED until Load."""
        root = self.root / "isanti/enrichment"
        if not root.exists():
            return ()
        root = safe_path(self.root, "isanti/enrichment", directory=True)
        names = []
        for item in root.iterdir():
            if item.is_dir() and not item.is_symlink() and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", item.name):
                names.append(item.name)
            require(len(names) <= 200, "Suitability catalog exceeds 200 entries")
        return tuple(sorted(names))

    def load(self, run_id: str, dataset: ParcelDataset, *, expected: str | None = None) -> SuitabilityObservation:
        try:
            require(isinstance(run_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", run_id) is not None,
                    "Choose a listed suitability identity")
            require(not dataset.overview.holds, "Held candidate evidence cannot bind suitability")
            base = ReviewService(self.root).load_parcels(dataset.overview.key,
                expected_completion=dataset.overview.completion_sha256)
            require(base.rows == dataset.rows and base.minimum_acres == dataset.minimum_acres,
                    "Loaded candidate observation changed")
            root = safe_path(self.root, "isanti/enrichment/" + run_id, directory=True)
            run = validate_run(root, "suitability_enrichment")
            require(expected is None or expected == run.completion_sha256, "Suitability completion changed")
            payload = read_artifact_json(run, "enrichment.json")
            context = payload["context"]
            ref = context["candidate_review" if base.overview.key.kind == "review" else "candidate_join"]
            require(ref == {"run_id": base.overview.key.run_id,
                            "completion_sha256": base.overview.completion_sha256},
                    "Suitability belongs to different candidate source evidence")
            eligible = {normalize_parcel_id(r.parcel_id) for r in base.rows}
            require({r["parcel_id"] for r in payload["records"]} <= eligible,
                    "Suitability includes parcels outside this candidate observation")
            return SuitabilityObservation(run_id, run.completion_sha256, canonical(payload))
        except (OSError, ValueError, TypeError, KeyError, StopIteration, ImportError) as exc:
            raise RunValidationError(
                "Suitability is missing, changed, incomplete, incompatible or needs the optional GIS extra. "
                "Nothing was refreshed or substituted; explicitly reload compatible saved evidence."
            ) from exc

    def prepare(self, observation: SuitabilityObservation, dataset: ParcelDataset,
                filters: TableFilters, *, scope: str, selected: str | None = None) -> SuitabilityPreview:
        require(scope in {"filtered", "selected"}, "Choose a supported suitability export scope")
        fresh = self.load(observation.run_id, dataset, expected=observation.completion_sha256)
        require(fresh == observation, "Suitability observation changed")
        result = query(dataset, filters)
        ids = [r.parcel_id for r in result.filtered]
        if scope == "selected":
            require(selected in ids, "Choose a currently filtered parcel")
            ids = [selected]
        else:
            require(selected is None, "Filtered export must not carry an implicit selected parcel")
        payload = observation.payload()
        rows = []
        for identity in ids:
            row = observation.record(identity)
            if row is None:
                row = {name: None for name in CSV_FIELDS if name != "context"}
                row.update(parcel_id=normalize_parcel_id(identity), status="not_assessed", holds=[])
            rows.append(row)
        payload["records"] = rows
        payload["context"]["export_scope"] = {
            "scope": scope, "selected_parcel_id": selected,
            "candidate_snapshot": dataset.overview.key.token,
            "candidate_completion_sha256": dataset.overview.completion_sha256,
            "suitability_run_id": observation.run_id,
            "suitability_completion_sha256": observation.completion_sha256,
            "filters": {k: str(v) if isinstance(v, Decimal) else v
                        for k, v in asdict(filters).items()},
            "order": "Current candidate service order, across all pages; distinct parcel IDs",
        }
        return SuitabilityPreview(observation, dataset, filters, scope, selected, canonical(payload))

    def download(self, preview: SuitabilityPreview, format: str) -> bytes:
        fresh = self.prepare(preview.observation, preview.dataset, preview.filters,
                             scope=preview.scope, selected=preview.selected)
        require(fresh.fingerprint == preview.fingerprint, "Suitability preview changed; no stale file supplied")
        return serialize(json.loads(fresh.document), format)
