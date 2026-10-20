"""Exact bounded ArcGIS polygon acquisition for fixed native-SR AOI groups."""

from __future__ import annotations

import json
from dataclasses import dataclass

from pyproj import CRS

from mn_land.geometry import GeometryError
from mn_land.ingestion.source_checks import integer, inventory, metadata_contract, transfer_flag
from mn_land.ingestion.spatial_capture import POLICY
from mn_land.utils.http import ArcGISError


@dataclass(frozen=True)
class PolygonLayer:
    url: str
    layer_id: int
    name: str
    fields: tuple[tuple[str, str], ...]
    wkid: int

    @property
    def names(self):
        return tuple(name for name, _ in self.fields)


def spatial_reference(sr: object, wkid: int) -> None:
    if not isinstance(sr, dict):
        raise GeometryError("Missing thematic native CRS")
    codes = [sr[k] for k in ("wkid", "latestWkid") if k in sr]
    if not codes or any(type(code) is not int or code != wkid for code in codes):
        raise GeometryError("Unexpected/conflicting thematic CRS code")
    for name in ("wkt", "wkt2"):
        if name in sr and not CRS(sr[name]).equals(CRS(wkid)):
            raise GeometryError("Conflicting thematic WKT/code")
    if any(k in sr for k in ("vcsWkid", "latestVcsWkid")):
        raise GeometryError("Unsupported thematic vertical CRS")


def layer_schema(metadata: dict, spec: PolygonLayer) -> dict:
    if not isinstance(metadata, dict):
        raise GeometryError("Thematic metadata must be an object")
    result = metadata_contract(metadata, spec.layer_id, spec.names, spec.name)
    for field in result["requested_fields"]:
        if field.get("type") != dict(spec.fields)[field["name"]] or type(field.get("nullable")) is not bool:
            raise GeometryError("Changed thematic source field declaration")
    if metadata.get("geometryType") != "esriGeometryPolygon" or (
        metadata.get("hasZ") is not False or metadata.get("hasM") is not False
        or metadata["advancedQueryCapabilities"].get("supportsTrueCurve") is not True
    ):
        raise GeometryError("Unsupported thematic geometry/dimensions/true-curve capability")
    sr = metadata.get("extent", {}).get("spatialReference")
    spatial_reference(sr, spec.wkid)
    result.update(spatial_reference=sr, geometry_type="esriGeometryPolygon", true_curves=True,
                  has_z=False, has_m=False)
    return result


def confirmed_inventory(request, url: str, base: dict, payload: dict, count: int,
                        oid: str, limit: int, label: str, *, record_limit: int) -> set[int]:
    """A null ID array is NOT accepted alone: independently prove an empty page.

    The original response is retained unchanged. Missing ID keys, positive count,
    errors, truncation and any nonempty confirmation still fail normal checks.
    """
    if count == 0 and "objectIds" in payload and payload["objectIds"] is None:
        proof = request(url, {**base, "outFields": oid, "returnGeometry": "false",
                             "orderByFields": f"{oid} ASC", "resultOffset": 0,
                             "resultRecordCount": min(2000, record_limit)})
        if proof.get("features") != [] or transfer_flag(proof, label + " empty proof") is True:
            raise GeometryError("Null ID inventory lacks independent empty feature-page proof")
        payload = {**payload, "objectIds": []}
    return inventory(payload, count, oid, limit, label)


