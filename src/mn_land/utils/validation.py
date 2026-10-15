"""Representation checks shared by ingestion boundaries, not county semantics."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


class InputValidationError(ValueError):
    """An input representation is not safe for canonical normalization."""


def finite_decimal(value: object, *, currency: bool = False) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise InputValidationError("must be a finite numeric value, not a boolean or object")
    text = str(value).strip()
    if not text:
        return None
    if currency and text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    if currency:
        pattern = r"[+-]?\$?(?:(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
    else:
        pattern = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
    if not re.fullmatch(pattern, text):
        raise InputValidationError(
            "cannot parse numeric value; require finite, unambiguous decimal/grouping syntax"
        )
    text = text.replace(",", "").replace("$", "")
    try:
        parsed = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("cannot parse numeric value") from exc
    if not parsed.is_finite():
        raise ValueError("must be finite; NaN and Infinity are not accepted")
    return parsed


def minimum_acres(value: object) -> Decimal:
    parsed = finite_decimal(value)
    if parsed is None or parsed < 0:
        raise ValueError("minimum acres must be a finite non-negative number")
    return parsed


def optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InputValidationError("must be text or null; numeric/object coercion is not accepted")
    return value.strip() or None


def year_number(value: object) -> int:
    if isinstance(value, str):
        text = value.strip()
        if len(text) == 4 and text.isascii() and text.isdigit() and 1000 <= int(text) <= 9999:
            return int(text)
    elif isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        parsed = finite_decimal(value)
        if parsed is not None and parsed == parsed.to_integral_value() and 1000 <= parsed <= 9999:
            return int(parsed)
    raise ValueError("year must be four ASCII digits or an exact four-digit integral cell")
