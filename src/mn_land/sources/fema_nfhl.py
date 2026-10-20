"""Fixed effective FEMA MapServer contract; no preliminary/county substitution."""
from __future__ import annotations

import re
from collections.abc import Callable

from mn_land.geometry import GeometryError
from mn_land.ingestion.source_checks import integer, transfer_flag
from mn_land.ingestion.spatial_layers import PolygonLayer, confirmed_inventory, spatial_reference

SERVICE = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"
OID = ("OBJECTID", "esriFieldTypeOID")
TEXT = "esriFieldTypeString"
DATE = "esriFieldTypeDate"

ZONES = PolygonLayer(SERVICE + "/28", 28, "Flood Hazard Zones", (OID,
    ("DFIRM_ID", TEXT), ("FLD_AR_ID", TEXT), ("FLD_ZONE", TEXT), ("ZONE_SUBTY", TEXT),
    ("SFHA_TF", TEXT), ("SOURCE_CIT", TEXT), ("GFID", TEXT),
    ("GlobalID", "esriFieldTypeGlobalID")), 4269)
AVAILABILITY = PolygonLayer(SERVICE + "/0", 0, "NFHL Availability", (OID,
    ("STUDY_ID", TEXT), ("GlobalID", "esriFieldTypeGlobalID")), 4269)
PANELS = PolygonLayer(SERVICE + "/3", 3, "FIRM Panels", (OID,
    ("DFIRM_ID", TEXT), ("FIRM_PAN", TEXT), ("EFF_DATE", DATE), ("PRE_DATE", DATE),
    ("SCALE", TEXT), ("PANEL_TYP", TEXT), ("PNP_REASON", TEXT), ("SOURCE_CIT", TEXT),
    ("GFID", TEXT), ("GlobalID", "esriFieldTypeGlobalID")), 4269)
REVISIONS = PolygonLayer(SERVICE + "/1", 1, "LOMRs", (OID,
    ("DFIRM_ID", TEXT), ("LOMR_ID", TEXT), ("CASE_NO", TEXT), ("EFF_DATE", DATE),
    ("STATUS", TEXT), ("SOURCE_CIT", TEXT), ("GFID", TEXT),
    ("GlobalID", "esriFieldTypeGlobalID")), 4269)
STUDIES = PolygonLayer(SERVICE + "/41", 41, "Study_Info", (OID,
    ("DFIRM_ID", TEXT), ("STD_NFO_ID", TEXT), ("STUDY_NM", TEXT), ("CNTY_NM", TEXT),
    ("H_DATUM", TEXT), ("PROJECTION", TEXT), ("INDX_EFFDT", DATE), ("DBREV_DT", DATE),
    ("GFID", TEXT), ("GlobalID", "esriFieldTypeGlobalID")), 4269)
LAYERS = {"zones": ZONES, "availability": AVAILABILITY, "panels": PANELS,
          "revisions": REVISIONS}
CATEGORY_POLICY = {
    "version": "fema-effective-categories-v1",
    "sfha_zones": ["A", "AE", "AH", "AO", "A99", "AR", "V", "VE"],
    "sfha_subtypes": [None, "", "FLOODWAY"],
    "x_subtypes": ["0.2 PCT ANNUAL CHANCE FLOOD HAZARD", "AREA OF MINIMAL FLOOD HAZARD"],
    "unknown": "hold overall metrics for positive unknown/conflicting classification",
    "floodway": "subset of mapped SFHA, never added twice",
    "interpretation": "mapped screening categories, not insurance, regulatory or no-risk determination",
}


def study_id(value: object) -> str | None:
    """Allow only a bounded source identifier, never arbitrary SQL text."""
    return value if isinstance(value, str) and re.fullmatch(r"[0-9]{5}[0-9C]", value) else None


