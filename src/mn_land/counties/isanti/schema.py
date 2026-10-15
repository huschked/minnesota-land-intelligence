"""Isanti's reviewed metadata declarations; transport policy belongs elsewhere."""

import logging
from collections.abc import Mapping

from .mappings import MAILING_FIELDS, SOURCE_FIELDS

LOGGER = logging.getLogger(__name__)


class SchemaValidationError(ValueError):
    """Source declarations are incompatible with this reviewed county adapter."""


NUMERIC_FIELDS = {
    SOURCE_FIELDS[name]
    for name in (
        "deeded_acres",
        "previous_taxes_owed",
        "current_tax_amount",
        "land_value",
        "improvement_value",
        "assessed_value",
    )
}
EXPECTED_TYPES = {
    name: "esriFieldTypeOID"
    if name == "OBJECTID"
    else "esriFieldTypeDouble"
    if name in NUMERIC_FIELDS
    else "esriFieldTypeString"
    for name in (*SOURCE_FIELDS.values(), *MAILING_FIELDS)
}
EXPECTED_ALIASES = {
    "OBJECTID": "OBJECTID",
    "PSTLADDRESS": "Postal Address",
    "PSTLADDRESS2": "Postal Address Line 2",
    "PSTLCITY": "Postal City",
    "PSTLSTATE": "Postal State",
    "PSTLZIP5": "Postal Zip 5",
    "PSTLZIP4": "Postal Zip +4",
    "PARCELID": "Parcel Identification Number",
    "DEEDEDACRES": "Deeded Acres",
    "TOTPRVTXTOD": "Total Previous Taxes Owed",
    "TOTCNTTXOD": "Total Current Taxes Owed",
    "LNDVALUE": "Land Value",
    "IMPRVALUE": "Improved Value",
    "CNTASSDVAL": "Current Assessed Value",
    "OWNERNME1": "First Owner Name",
    "PRIMARYCLASS": "Class Classification 1",
    "LEGALDESCRIPT": "Legal Description",
    "PARCEL_REPORT": "Parcel Report (Link)",
}


def validate_metadata(metadata: object) -> None:
    if not isinstance(metadata, Mapping) or not isinstance(metadata.get("fields"), list):
        raise SchemaValidationError("Isanti metadata must contain a fields array")
    declarations = {}
    for entry in metadata["fields"]:
        if (
            not isinstance(entry, Mapping)
            or not isinstance(entry.get("name"), str)
            or not entry["name"]
        ):
            raise ValueError("Isanti field declaration requires a nonblank field name")
        if entry["name"] in declarations:
            raise ValueError(f"duplicate Isanti field declaration: {entry['name']}")
        declarations[entry["name"]] = entry
    for name, expected in EXPECTED_TYPES.items():
        declaration = declarations.get(name)
        if declaration is None or declaration.get("type") != expected:
            raise ValueError(f"Isanti schema field {name} must declare type {expected}")
        if not isinstance(declaration.get("nullable"), bool):
            raise SchemaValidationError(
                f"Isanti schema field {name} must declare boolean nullability"
            )
        if name == "OBJECTID" and declaration["nullable"] is not False:
            raise ValueError("Isanti OBJECTID must be non-nullable")
        expected_alias = EXPECTED_ALIASES.get(name)
        if expected_alias and declaration.get("alias") != expected_alias:
            LOGGER.warning(
                "isanti_alias_changed field=%s expected=%s actual=%s",
                name,
                expected_alias,
                declaration.get("alias"),
            )
    added = sorted(set(declarations) - set(EXPECTED_TYPES))
    if added:
        LOGGER.info("isanti_unrequested_fields count=%s fields=%s", len(added), added)