def fetch_polygons(request, spec: PolygonLayer, aoi_groups: list[dict], *,
                   schema=layer_schema, confirm_null_empty: bool = False) -> tuple[list[dict], dict]:
    if not isinstance(aoi_groups, list) or not 0 < len(aoi_groups) <= 13:
        raise GeometryError("Select 1..13 bounded native AOI groups")
    for group in aoi_groups:
        if len(json.dumps(group, allow_nan=False).encode()) > 6000:
            raise GeometryError("Spatial query geometry byte budget exceeded")
    start_schema = schema(request(spec.url, {"f": "json"}), spec)
    oid = start_schema["object_id"]
    query_url = spec.url + "/query"

    def memberships():
        results = []
        for group in aoi_groups:
            base = {"f": "json", "where": "1=1", "geometry": json.dumps(group, separators=(",", ":")),
                    "geometryType": "esriGeometryPolygon", "inSR": spec.wkid,
                    "spatialRel": "esriSpatialRelIntersects"}
            count = integer(request(query_url, {**base, "returnCountOnly": "true"}).get("count"),
                            "thematic count", minimum=0)
            if count > POLICY.max_inventory_ids:
                raise GeometryError("Thematic count exceeds inventory budget")
            payload = request(query_url, {**base, "returnIdsOnly": "true"})
            ids = confirmed_inventory(request, query_url, base, payload, count, oid,
                POLICY.max_inventory_ids, "thematic AOI", record_limit=start_schema["max_record_count"]
            ) if confirm_null_empty else inventory(
                payload, count, oid, POLICY.max_inventory_ids, "thematic AOI")
            results.append(sorted(ids))
        return results

    first = memberships()
    ids = sorted({identity for group in first for identity in group})
    if len(ids) > POLICY.max_inventory_ids:
        raise GeometryError("Combined thematic inventory exceeds budget")
    features = []
    seen = set()
    batch_size = min(10, start_schema["max_record_count"])

    def batch(members):
        params = {"f": "json", "where": "1=1", "objectIds": ",".join(map(str, members)),
                  "outFields": ",".join(spec.names), "returnGeometry": "true",
                  "returnTrueCurves": "true", "returnZ": "true", "returnM": "true",
                  "outSR": spec.wkid, "orderByFields": f"{oid} ASC",
                  "resultRecordCount": len(members), "resultOffset": 0}
        try:
            payload = request(query_url, params)
        except ArcGISError as exc:
            if len(members) == 1 or "body byte budget" not in str(exc):
                raise
            middle = len(members) // 2
            batch(members[:middle])
            batch(members[middle:])
            return
        spatial_reference(payload.get("spatialReference"), spec.wkid)
        if transfer_flag(payload, "thematic batch") is True or any(
            k in payload for k in ("transform", "quantizationParameters")
        ) or payload.get("geometryType") != "esriGeometryPolygon" or (
            payload.get("hasZ", False) is not False or payload.get("hasM", False) is not False
        ):
            raise GeometryError("Truncated/quantized/unsupported thematic geometry response")
        values = payload.get("features")
        if not isinstance(values, list) or len(values) != len(members):
            raise GeometryError("Incomplete/oversized thematic feature batch")
        actual = []
        for feature in values:
            if not isinstance(feature, dict) or not isinstance(feature.get("attributes"), dict):
                raise GeometryError("Invalid thematic feature/attributes")
            attributes = feature["attributes"]
            if not set(spec.names) <= attributes.keys():
                raise GeometryError("Missing thematic source fields")
            identity = integer(attributes.get(oid), "thematic OID", minimum=0)
            if identity not in members or identity in seen:
                raise GeometryError("Duplicate/unexpected thematic OID")
            if not isinstance(feature.get("geometry"), dict):
                raise GeometryError("Null/missing thematic geometry")
            if "spatialReference" in feature["geometry"]:
                spatial_reference(feature["geometry"]["spatialReference"], spec.wkid)
            seen.add(identity)
            actual.append(identity)
            features.append(feature)
        if actual != sorted(members):
            raise GeometryError("Thematic OID order/membership mismatch")

    for offset in range(0, len(ids), batch_size):
        batch(ids[offset:offset + batch_size])
    last = memberships()
    end_schema = schema(request(spec.url, {"f": "json"}), spec)
    if first != last or start_schema != end_schema or seen != set(ids):
        raise GeometryError("Thematic schema/edit token/membership drift")
    return features, {"schema": start_schema, "aoi_membership": first, "unique_count": len(ids),
                      "membership_reconciled": True, "transactional_snapshot": False,
                      "same_id_consistency": "unknown; no edit token" if start_schema["edit_token"] is None
                      else "edit token checked; non-atomic requests"}