def service_contract(metadata: dict) -> dict:
    if not isinstance(metadata, dict) or "Query" not in metadata.get("capabilities", "").split(","):
        raise GeometryError("FEMA service Query capability required")
    spatial_reference(metadata.get("spatialReference"), 4269)
    selected = []
    for key, specs in (("layers", list(LAYERS.values())), ("tables", [STUDIES])):
        entries = metadata.get(key)
        if not isinstance(entries, list) or any(not isinstance(r, dict) for r in entries):
            raise GeometryError("FEMA service layer/table inventory missing")
        for spec in specs:
            matches = [r for r in entries if type(r.get("id")) is int and r["id"] == spec.layer_id]
            if len(matches) != 1 or matches[0].get("name") != spec.name:
                raise GeometryError("FEMA effective service layer identity changed")
            selected.append(matches[0])
    return {"version": metadata.get("currentVersion"), "selected_layers": selected,
            "spatial_reference": metadata["spatialReference"],
            "capabilities": metadata["capabilities"],
            "source_notices": {k: metadata.get(k) for k in ("serviceDescription", "description", "copyrightText")}}


def category(raw: dict) -> str:
    zone, subtype, sfha = (raw.get(k) for k in ("FLD_ZONE", "ZONE_SUBTY", "SFHA_TF"))
    if (zone in CATEGORY_POLICY["sfha_zones"] and sfha == "T"
            and subtype in CATEGORY_POLICY["sfha_subtypes"]):
        return "sfha_floodway" if subtype == "FLOODWAY" else "sfha_other"
    if zone == "X" and sfha == "F":
        if subtype == "0.2 PCT ANNUAL CHANCE FLOOD HAZARD":
            return "annual_chance_0_2pct"
        if subtype == "AREA OF MINIMAL FLOOD HAZARD":
            return "minimal_hazard"
    return "unknown"


def map_schema(metadata: dict, spec: PolygonLayer) -> dict:
    """MapServer omissions remain unknown; actual returned coordinates gate 2D.

    Do not fabricate FeatureServer nullable/hasZ/hasM/objectIdField declarations.
    The unique explicitly typed OID field supplies the MapServer OID identity.
    """
    if not isinstance(metadata, dict) or metadata.get("id") != spec.layer_id or (
        type(metadata.get("id")) is not int or metadata.get("name") != spec.name
        or metadata.get("type") != ("Table" if spec == STUDIES else "Feature Layer")
    ):
        raise GeometryError("Unexpected FEMA layer/table identity")
    capabilities = metadata.get("capabilities")
    advanced = metadata.get("advancedQueryCapabilities")
    if not isinstance(capabilities, str) or "Query" not in capabilities.split(",") or (
        not isinstance(advanced, dict) or any(advanced.get(k) is not True
            for k in ("supportsOrderBy", "supportsPagination"))
    ):
        raise GeometryError("FEMA ordered query/pagination capability required")
    declarations = metadata.get("fields")
    if not isinstance(declarations, list) or any(not isinstance(f, dict) for f in declarations):
        raise GeometryError("Missing FEMA field declarations")
    fields = {f.get("name"): f for f in declarations if isinstance(f.get("name"), str)}
    if len(fields) != len(declarations) or [f["name"] for f in declarations
        if f.get("type") == "esriFieldTypeOID"] != ["OBJECTID"]:
        raise GeometryError("Duplicate/missing/conflicting FEMA OID/fields")
    if metadata.get("objectIdField", "OBJECTID") != "OBJECTID":
        raise GeometryError("Conflicting FEMA OID declaration")
    unique = metadata.get("uniqueIdInfo")
    if unique is not None and (not isinstance(unique, dict) or unique.get("OIDFieldContainsHashValue") is True):
        raise GeometryError("FEMA hashed/unsupported unique-ID query contract")
    for name, kind in spec.fields:
        if name not in fields or fields[name].get("type") != kind or (
            "nullable" in fields[name] and type(fields[name]["nullable"]) is not bool
        ):
            raise GeometryError("Changed FEMA requested field type/nullability")
    if fields["OBJECTID"].get("nullable", False) is not False:
        raise GeometryError("FEMA OID must not declare nullable")
    editing = metadata.get("editingInfo")
    if editing is not None and not isinstance(editing, dict):
        raise GeometryError("Invalid FEMA edit evidence")
    token = editing.get("lastEditDate") if editing else None
    if token is not None:
        integer(token, "FEMA edit token", minimum=0)
    result = {"id": spec.layer_id, "name": spec.name, "object_id": "OBJECTID",
        "max_record_count": integer(metadata.get("maxRecordCount"), "FEMA record cap", minimum=1),
        "capabilities": sorted(capabilities.split(",")), "edit_token": token,
        "requested_fields": [fields[n] for n in spec.names],
        "oid_identity_evidence": "unique esriFieldTypeOID declaration; returned IDs reconciled",
        "nullable_declarations": {n: fields[n].get("nullable") for n in spec.names},
        "pagination": True, "order_by": True}
    if spec != STUDIES:
        if metadata.get("geometryType") != "esriGeometryPolygon" or (
            advanced.get("supportsTrueCurve") is not True
        ):
            raise GeometryError("FEMA polygon/true-curve contract required")
        for key in ("hasZ", "hasM"):
            if key in metadata and metadata[key] is not False:
                raise GeometryError("Unsupported FEMA declared dimensions")
        sr = metadata.get("extent", {}).get("spatialReference")
        spatial_reference(sr, spec.wkid)
        if "sourceSpatialReference" in metadata:
            spatial_reference(metadata["sourceSpatialReference"], spec.wkid)
        result.update(spatial_reference=sr, geometry_type="esriGeometryPolygon", true_curves=True,
                      has_z=metadata.get("hasZ"), has_m=metadata.get("hasM"),
                      dimension_gate="returned native coordinates must be exactly 2D")
    return result


