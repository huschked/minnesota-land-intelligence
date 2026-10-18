"""Reviewed Isanti polygon acquisition contract, independent of attribute client."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from pyproj import CRS
from pyproj.exceptions import CRSError

from mn_land.config.retrieval import RetrievalPolicy
from mn_land.counties.isanti.delinquency import normalize_parcel_id
from mn_land.geometry import AnalysisPolicy, GeometryError
from mn_land.ingestion.source_checks import integer, inventory, metadata_contract, transfer_flag
from mn_land.runs import write_json
from mn_land.utils.http import ArcGISError, JsonTransport, UrllibJsonTransport

LAYER = "https://gis.co.isanti.mn.us/arcgis/rest/services/LandRecords/TaxParcels_Public/FeatureServer/0"
FIELDS = ("OBJECTID", "PARCELID", "UNFORMATTEDPIN", "DEEDEDACRES")
MAX_PARCELS = 500
MAX_REQUESTS = 100
MAX_CAPTURE_BYTES = 128 * 1024 * 1024
POLICY = RetrievalPolicy(max_inventory_ids=MAX_PARCELS)
ANALYSIS = AnalysisPolicy(45.55, -93.3, (-94.0, 45.2, -92.8, 45.9))


def native_crs(spatial_reference: object) -> CRS:
    """Reject conflicting codes/WKT rather than silently trusting one declaration."""
    if not isinstance(spatial_reference, dict):
        raise GeometryError("Missing native spatial reference")
    codes = [spatial_reference[k] for k in ("wkid", "latestWkid") if k in spatial_reference]
    if not codes or any(type(code) is not int or code != 103736 for code in codes):
        raise GeometryError("Only reviewed ESRI:103736 native CRS is supported")
    expected = CRS("ESRI:103736")
    if expected.datum.name != "D_NAD_1983_HARN_Adj_MN_Isanti" or (
        abs(expected.ellipsoid.semi_major_metre - 6378411.321) > 0.000001
        or abs(expected.ellipsoid.inverse_flattening - 298.257222100883) > 1e-10
        or any(abs(axis.unit_conversion_factor - 1200 / 3937) > 1e-14
               for axis in expected.axis_info)
    ):
        raise GeometryError("Local CRS database differs from reviewed Isanti datum/units")
    for key in ("wkt", "wkt2"):
        if key in spatial_reference:
            try:
                same = CRS(spatial_reference[key]).equals(expected)
            except CRSError as exc:
                raise GeometryError("Unresolvable source WKT") from exc
            if not same:
                raise GeometryError("Native WKID and WKT conflict")
    if any(k in spatial_reference for k in ("vcsWkid", "latestVcsWkid")):
        raise GeometryError("Vertical CRS unsupported; no dimension stripping")
    return expected


def schema(metadata: dict) -> dict:
    if not isinstance(metadata, dict):
        raise GeometryError("Geometry metadata must be an object")
    result = metadata_contract(metadata, 0, FIELDS, "TaxParcels_Public")
    if result["object_id"] != "OBJECTID" or metadata.get("geometryType") != "esriGeometryPolygon":
        raise GeometryError("Unexpected polygon layer identity")
    for field in result["requested_fields"]:
        expected = "esriFieldTypeOID" if field["name"] == "OBJECTID" else (
            "esriFieldTypeDouble" if field["name"] == "DEEDEDACRES" else "esriFieldTypeString"
        )
        if field.get("type") != expected or type(field.get("nullable")) is not bool:
            raise GeometryError("Changed identity/acreage field declaration")
    if metadata.get("hasZ") is not False or metadata.get("hasM") is not False:
        raise GeometryError("Z/M layer held; unsupported dimensions must not be dropped")
    if metadata["advancedQueryCapabilities"].get("supportsTrueCurve") is not True:
        raise GeometryError("Cannot establish native true-curve query fidelity")
    sr = metadata.get("extent", {}).get("spatialReference")
    native_crs(sr)
    result.update(
        spatial_reference=sr, geometry_type=metadata["geometryType"],
        has_z=False, has_m=False, true_curves=True,
        curve_types=metadata["advancedQueryCapabilities"].get("supportedCurveTypes"),
    )
    return result


def identity(feature: object) -> tuple[int, str]:
    if not isinstance(feature, dict) or not isinstance(feature.get("attributes"), dict):
        raise GeometryError("Missing feature attributes")
    attributes = feature["attributes"]
    if not set(FIELDS) <= attributes.keys():
        raise GeometryError("Missing requested geometry attribute field")
    oid = integer(attributes.get("OBJECTID"), "geometry OID", minimum=1)
    pin = attributes.get("UNFORMATTEDPIN")
    if not isinstance(pin, str) or not re.fullmatch(r"[0-9]{9}", pin):
        raise GeometryError("Unformatted PIN must be exact nine-digit text")
    if normalize_parcel_id(attributes.get("PARCELID")) != pin:
        raise GeometryError("Conflicting formatted and unformatted parcel identities")
    return oid, pin


class Capture:
    """Every intended request and response is independently dated and retained."""

    def __init__(self, directory: Path, transport: JsonTransport) -> None:
        self.directory, self.transport = directory, transport
        self.records: list[dict] = []

    def check_budget(self) -> None:
        if sum(p.stat().st_size for p in self.directory.rglob("*") if p.is_file()) > MAX_CAPTURE_BYTES:
            raise GeometryError("Aggregate retained geometry capture byte budget exceeded")

    def request(self, params: dict, *, query: bool = True) -> dict:
        number = len(self.records) + 1
        if number > MAX_REQUESTS:
            raise GeometryError("Geometry request budget exceeded")
        url = LAYER + ("/query" if query else "")
        record = {
            "number": number, "url": url, "params": params,
            "started_at": datetime.now(UTC).isoformat(),
            "first_http_attempt": getattr(self.transport, "attempt_count", 0) + 1,
        }
        self.records.append(record)
        write_json(self.directory / f"request_{number:03d}.json", record)
        try:
            payload = self.transport.get_json(url, params)
        except ArcGISError as exc:
            record["finished_at"] = datetime.now(UTC).isoformat()
            record["last_http_attempt"] = getattr(self.transport, "attempt_count", None)
            record["failure"] = "body_budget" if "body byte budget" in str(exc) else "retrieval"
            write_json(self.directory / f"receipt_{number:03d}.json", record)
            self.check_budget()
            raise
        record["finished_at"] = datetime.now(UTC).isoformat()
        record["last_http_attempt"] = getattr(self.transport, "attempt_count", None)
        record["response"] = f"response_{number:03d}.json"
        write_json(self.directory / record["response"], payload)
        write_json(self.directory / f"receipt_{number:03d}.json", record)
        self.check_budget()
        if not isinstance(payload, dict):
            raise GeometryError("Geometry response must be an object")
        return payload


def acquire(request, pins: list[str], *, batch_size: int = 50) -> tuple[list[dict], dict]:
    """Exact OID batches, count/membership before and after; no offset truncation.

    request is either a dated capture or an offline sequence replay. Oversized
    feature batches split recursively; a single oversized polygon holds the run.
    """
    if not pins or len(pins) > MAX_PARCELS or len(set(pins)) != len(pins) or any(
        not isinstance(pin, str) or not re.fullmatch(r"[0-9]{9}", pin) for pin in pins
    ):
        raise GeometryError("Select 1..500 distinct exact nine-digit parcel IDs")
    if type(batch_size) is not int or not 1 <= batch_size <= 50:
        raise GeometryError("Geometry batch size must be 1..50")
    before = schema(request({"f": "json"}, query=False))
    size = min(batch_size, before["max_record_count"])
    where = "UNFORMATTEDPIN IN (" + ",".join(f"'{pin}'" for pin in sorted(pins)) + ")"

    def membership():
        count = integer(request({"f": "json", "where": where, "returnCountOnly": "true"}).get(
            "count"), "selected count", minimum=0)
        if count != len(pins):
            raise GeometryError("Missing/duplicate parcel membership; selected count differs")
        return inventory(
            request({"f": "json", "where": where, "returnIdsOnly": "true"}),
            count, "OBJECTID", MAX_PARCELS, "geometry",
        )

    first = membership()
    features: list[dict] = []
    seen_pins: set[str] = set()
    seen_oids: set[int] = set()

    def batch(ids: list[int]):
        params = {
            "f": "json", "objectIds": ",".join(map(str, ids)), "where": where,
            "outFields": ",".join(FIELDS), "returnGeometry": "true",
            "returnTrueCurves": "true", "returnZ": "true", "returnM": "true",
            "outSR": 103736, "orderByFields": "OBJECTID ASC",
            "resultRecordCount": len(ids), "resultOffset": 0,
        }
        try:
            payload = request(params)
        except ArcGISError as exc:
            if len(ids) == 1 or "body byte budget" not in str(exc):
                raise
            midpoint = len(ids) // 2
            batch(ids[:midpoint])
            batch(ids[midpoint:])
            return
        if transfer_flag(payload, "geometry batch") is True:
            raise GeometryError("Incomplete geometry batch / transfer limit")
        if any(k in payload for k in ("transform", "quantizationParameters")):
            raise GeometryError("Quantized geometry not requested or supported")
        native_crs(payload.get("spatialReference"))
        if payload.get("geometryType") != "esriGeometryPolygon" or (
            payload.get("hasZ", False) is not False or payload.get("hasM", False) is not False
        ):
            raise GeometryError("Changed geometry type/dimensions")
        values = payload.get("features")
        if not isinstance(values, list) or len(values) != len(ids):
            raise GeometryError("Incomplete/oversized geometry batch")
        page_oids = []
        for value in values:
            oid, pin = identity(value)
            if oid not in ids or oid in seen_oids or pin not in pins or pin in seen_pins:
                raise GeometryError("Missing/duplicate/conflicting exact parcel/OID membership")
            if "geometry" not in value or value["geometry"] is None:
                raise GeometryError("Missing geometry; no partial success")
            geometry = value["geometry"]
            if not isinstance(geometry, dict):
                raise GeometryError("Unsupported geometry object")
            if "spatialReference" in geometry:
                native_crs(geometry["spatialReference"])
            seen_oids.add(oid)
            seen_pins.add(pin)
            page_oids.append(oid)
            features.append(value)
        if page_oids != sorted(ids):
            raise GeometryError("Unordered or unexpected geometry OID page")

    ids = sorted(first)
    for start in range(0, len(ids), size):
        batch(ids[start:start + size])
    last = membership()
    after = schema(request({"f": "json"}, query=False))
    if before != after or first != last or seen_oids != first or seen_pins != set(pins):
        raise GeometryError("Geometry metadata/edit token/membership drift; publication refused")
    return sorted(features, key=lambda f: identity(f)[1]), {
        "count": len(features), "membership_reconciled": True,
        "transactional_snapshot": False, "schema": before,
        "batch_size": size, "configured_batch_size": batch_size,
        "same_id_consistency": "edit-token checked; not atomic" if before["edit_token"] is not None
        else "UNKNOWN: no source edit token; non-atomic requests",
    }


def capture(directory: Path, pins: list[str], transport=None, *, batch_size: int = 50):
    directory.mkdir(exist_ok=False)
    transport = transport or UrllibJsonTransport(policy=POLICY)
    wire = isinstance(transport, UrllibJsonTransport)
    if wire and transport.policy != POLICY:
        raise GeometryError("Production geometry transport must use reviewed bounded policy")
    recorder = Capture(directory, transport)
    if wire:
        transport.begin_capture(directory / "http")
    try:
        features, checks = acquire(recorder.request, pins, batch_size=batch_size)
        return features, checks, recorder.records, wire
    finally:
        if wire:
            transport.end_capture()
