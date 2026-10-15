"""F02: source schema gates, row quarantines, and optional missing-value warnings."""

import json
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from mn_land.config.settings import Settings
from mn_land.counties.isanti import IsantiAdapter
from mn_land.counties.isanti.schema import EXPECTED_ALIASES, EXPECTED_TYPES, validate_metadata
from mn_land.delinquency.pipeline import load_parcel_snapshot
from mn_land.ingestion.arcgis import ArcGISClient
from mn_land.ingestion.pipeline import run_pipeline


def metadata() -> dict:
    return {
        "objectIdField": "OBJECTID",
        "fields": [
            {
                "name": name,
                "type": kind,
                "nullable": name != "OBJECTID",
                "alias": EXPECTED_ALIASES[name],
            }
            for name, kind in EXPECTED_TYPES.items()
        ],
    }


def record() -> dict:
    return json.loads(
        (Path(__file__).parents[1] / "fixtures/isanti_parcel.json").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        {},
        {"fields": {}},
        {"fields": [None]},
        {"fields": [{"name": ""}]},
        {"fields": [{"name": True}]},
    ],
)
def test_F02_metadata_structure_is_not_guessed(bad) -> None:
    with pytest.raises(ValueError):
        validate_metadata(bad)


@pytest.mark.parametrize(
    "mutation", ["missing", "renamed", "type", "duplicate", "nullable", "OID_nullable"]
)
def test_F02_mapped_schema_drift_fails(mutation) -> None:
    source = metadata()
    if mutation == "missing":
        source["fields"].pop()
    elif mutation == "renamed":
        source["fields"][-1]["name"] += "_new"
    elif mutation == "type":
        source["fields"][-1]["type"] = "esriFieldTypeInteger"
    elif mutation == "duplicate":
        source["fields"].append(deepcopy(source["fields"][0]))
    elif mutation == "nullable":
        source["fields"][-1]["nullable"] = "true"
    else:
        source["fields"][0]["nullable"] = True
    with pytest.raises(ValueError):
        validate_metadata(source)


def test_F02_added_fields_and_alias_changes_do_not_change_meanings(caplog) -> None:
    source = metadata()
    source["fields"].append({"name": "EXTRA", "type": "esriFieldTypeString"})
    next(field for field in source["fields"] if field["name"] == "TOTPRVTXTOD")["alias"] = (
        "New Alias"
    )
    validate_metadata(source)
    assert "isanti_alias_changed" in caplog.text
    parcel = IsantiAdapter(client=object()).normalize_parcel(record(), datetime.now(UTC))
    assert parcel.past_due_tax_amount is None
    assert parcel.tax_semantics_verified is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("PARCELID", None),
        ("PARCELID", 20010200),
        ("PARCELID", "letters"),
        ("DEEDEDACRES", -1),
        ("DEEDEDACRES", "NaN"),
        ("TOTPRVTXTOD", True),
        ("LNDVALUE", "Infinity"),
        ("OWNERNME1", {}),
        ("PSTLCITY", False),
    ],
)
def test_F02_invalid_nonnull_GIS_values_are_row_errors(field, value) -> None:
    source = record()
    source["attributes"][field] = value
    with pytest.raises(ValueError, match=field):
        IsantiAdapter(client=object()).normalize_parcel(source, datetime.now(UTC))


@pytest.mark.parametrize("source", [None, [], {"attributes": []}])
def test_F02_malformed_features_have_domain_row_errors(source) -> None:
    with pytest.raises(ValueError, match="attributes"):
        IsantiAdapter(client=object()).normalize_parcel(source, datetime.now(UTC))


def test_F02_missing_optional_value_is_unknown_with_a_warning() -> None:
    source = record()
    del source["attributes"]["LNDVALUE"]
    source["attributes"]["IMPRVALUE"] = None
    parcel = IsantiAdapter(client=object()).normalize_parcel(source, datetime.now(UTC))
    assert parcel.land_value is None
    assert parcel.improvement_value is None
    assert parcel.source_metadata.validation_warnings == ("missing optional attribute: LNDVALUE",)


def test_F02_gate_runs_before_queries_and_keeps_metadata_evidence(tmp_path) -> None:
    requests = []

    class Transport:
        def get_json(self, url, params):
            requests.append(url)
            return {"fields": []}

    adapter = IsantiAdapter(client=ArcGISClient("https://example.test", 0, transport=Transport()))
    output = tmp_path / "raw"
    with pytest.raises(ValueError, match="schema"):
        list(adapter.fetch_parcels(output, datetime.now(UTC)))
    assert requests == ["https://example.test/0"]
    assert json.loads((output / "layer_metadata.json").read_text()) == {"fields": []}
    assert not (output / "manifest.json").exists()


def test_F02_live_pipeline_and_offline_loader_retain_quarantine_locations(
    tmp_path, monkeypatch
) -> None:
    from mn_land.ingestion import pipeline

    good = record()
    bad = deepcopy(good)
    bad["attributes"]["OBJECTID"] = 102
    bad["attributes"]["DEEDEDACRES"] = "NaN"

    class Transport:
        def get_json(self, url, params):
            if not url.endswith("/query"):
                return metadata()
            if params.get("returnCountOnly"):
                return {"count": 2}
            return {"features": [good, bad]}

    monkeypatch.setattr(
        pipeline,
        "SETTINGS",
        Settings(
            raw_dir=tmp_path / "raw",
            processed_dir=tmp_path / "processed",
        ),
    )
    adapter = IsantiAdapter(client=ArcGISClient("https://example.test", 0, transport=Transport()))
    stats = run_pipeline(adapter, Decimal(10))
    assert (stats.retrieved, stats.normalized, stats.normalization_errors) == (2, 1, 1)
    diagnostics = json.loads((stats.raw_run_dir / "normalization_diagnostics.json").read_text())
    assert diagnostics[0]["source_record_id"] == 102
    assert diagnostics[0]["field"] == "DEEDEDACRES"
    assert diagnostics[0]["record_number"] == 2
    reloaded = []
    parcels, errors, _ = load_parcel_snapshot(adapter, stats.raw_run_dir, diagnostics=reloaded)
    assert len(parcels) == 1 and errors == 1
    assert reloaded[0]["source_record_id"] == 102
    assert reloaded[0]["feature_number"] == 2
    assert reloaded[0]["raw_page"].endswith("page_00001.json")