def fetch_studies(request: Callable, identifiers: list[str]) -> tuple[list[dict], dict]:
    if identifiers != sorted(set(identifiers)) or len(identifiers) > 20 or any(
        study_id(s) != s for s in identifiers
    ):
        raise GeometryError("Select <=20 exact safe FEMA study identifiers")
    where = "DFIRM_ID IN (" + ",".join("'" + s + "'" for s in identifiers) + ")" if identifiers else "1=0"
    spec, url = STUDIES, STUDIES.url + "/query"
    first = map_schema(request(spec.url, {"f": "json"}), spec)

    def members() -> list[int]:
        base = {"f": "json", "where": where}
        count = integer(request(url, {**base, "returnCountOnly": "true"}).get("count"),
                        "FEMA study count", minimum=0)
        if count > 100:
            raise GeometryError("FEMA study table exceeds 100-row budget")
        return sorted(confirmed_inventory(request, url, base,
            request(url, {**base, "returnIdsOnly": "true"}), count, "OBJECTID", 100, "FEMA study",
            record_limit=first["max_record_count"]))

    ids = members()
    rows = []
    size = min(10, first["max_record_count"])
    for offset in range(0, len(ids), size):
        batch = ids[offset:offset + size]
        payload = request(url, {"f": "json", "where": where, "objectIds": ",".join(map(str, batch)),
            "outFields": ",".join(spec.names), "returnGeometry": "false",
            "orderByFields": "OBJECTID ASC", "resultOffset": 0, "resultRecordCount": len(batch)})
        values = payload.get("features")
        if transfer_flag(payload, "FEMA study page") is True or not isinstance(values, list) or (
            len(values) != len(batch)
        ):
            raise GeometryError("Truncated/incomplete FEMA study page")
        actual = []
        for row in values:
            if not isinstance(row, dict) or not isinstance(row.get("attributes"), dict) or (
                not set(spec.names) <= row["attributes"].keys() or "geometry" in row
            ):
                raise GeometryError("Invalid FEMA study row/fields")
            raw = row["attributes"]
            actual.append(integer(raw["OBJECTID"], "FEMA study OID", minimum=0))
            if raw["DFIRM_ID"] not in identifiers:
                raise GeometryError("Unexpected FEMA study identity")
            rows.append(raw)
        if actual != batch:
            raise GeometryError("FEMA study OID order/membership differs")
    if members() != ids or map_schema(request(spec.url, {"f": "json"}), spec) != first:
        raise GeometryError("FEMA study metadata/membership drift")
    return rows, {"schema": first, "selected_studies": identifiers, "object_ids": ids,
                  "unique_count": len(ids), "membership_reconciled": True,
                  "transactional_snapshot": False}
