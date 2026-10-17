"""U04/U05/U10: pure deterministic views, nulls, ordering and parcel identity."""

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from types import SimpleNamespace

import pytest

from mn_land.parcel_table import (
    ParcelDataset,
    TableFilters,
    number,
    project_rows,
    query,
    select_parcel,
    selected_row,
    selector_ids,
)
from mn_land.review_service import SnapshotKey


def record(parcel_id="0001", acres="10", improvement="0", classification="Other", owner="Example"):
    return {
        "parcel_id": parcel_id,
        "deeded_acres": acres,
        "improvement_value": improvement,
        "property_classification": classification,
        "owner_name": owner,
    }


@pytest.fixture
def dataset():
    rows = [
        record("0001", "10", "0"),
        record("0002", "100", None, None, None),
        record("0003", "20", "100", "PILT-Payment In-Lieu of Taxes"),
        record("0004", "20", "9", "Rural Vacant Land/Non-Productive"),
        record("0005", "10.0000000000000001", "9", "5E-Exempt Properties"),
    ]
    overview = SimpleNamespace(key=SnapshotKey("review", "saved"), completion_sha256="a" * 64)
    return ParcelDataset(
        overview, Decimal(10), project_rows(rows, [rows[0], record("0006", "11", "0")], Decimal(10))
    )


def ids(result):
    return [row.parcel_id for row in result.filtered]


def test_dynamic_distinct_counts_keep_period_overlap_and_nested_views(dataset):
    result = query(dataset, TableFilters(view="either"))
    assert dict(result.counts) == {
        "focused": 2,
        "outside_special": 3,
        "prior": 5,
        "special": 2,
        "current": 2,
        "either": 6,
        "both": 1,
    }
    assert ids(query(dataset, TableFilters())) == ["0001", "0004"]
    assert ids(query(dataset, TableFilters(view="both"))) == ["0001"]
    assert len(ids(result)) == 6  # not prior 5 + current 2
    filtered = query(dataset, TableFilters(view="either", minimum_acres=Decimal(20)))
    assert dict(filtered.counts)["either"] == 3
    assert dict(filtered.counts)["current"] == 0


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("all", ["0001", "0002", "0003", "0004", "0005", "0006"]),
        ("known", ["0001", "0003", "0004", "0005", "0006"]),
        ("unknown", ["0002"]),
        ("zero", ["0001", "0006"]),
        ("nonzero", ["0003", "0004", "0005"]),
    ],
)
def test_improvement_unknown_is_not_zero(dataset, mode, expected):
    assert ids(query(dataset, TableFilters(view="either", improvement=mode))) == expected


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("all", ["0001", "0002", "0003", "0004", "0005", "0006"]),
        ("only", ["0003", "0005"]),
        ("exclude", ["0001", "0004", "0006"]),
        ("unknown", ["0002"]),
    ],
)
def test_special_filter_does_not_call_unknown_classification_known_other(dataset, mode, expected):
    assert ids(query(dataset, TableFilters(view="either", special=mode))) == expected


def test_decimal_bounds_are_exact_inclusive_and_floor_is_not_silently_lowered(dataset):
    assert ids(query(dataset, TableFilters(view="either", maximum_acres=Decimal(10)))) == ["0001"]
    assert ids(
        query(
            dataset,
            TableFilters(
                view="either",
                minimum_acres=Decimal("10.0000000000000001"),
                maximum_acres=Decimal("10.0000000000000001"),
            ),
        )
    ) == ["0005"]
    with pytest.raises(ValueError, match="loaded candidate floor"):
        query(dataset, TableFilters(minimum_acres=Decimal("9.99")))
    with pytest.raises(ValueError, match="Maximum"):
        query(dataset, TableFilters(maximum_acres=Decimal(9)))


def test_search_is_literal_case_insensitive_and_class_unknown_can_be_selected(dataset):
    assert ids(query(dataset, TableFilters(view="either", search=" EXAMPLE "))) == [
        "0001",
        "0003",
        "0004",
        "0005",
        "0006",
    ]
    assert ids(query(dataset, TableFilters(view="either", search="0002"))) == ["0002"]
    assert not ids(query(dataset, TableFilters(view="either", search=".*")))
    assert ids(query(dataset, TableFilters(view="either", classifications=(None,)))) == ["0002"]
    assert ids(query(dataset, TableFilters(view="either", classifications=("Other",)))) == [
        "0001",
        "0006",
    ]


