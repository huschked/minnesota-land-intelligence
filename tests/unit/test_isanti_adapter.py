import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from mn_land.counties.isanti.adapter import IsantiAdapter, parse_decimal

FIXTURE = Path(__file__).parents[1] / "fixtures" / "isanti_parcel.json"


def test_isanti_field_mapping_preserves_cautious_tax_semantics() -> None:
    record = json.loads(FIXTURE.read_text(encoding="utf-8"))
    parcel = IsantiAdapter(client=object()).normalize_parcel(record, datetime.now(UTC))
    assert parcel.parcel_id == "02.001.0200"
    assert parcel.deeded_acres == Decimal("25.5")
    assert parcel.previous_taxes_owed == Decimal("5000.01")
    assert parcel.past_due_tax_amount is None
    assert parcel.tax_semantics_verified is False
    assert parcel.owner_mailing_address == "100 Main St, Cambridge, MN, 55008"
    assert parcel.assessed_value == Decimal(175000)


def test_null_values_remain_unknown() -> None:
    record = {"PARCELID": "x", "DEEDEDACRES": None, "TOTPRVTXTOD": None}
    parcel = IsantiAdapter(client=object()).normalize_parcel(record, datetime.now(UTC))
    assert parcel.deeded_acres is None
    assert parcel.previous_taxes_owed is None
    assert parcel.past_due_tax_amount is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("$5,000.01", Decimal("5000.01")), (0, Decimal(0)), (None, None), ("", None)],
)
def test_numeric_parsing(raw: object, expected: Decimal | None) -> None:
    assert parse_decimal(raw) == expected


def test_bad_numeric_value_fails_visibly() -> None:
    with pytest.raises(ValueError, match="cannot parse"):
        parse_decimal("unknown")
