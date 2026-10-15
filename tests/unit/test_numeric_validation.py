"""F03/F05/F06: finite numbers, exact identifiers, and typed years."""

import argparse
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from mn_land.cli import decimal_argument
from mn_land.counties.isanti.adapter import parse_decimal
from mn_land.counties.isanti.delinquency import classify_assessment_years, normalize_parcel_id
from mn_land.counties.isanti.review import build_review
from mn_land.delinquency.file_loader import parse_money, parse_years
from mn_land.delinquency.pipeline import import_and_join_delinquency
from mn_land.filtering.candidate_filter import filter_candidates
from mn_land.ingestion.pipeline import run_pipeline
from mn_land.utils.validation import minimum_acres


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        {},
        [],
        "NaN",
        "sNaN",
        "Infinity",
        "-Infinity",
        float("nan"),
        float("inf"),
        Decimal("NaN"),
        "not a number",
    ],
)
@pytest.mark.parametrize("parser", [parse_decimal, parse_money, minimum_acres])
def test_F03_nonfinite_boolean_and_object_values_fail(value, parser) -> None:
    with pytest.raises(ValueError):
        parser(value)


@pytest.mark.parametrize("value", ["NaN", "sNaN", "Infinity", "-Infinity", "-1", "bad"])
def test_F03_CLI_rejects_invalid_minimum(value) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        decimal_argument(value)


def test_F03_zero_null_and_negative_money_remain_distinct() -> None:
    assert minimum_acres(0) == Decimal(0)
    assert minimum_acres("10.00") == Decimal(10)
    assert parse_money(None) is None
    assert parse_decimal("") is None
    assert parse_money("($1,250.50)") == Decimal("-1250.50")
    assert parse_decimal("-1.5") == Decimal("-1.5")


@pytest.mark.parametrize("value", ["1,2", "1$2", "--1", "1_000", "(1", "1.2.3"])
def test_F03_malformed_numeric_syntax_is_not_repaired(value) -> None:
    with pytest.raises(ValueError):
        parse_money(value)


@pytest.mark.parametrize("value", [True, Decimal("NaN"), Decimal("Infinity"), Decimal(-1)])
def test_F03_callable_entry_points_validate_before_IO(value) -> None:
    missing = Path("does-not-exist")
    for function in (
        lambda: run_pipeline(object(), value),
        lambda: import_and_join_delinquency(missing, missing, value),
        lambda: build_review(missing, value),
        lambda: filter_candidates([], value),
    ):
        with pytest.raises(ValueError):
            function()


@pytest.mark.parametrize("value", [123, 123.5, 1e8, True, Decimal(20010200), [], {}])
def test_F05_identifiers_are_not_numeric_coercions(value) -> None:
    with pytest.raises(ValueError):
        normalize_parcel_id(value)


@pytest.mark.parametrize("value", [2024, 2024.0, Decimal(2024), "2024"])
def test_F06_exact_numeric_and_text_years_agree(value) -> None:
    assert classify_assessment_years(value, 2025)[:3] == (2024, 2025, 2026)
    assert parse_years(value) == (2024,)


@pytest.mark.parametrize(
    "value", [True, 2024.5, float("nan"), float("inf"), date(2024, 1, 1), "2024.0", "24", None]
)
def test_F06_mixed_years_reject_unsafe_representations(value) -> None:
    with pytest.raises(ValueError):
        classify_assessment_years(value, "2025")