@pytest.mark.parametrize(
    "descending,expected",
    [
        (False, ["0001", "0006", "0004", "0005", "0003", "0002"]),
        (True, ["0003", "0004", "0005", "0001", "0006", "0002"]),
    ],
)
def test_numeric_sort_not_lexical_nulls_last_and_id_ties_ascending(dataset, descending, expected):
    result = query(
        dataset, TableFilters(view="either", sort="improvement_value", descending=descending)
    )
    assert ids(result) == expected
    assert result.filtered[-1].improvement_value is None


def test_pagination_and_selection_keep_full_identity_across_sort_and_page(dataset):
    first = query(dataset, TableFilters(view="either"), page=1, page_size=2)
    assert [row.parcel_id for row in first.rows] == ["0001", "0002"]
    identity = select_parcel(dataset, first, "0002")
    changed = query(
        dataset,
        TableFilters(view="either", sort="deeded_acres", descending=True),
        page=2,
        page_size=2,
    )
    assert selected_row(dataset, changed, identity).parcel_id == "0002"
    assert identity.county == "Isanti" and identity.snapshot_token == "review/saved"
    assert selected_row(dataset, changed, replace(identity, snapshot_token="review/other")) is None
    assert selected_row(dataset, changed, replace(identity, completion_sha256="b" * 64)) is None
    hidden = query(dataset, TableFilters(view="either", improvement="zero"))
    assert selected_row(dataset, hidden, identity) is None
    with pytest.raises(ValueError):
        select_parcel(dataset, hidden, "0002")
    clamped = query(dataset, TableFilters(view="either"), page=99, page_size=2)
    assert clamped.page == clamped.pages == 3
    assert [row.parcel_id for row in clamped.rows] == ["0005", "0006"]


def test_projection_allowlist_immutable_no_raw_money_or_paths_and_no_silent_fact_conflicts():
    source = record()
    source.update(
        original_row={"TOTAMT": "99999"}, local_path="secret", total_taxes_and_penalties_due=None
    )
    row = project_rows([source], [], Decimal(10))[0]
    assert "secret" not in repr(row) and "99999" not in repr(row)
    assert row.improvement_value == 0
    with pytest.raises(FrozenInstanceError):
        row.parcel_id = "changed"
    with pytest.raises(ValueError, match="Conflicting"):
        project_rows([source], [record(improvement="1")], Decimal(10))
    with pytest.raises(ValueError, match="Duplicate"):
        project_rows([source, source], [], Decimal(10))
    assert not project_rows([record(acres="9")], [], Decimal(10))


@pytest.mark.parametrize(
    "values",
    [
        {"view": "fake"},
        {"sort": "debt"},
        {"improvement": "fake"},
        {"special": "fake"},
        {"minimum_acres": "NaN"},
        {"maximum_acres": "Infinity"},
        {"descending": 1},
        {"search": "x" * 201},
    ],
)
def test_invalid_filters_rejected_server_side(dataset, values):
    with pytest.raises(ValueError):
        query(dataset, TableFilters(**values))


@pytest.mark.parametrize("page,size", [(0, 25), (True, 25), (1, 0), (1, 101), (1, True)])
def test_invalid_pagination_rejected(dataset, page, size):
    with pytest.raises(ValueError):
        query(dataset, TableFilters(), page=page, page_size=size)


def test_decimal_parser_preserves_unknown_and_rejects_binary_floats():
    assert number(None) is None
    assert number("0") == Decimal(0)
    with pytest.raises(TypeError):
        number(0.1)


def test_search_recognizes_county_id_separators_without_changing_display_identity(dataset):
    row = replace(dataset.rows[0], parcel_id="02.001.0200")
    dataset = replace(dataset, rows=(row,))
    result = query(dataset, TableFilters(view="either", search="020010200"))
    assert ids(result) == ["02.001.0200"]
    assert ids(query(dataset, TableFilters(view="either", search="02-001 0200"))) == ["02.001.0200"]


def test_large_selector_is_bounded_without_losing_a_filtered_identity(dataset):
    dataset = replace(
        dataset,
        rows=tuple(replace(dataset.rows[0], parcel_id=f"{index:09d}") for index in range(2001)),
    )
    result = query(dataset, TableFilters(view="either"))
    choices = selector_ids(result, "000002000")
    assert len(choices) == 26 and choices[-1] == "000002000"
    assert len(selector_ids(result, "not-present")) == 25
    identity = select_parcel(dataset, result, "000002000")
    assert selected_row(dataset, result, identity) is not None
