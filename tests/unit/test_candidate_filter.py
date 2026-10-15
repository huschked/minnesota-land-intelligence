from datetime import UTC, datetime
from decimal import Decimal

import pytest

from mn_land.filtering.candidate_filter import filter_candidates
from mn_land.models import Parcel, SourceMetadata


def parcel(acres: str | None, tax: str | None, *, verified: bool = True) -> Parcel:
    source = SourceMetadata("Test", "Test", "https://example.test/service", 0, datetime.now(UTC))
    return Parcel(
        county="Test", parcel_id="1", owner_name=None, owner_mailing_address=None,
        deeded_acres=Decimal(acres) if acres is not None else None,
        previous_taxes_owed=Decimal(tax) if tax is not None else None,
        past_due_tax_amount=Decimal(tax) if tax is not None and verified else None,
        current_tax_amount=None, land_value=None, improvement_value=None, assessed_value=None,
        property_classification=None, legal_description=None, geometry=None, source_reference=None,
        source_metadata=source, tax_semantics_verified=verified,
    )


@pytest.mark.parametrize("acres", ["10.00", "25.00"])
def test_minimum_acreage_boundary_accepts(acres: str) -> None:
    assert len(filter_candidates([parcel(acres, "0.01")], Decimal(10)).accepted) == 1


def test_under_minimum_and_missing_acreage_are_distinct() -> None:
    result = filter_candidates([parcel("9.99", "1"), parcel(None, "1")], Decimal(10))
    assert result.rejected == {"under_minimum_acreage": 1, "missing_acreage": 1}


@pytest.mark.parametrize("tax", ["0", "-1"])
def test_nonpositive_tax_rejected(tax: str) -> None:
    assert filter_candidates([parcel("10", tax)], Decimal(10)).rejected["no_past_due_tax"] == 1


def test_missing_tax_and_ambiguous_semantics_are_distinct() -> None:
    missing = filter_candidates([parcel("10", None)], Decimal(10))
    ambiguous = filter_candidates([parcel("10", "20", verified=False)], Decimal(10))
    assert missing.rejected["missing_past_due_tax"] == 1
    assert ambiguous.rejected["ambiguous_tax_semantics"] == 1
