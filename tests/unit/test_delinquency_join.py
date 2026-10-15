from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from mn_land.delinquency.join import join_delinquency_records
from mn_land.models import DelinquencyRecord, DelinquencyStatus, Parcel, SourceMetadata

SOURCE = SourceMetadata("Isanti County", "Test", "official.csv", None, datetime.now(UTC))


def parcel(parcel_id: str = "01.001.0201") -> Parcel:
    return Parcel(
        county="Isanti",
        parcel_id=parcel_id,
        owner_name=None,
        owner_mailing_address=None,
        deeded_acres=Decimal(20),
        previous_taxes_owed=Decimal(999),
        past_due_tax_amount=None,
        current_tax_amount=None,
        land_value=None,
        improvement_value=None,
        assessed_value=None,
        property_classification=None,
        legal_description=None,
        geometry=None,
        source_reference=None,
        source_metadata=SOURCE,
        tax_semantics_verified=False,
    )


def record(parcel_id: str = "010010201", row: int = 2) -> DelinquencyRecord:
    return DelinquencyRecord(
        county="Isanti",
        parcel_id=parcel_id,
        normalized_parcel_id="".join(character for character in parcel_id if character.isdigit()),
        taxpayer_name=None,
        owner_name=None,
        mailing_address=None,
        delinquent_years=None,
        delinquent_tax_amount=None,
        penalty_amount=None,
        total_taxes_and_penalties_due=None,
        source_metadata=SOURCE,
        source_row_number=row,
        original_row={"PIN": parcel_id},
    )


def test_exact_normalized_join_is_verified() -> None:
    result = join_delinquency_records([parcel()], [record()])
    assert len(result.verified_matches) == 1
    assert result.matches[0].status == DelinquencyStatus.VERIFIED_DELINQUENT


def test_unmatched_record_remains_visible() -> None:
    result = join_delinquency_records([parcel()], [record("99.999.9999")])
    assert result.matches == ()
    assert result.unmatched_records[0].parcel_id == "99.999.9999"


def test_duplicate_delinquency_rows_are_ambiguous_not_aggregated() -> None:
    duplicate = replace(record(), source_row_number=3)
    result = join_delinquency_records([parcel()], [record(), duplicate])
    assert not result.verified_matches
    assert len(result.duplicate_records["010010201"]) == 2
    assert result.matches[0].status == DelinquencyStatus.AMBIGUOUS


def test_positive_gis_tax_field_alone_never_verifies_delinquency() -> None:
    result = join_delinquency_records([parcel()], [])
    assert not result.verified_matches
    assert parcel().previous_taxes_owed == Decimal(999)


def test_conflicting_official_evidence_blocks_promotion_without_losing_match() -> None:
    held = replace(record(), verification_hold_reason="Official report conflicts with listing")
    result = join_delinquency_records([parcel()], [held])
    assert len(result.exact_matches) == 1
    assert result.matches[0].status == DelinquencyStatus.UNVERIFIED
    assert result.matches[0].reason == held.verification_hold_reason
    assert not result.verified_matches
