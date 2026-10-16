"""County-independent ArcGIS capability and membership checks."""

from collections.abc import Sequence
from typing import Any

from mn_land.utils.http import ArcGISError


def integer(value: Any, label: str, *, minimum: int | None = None) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        raise ArcGISError(
            f"{label} must be a non-boolean integer"
            + (f" >= {minimum}" if minimum is not None else "")
        )
    return value


def transfer_flag(payload: dict, label: str) -> bool | None:
    flag = payload.get("exceededTransferLimit")
    if "exceededTransferLimit" in payload and type(flag) is not bool:
        raise ArcGISError(f"{label}: exceededTransferLimit must be boolean")
    return flag


def metadata_contract(
    metadata: dict,
    layer_id: int,
    out_fields: Sequence[str],
    expected_name: str | None,
) -> dict:
    if integer(metadata.get("id"), "metadata layer id", minimum=0) != layer_id:
        raise ArcGISError("Unexpected layer identity")
    name = metadata.get("name")
    if not isinstance(name, str) or not name.strip() or (expected_name and name != expected_name):
        raise ArcGISError("Unexpected layer name")
    capabilities = metadata.get("capabilities")
    if not isinstance(capabilities, str) or "Query" not in {
        part.strip() for part in capabilities.split(",")
    }:
        raise ArcGISError("Layer must advertise Query capability")
    advanced = metadata.get("advancedQueryCapabilities")
    if not isinstance(advanced, dict) or any(
        advanced.get(key) is not True for key in ("supportsPagination", "supportsOrderBy")
    ):
        raise ArcGISError("Layer must support pagination and order-by")
    limit = integer(metadata.get("maxRecordCount"), "maxRecordCount", minimum=1)
    oid = metadata.get("objectIdField")
    if not isinstance(oid, str) or not oid or oid not in out_fields:
        raise ArcGISError("Declared OID must be included in requested fields")
    fields = metadata.get("fields")
    if not isinstance(fields, list) or any(not isinstance(field, dict) for field in fields):
        raise ArcGISError("Metadata fields must be objects")
    declarations = {}
    for field in fields:
        field_name = field.get("name")
        if not isinstance(field_name, str) or not field_name or field_name in declarations:
            raise ArcGISError("Invalid or duplicate field declaration")
        declarations[field_name] = field
    if not set(out_fields) <= declarations.keys():
        raise ArcGISError("Missing requested field declaration")
    if (
        declarations[oid].get("type") != "esriFieldTypeOID"
        or declarations[oid].get("nullable") is not False
    ):
        raise ArcGISError("Declared OID must have non-nullable OID type")
    editing = metadata.get("editingInfo")
    if editing is not None and not isinstance(editing, dict):
        raise ArcGISError("Invalid editingInfo")
    edit_token = editing.get("lastEditDate") if editing else None
    if edit_token is not None:
        integer(edit_token, "editingInfo.lastEditDate", minimum=0)
    return {
        "id": layer_id,
        "name": name,
        "object_id": oid,
        "max_record_count": limit,
        "capabilities": sorted(part.strip() for part in capabilities.split(",")),
        "pagination": True,
        "order_by": True,
        "requested_fields": [declarations[field] for field in sorted(out_fields)],
        "edit_token": edit_token,
    }


def inventory(payload: dict, count: int, oid: str, limit: int, label: str) -> set[int]:
    if payload.get("objectIdFieldName") != oid:
        raise ArcGISError(f"{label}: unexpected inventory OID field")
    ids = payload.get("objectIds")
    if not isinstance(ids, list) or len(ids) > limit:
        raise ArcGISError(f"{label}: missing inventory or inventory exceeds ID budget")
    if transfer_flag(payload, label) is True:
        raise ArcGISError(f"{label}: incomplete ID inventory")
    seen = set()
    for value in ids:
        integer(value, f"{label} OID")
        if value in seen:
            raise ArcGISError(f"{label}: Duplicate object ID")
        seen.add(value)
    if len(seen) != count:
        raise ArcGISError(f"{label}: count and inventory disagree")
    return seen
