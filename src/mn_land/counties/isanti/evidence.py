"""Reviewed Isanti public link destinations and literal listing display fields."""

import re
from urllib.parse import parse_qsl, urlsplit

from .delinquency import normalize_parcel_id
from .mappings import LAYER_ID, SERVICE_URL

LISTING_FIELDS = frozenset(
    [
        "JUR",
        "TAXYR",
        "ASMTYR",
        "ROLLTYPE",
        "PARID",
        "EFFDATE",
        "EFFDATE2",
        "LTRDT",
        "TAXAMT",
        "PENAMT",
        "INTAMT",
        "FEEAMT",
        "TOTAMT",
        "PENAMT2",
        "INTAMT2",
        "TOTAMT2",
        "OWN1",
        "OWN2",
        "LEGAL",
        "MAILADDR1",
        "MAILADDR2",
        "MAILADDR3",
        "MAILCITY",
        "AUTHNAME",
        "SPAAMT",
        "TAXONLYAMT",
        "PROPPADDR",
        "PROPCITY",
        "PROPSTATE",
        "PROPZIP",
        "CARE_OF",
        "VALCLASS",
    ]
)
REPORT_BASE = "https://gis.co.isanti.mn.us/ParcelReports/PublicParcelReport.ashx"


def public_link(value: object, parcel_id: str) -> str | None:
    """Strict exact host/path/query allowlist, bound to this parcel, with no fetch."""
    if not isinstance(value, str) or any(char.isspace() or ord(char) < 32 for char in value):
        return None
    if any(char in value for char in ("\\", "%", "#")):
        return None
    try:
        parts = urlsplit(value)
        if (
            parts.scheme != "https"
            or parts.netloc != "gis.co.isanti.mn.us"
            or parts.username
            or parts.password
            or parts.port is not None
        ):
            return None
        if value == f"{SERVICE_URL}/{LAYER_ID}":
            return value
        if parts.path != "/ParcelReports/PublicParcelReport.ashx":
            return None
        query = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
        if len(query) != 1 or query[0][0] != "PIN" or not re.fullmatch(r"[0-9.\-]+", query[0][1]):
            return None
        key = normalize_parcel_id(parcel_id)
        if len(key) != 9 or normalize_parcel_id(query[0][1]) != key:
            return None
        return value
    except (ValueError, TypeError):
        return None


def report_link(parcel_id: str) -> str | None:
    """Construct only a valid county report reference, not evidence of its contents."""
    return public_link(f"{REPORT_BASE}?PIN={parcel_id}", parcel_id)
