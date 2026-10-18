"""Contextual canonical JSON and presentation-only CSV protection."""

import csv
import io
import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from mn_land.parcel_table import ParcelDataset, TableFilters, project_rows, query, select_parcel
from mn_land.review_service import SnapshotKey
from mn_land.worklists import issue_rows, project_worklist, serialize


def record(pin, acres="10", value="0", owner=None):
    return {
        "parcel_id": pin,
        "deeded_acres": acres,
        "improvement_value": value,
        "property_classification": "Other",
        "owner_name": owner,
        "assessment_years": [2024],
        "taxes_payable_years": [2025],
        "delinquency_status": "verified_delinquent",
        "balance_aggregation_status": "not_aggregated",
        "delinquency_source_records": [{"source_row_number": 2, "source_metadata": {}}],
        "delinquent_tax_amount": None,
        "penalty_amount": None,
        "total_taxes_and_penalties_due": None,
    }


@pytest.fixture
def inputs():
    prior = [record("0001", "10.0000000000000001", "0", "Owner"), record("0002", "20", None)]
    current = [{**prior[0], "assessment_years": [2025], "taxes_payable_years": [2026]}]
    overview = SimpleNamespace(
        key=SnapshotKey("review", "saved"), completion_sha256="a" * 64, holds=(), warnings=()
    )
    return {
        "dataset": ParcelDataset(overview, Decimal(10), project_rows(prior, current, Decimal(10))),
        "filters": TableFilters(view="either", sort="improvement_value", descending=True),
        "prior": prior,
        "current": current,
        "issues": [
            {
                "kind": "unmatched",
                "artifact": "issues.csv",
                "record_ordinal": 1,
                "fields": {"id": "9999", "owner": "=1+1"},
            }
        ],
        "context": {"snapshot": "review/saved", "listing_publication_date": None},
        "checked_at": datetime(2026, 10, 17, tzinfo=UTC),
    }


def test_distinct_all_pages_decimal_nulls_context_periods_and_immutability(inputs):
    inputs["prior"][0]["penalty_amount"] = "0"
    preview = project_worklist(**inputs)
    data = json.loads(serialize(preview, "json"))
    assert [row["parcel_id"] for row in data["candidates"]] == ["0001", "0002"]
    assert data["candidates"][0]["deeded_acres"] == "10.0000000000000001"
    assert data["candidates"][0]["improvement_value"] == "0"
    assert data["candidates"][1]["improvement_value"] is None
    assert data["candidates"][0]["prior_year"]["total_taxes_and_penalties_due"] is None
    assert data["candidates"][0]["prior_year"]["penalty_amount"] == "0"
    assert data["candidates"][0]["current_year"]["taxes_payable_years"] == [2026]
    assert data["context"]["filters"]["sort"] == "improvement_value"
    assert data["context"]["issue_scope"].startswith("whole")
    assert data["context"]["listing_publication_date"] is None
    assert preview.fingerprint == project_worklist(**inputs).fingerprint
    assert serialize(preview, "csv") == serialize(preview, "csv")
    with pytest.raises(FrozenInstanceError):
        preview.scope = "selected"
    data["candidates"].clear()
    assert len(preview.payload()["candidates"]) == 2


@pytest.mark.parametrize(
    "text",
    [
        "=1+1",
        "+SUM(1)",
        "-1+2",
        "@SUM(A1)",
        "\t=1",
        "\r=1",
        "\n=1",
        "  =1",
        "\x00=1",
        "\ufeff=1",
        "＝1",
        "＋1",
        "－1",
        "＠1",
        'x",=1;\n=2',
        "'already",
        "000001",
    ],
)
def test_every_csv_text_cell_protected_while_json_and_inputs_remain_exact(inputs, text):
    inputs["prior"][0]["owner_name"] = text
    inputs["current"][0]["owner_name"] = text
    inputs["dataset"] = replace(
        inputs["dataset"], rows=project_rows(inputs["prior"], inputs["current"], Decimal(10))
    )
    preview = project_worklist(**inputs)
    assert json.loads(serialize(preview, "json"))["candidates"][0]["GIS_owner_text"] == text
    parsed = list(csv.DictReader(io.StringIO(serialize(preview, "csv").decode("utf-8-sig"))))
    assert parsed[0]["GIS_owner_text"] == "'" + text
    assert all(
        value == "UNKNOWN" or value.startswith("'") for row in parsed for value in row.values()
    )
    assert inputs["prior"][0]["owner_name"] == text
    assert json.loads(parsed[0]["candidate_json"][1:])["GIS_owner_text"] == text


def test_selected_filtered_empty_and_held_do_not_hide_global_issues(inputs):
    dataset = inputs["dataset"]
    identity = select_parcel(dataset, query(dataset, inputs["filters"]), "0002")
    selected = project_worklist(**inputs, scope="selected", identity=identity).payload()
    assert [row["parcel_id"] for row in selected["candidates"]] == ["0002"]
    assert len(selected["issues"]) == 1
    inputs["filters"] = TableFilters(search="no match", view="either")
    with pytest.raises(ValueError):
        project_worklist(**inputs, scope="selected", identity=identity)
    empty = project_worklist(**inputs).payload()
    assert not empty["candidates"] and len(empty["issues"]) == 1
    dataset.overview.holds = ("hold",)
    inputs["dataset"] = replace(dataset, rows=())
    assert not project_worklist(**inputs).payload()["candidates"]
    inputs["dataset"] = dataset
    inputs["filters"] = TableFilters(view="either")
    with pytest.raises(ValueError, match="Held"):
        project_worklist(**inputs)


def test_empty_csv_still_has_context_and_output_budgets_fail_closed(inputs, monkeypatch):
    from mn_land import worklists

    inputs["filters"] = TableFilters(search="none")
    inputs["issues"] = []
    preview = project_worklist(**inputs)
    rows = list(csv.DictReader(io.StringIO(serialize(preview, "csv").decode("utf-8-sig"))))
    assert rows[0]["record_type"] == "'context_only"
    assert json.loads(rows[0]["context_json"][1:])["candidate_count"] == 0
    monkeypatch.setattr(worklists, "MAX_OUTPUT_BYTES", 1)
    for format in ("json", "csv"):
        with pytest.raises(ValueError):
            serialize(preview, format)
    with pytest.raises(ValueError):
        serialize(preview, "html")
    monkeypatch.setattr(worklists, "MAX_ROWS", 0)
    inputs["filters"] = TableFilters(view="either")
    with pytest.raises(ValueError):
        project_worklist(**inputs)


@pytest.mark.parametrize(
    "body,expected",
    [
        (b"a,a\nx,y\n", 1),
        (b"b\nx\n", 1),
        (b"a\nx,y\n", 1),
        (b"a,b\nx\n", 1),
        (b"a\nx\n", 2),
        (b"a\nx\n", -1),
    ],
)
def test_malformed_missing_duplicate_or_miscounted_issue_tables_fail(body, expected):
    with pytest.raises(ValueError):
        issue_rows(body, ("a",), expected)


def test_issue_fields_are_allowlisted_and_empty_stays_unknown():
    assert issue_rows(b"", ("a",), 0) == []
    assert issue_rows(b"a,PRIVATE\n,secret\n", ("a",), 1) == [{"a": None}]


def test_worklist_is_not_limited_to_the_visible_page_and_issues_sort_stably(inputs):
    records = [record(f"{index:04}", str(index + 10)) for index in range(35)]
    inputs["prior"] = records
    inputs["current"] = []
    inputs["dataset"] = replace(inputs["dataset"], rows=project_rows(records, [], Decimal(10)))
    inputs["filters"] = TableFilters(view="prior", sort="deeded_acres", descending=True)
    inputs["issues"] *= 2
    data = project_worklist(**inputs).payload()
    assert len(query(inputs["dataset"], inputs["filters"]).rows) == 25
    assert len(data["candidates"]) == 35
    assert data["candidates"][0]["parcel_id"] == "0034"
    assert len(data["issues"]) == 2  # issue overlap retained, not silently deduplicated
