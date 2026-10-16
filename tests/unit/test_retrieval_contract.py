"""H01-H05: synthetic source inventories and capability/completeness failures."""

import json
from copy import deepcopy
from datetime import UTC, datetime

import pytest

from mn_land.config.retrieval import RetrievalPolicy
from mn_land.config.settings import Settings
from mn_land.counties.isanti import IsantiAdapter
from mn_land.ingestion.arcgis import ArcGISClient
from mn_land.utils.http import ArcGISError


def source_metadata():
    return {
        "id": 0,
        "name": "Synthetic",
        "objectIdField": "OID",
        "capabilities": "Query",
        "maxRecordCount": 2,
        "advancedQueryCapabilities": {"supportsPagination": True, "supportsOrderBy": True},
        "fields": [{"name": "OID", "type": "esriFieldTypeOID", "nullable": False}],
    }


class Source:
    def __init__(self):
        self.initial_metadata = source_metadata()
        self.final_metadata = None
        self.ids = [1, 2, 3, 4, 5]
        self.final_ids = None
        self.count = 5
        self.final_count = None
        self.pages = None
        self.requests = []
        self.metadata_calls = self.count_calls = self.ids_calls = self.page_calls = 0
        self.ids_payload = None

    def get_json(self, url, params):
        self.requests.append((url, dict(params)))
        if not url.endswith("/query"):
            self.metadata_calls += 1
            return deepcopy(
                self.final_metadata
                if self.metadata_calls > 1 and self.final_metadata is not None
                else self.initial_metadata
            )
        if params.get("returnCountOnly"):
            self.count_calls += 1
            return {
                "count": self.final_count
                if self.count_calls > 1 and self.final_count is not None
                else self.count
            }
        if params.get("returnIdsOnly"):
            self.ids_calls += 1
            return deepcopy(
                self.ids_payload
                if self.ids_payload is not None
                else {
                    "objectIdFieldName": "OID",
                    "objectIds": self.final_ids
                    if self.ids_calls > 1 and self.final_ids is not None
                    else self.ids,
                }
            )
        self.page_calls += 1
        if self.pages is not None:
            return deepcopy(self.pages[self.page_calls - 1])
        offset, size = params["resultOffset"], params["resultRecordCount"]
        return page(*self.ids[offset : offset + size])


def page(*ids, **extra):
    return {"features": [{"attributes": {"OID": oid}} for oid in ids], **extra}


def fetch(tmp_path, source, **kwargs):
    return list(
        ArcGISClient("https://example.test/FeatureServer", 0, transport=source, **kwargs).fetch_all(
            out_fields=("OID",),
            raw_run_dir=tmp_path / "run",
            retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("id", True),
        ("id", 1),
        ("name", ""),
        ("name", None),
        ("objectIdField", None),
        ("objectIdField", "missing"),
        ("maxRecordCount", True),
        ("maxRecordCount", 0),
        ("maxRecordCount", -1),
        ("maxRecordCount", 1.5),
        ("capabilities", "Create"),
        ("advancedQueryCapabilities", {}),
        ("fields", []),
        ("editingInfo", []),
    ],
)
def test_H01_bad_metadata_fails_before_pages(tmp_path, key, value):
    source = Source()
    source.initial_metadata[key] = value
    with pytest.raises(ArcGISError):
        fetch(tmp_path, source)
    assert source.count_calls == source.page_calls == 0
    assert (tmp_path / "run/layer_metadata.json").exists()
    assert not (tmp_path / "run/manifest.json").exists()


@pytest.mark.parametrize("capability", ["supportsPagination", "supportsOrderBy"])
@pytest.mark.parametrize("value", [False, "true", 1, None])
def test_H01_requires_explicit_capability_support(tmp_path, capability, value):
    source = Source()
    source.initial_metadata["advancedQueryCapabilities"][capability] = value
    with pytest.raises(ArcGISError):
        fetch(tmp_path, source)


@pytest.mark.parametrize("count", [True, -1, "5", None, 5.0])
def test_H01_bad_counts_fail(tmp_path, count):
    source = Source()
    source.count = count
    with pytest.raises(ArcGISError):
        fetch(tmp_path, source)
    assert source.page_calls == 0


@pytest.mark.parametrize("page_size", [0, -1, True, 1.5])
def test_H01_bad_page_config(page_size):
    with pytest.raises(ArcGISError):
        ArcGISClient("https://example.test", 0, page_size=page_size)


def test_H01_expected_name_not_guessed(tmp_path):
    with pytest.raises(ArcGISError, match="layer name"):
        fetch(tmp_path, Source(), expected_layer_name="Other")


def test_H01_settings_reach_real_transport():
    settings = Settings(
        timeout_seconds=7,
        max_retries=2,
        page_size=17,
        max_body_bytes=1000,
        min_request_spacing=2,
        max_inventory_ids=23,
    )
    adapter = IsantiAdapter(settings=settings)
    assert adapter.client.page_size == 17
    assert adapter.client.transport.timeout == 7
    assert adapter.client.transport.max_retries == 2
    assert adapter.client.transport.policy == settings.retrieval_policy() == adapter.client.policy
    assert adapter.client.expected_layer_name == "TaxParcels_Public"


@pytest.mark.parametrize("command", ["find-candidates", "validate-source"])
def test_H06_CLI_retrieval_failure_has_clear_error_exit(monkeypatch, caplog, command):
    from mn_land import cli

    def fail(*args, **kwargs):
        raise ArcGISError("Retry later: required wait exceeds retrieval wait budget")

    monkeypatch.setattr(cli, "run_pipeline", fail)
    monkeypatch.setattr(ArcGISClient, "metadata", fail)
    assert cli.main([command, "--county", "isanti"]) == 2
    assert "Retry later" in caplog.text


@pytest.mark.parametrize(
    "advertised,configured,effective,offsets",
    [
        (1, 2, 1, [0, 1, 2, 3, 4]),
        (2, 2, 2, [0, 2, 4]),
        (4, 2, 2, [0, 2, 4]),
    ],
)
def test_H02_page_clamp_and_partial_final(tmp_path, advertised, configured, effective, offsets):
    source = Source()
    source.initial_metadata["maxRecordCount"] = advertised
    assert len(fetch(tmp_path, source, page_size=configured)) == 5
    requests = [params for _, params in source.requests if "resultOffset" in params]
    assert [params["resultOffset"] for params in requests] == offsets
    assert all(
        params["resultRecordCount"] == effective
        and params["returnGeometry"] == "false"
        and params["orderByFields"] == "OID ASC"
        for params in requests
    )
    manifest = json.loads((tmp_path / "run/manifest.json").read_text())
    assert manifest["page_size"] == effective
    assert len(manifest["source_checks"]["observations"]) == len(offsets) + 6


@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        {},
        {"features": None},
        {"features": [None]},
        {"features": [{"attributes": []}]},
        {"features": [{"attributes": {}}]},
        page(None),
        page(True),
        page("1"),
        page(1.0),
        page(1, 1),
        page(6),
        page(2, 1),
        page(1, 2, 3),
    ],
)
def test_H03_invalid_pages_fail_with_retained_evidence(tmp_path, bad):
    source = Source()
    source.pages = [bad]
    with pytest.raises(ArcGISError):
        fetch(tmp_path, source)
    assert (tmp_path / "run/page_00001.json").exists()
    assert (tmp_path / "run/retrieval_failure.json").exists()
    assert not (tmp_path / "run/manifest.json").exists()


@pytest.mark.parametrize(
    "pages",
    [
        [page(1, 2), page(2, 3)],
        [page(2, 3), page(1, 4)],
        [page(1, 2), page()],
        [page(1, exceededTransferLimit=False)],
        [page(1, exceededTransferLimit="true")],
        [page(1, 2), page(3, 4), page(5, exceededTransferLimit=True)],
    ],
)
def test_H03_H04_cross_page_and_transfer_failures(tmp_path, pages):
    source = Source()
    source.pages = pages
    with pytest.raises(ArcGISError):
        fetch(tmp_path, source)


def test_H04_short_nonempty_pages_continue_by_actual_length(tmp_path):
    source = Source()
    source.pages = [
        page(1, exceededTransferLimit=True),
        page(2, 3),
        page(4),
        page(5, exceededTransferLimit=False),
    ]
    assert len(fetch(tmp_path, source)) == 5
    assert [
        params["resultOffset"] for _, params in source.requests if "resultOffset" in params
    ] == [0, 1, 3, 4]


def test_H04_consistent_zero_source_is_explicit_not_payment_evidence(tmp_path):
    source = Source()
    source.count, source.ids = 0, []
    assert fetch(tmp_path, source) == []
    assert (
        source.page_calls == 0
        and source.metadata_calls == source.count_calls == source.ids_calls == 2
    )
    manifest = json.loads((tmp_path / "run/manifest.json").read_text())
    assert "empty source" in manifest["source_checks"]["warnings"][0]


@pytest.mark.parametrize(
    "ids", [[1, 1, 3, 4, 5], [1, 2], [True, 2, 3, 4, 5], ["1", 2, 3, 4, 5], None]
)
def test_H03_bad_inventory(tmp_path, ids):
    source = Source()
    source.ids_payload = {"objectIdFieldName": "OID", "objectIds": ids}
    with pytest.raises(ArcGISError):
        fetch(tmp_path, source)
    assert source.page_calls == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"objectIdFieldName": "Other", "objectIds": [1, 2, 3, 4, 5]},
        {"objectIdFieldName": "OID", "objectIds": [1, 2, 3, 4, 5], "exceededTransferLimit": True},
    ],
)
def test_H04_inventory_identity_and_transfer_limit(tmp_path, payload):
    source = Source()
    source.ids_payload = payload
    with pytest.raises(ArcGISError):
        fetch(tmp_path, source)


def test_H04_inventory_budget(tmp_path):
    with pytest.raises(ArcGISError, match="inventory budget"):
        fetch(tmp_path, Source(), policy=RetrievalPolicy(max_inventory_ids=4))


@pytest.mark.parametrize(
    "change", ["count", "ids", "schema", "capability", "limit", "edit", "alias"]
)
def test_H05_reject_source_changes_even_equal_count_replacement(tmp_path, change):
    source = Source()
    source.final_metadata = deepcopy(source.initial_metadata)
    if change == "count":
        source.final_count, source.final_ids = 4, [1, 2, 3, 4]
    elif change == "ids":
        source.final_ids = [1, 2, 3, 4, 6]
    elif change == "schema":
        source.final_metadata["fields"][0]["nullable"] = True
    elif change == "capability":
        source.final_metadata["advancedQueryCapabilities"]["supportsOrderBy"] = False
    elif change == "limit":
        source.final_metadata["maxRecordCount"] = 3
    elif change == "edit":
        source.final_metadata["editingInfo"] = {"lastEditDate": 123}
    else:
        source.final_metadata["fields"][0]["alias"] = "changed"
    with pytest.raises(ArcGISError):
        fetch(tmp_path, source)
    assert not (tmp_path / "run/manifest.json").exists()


@pytest.mark.parametrize("token", [None, 123])
def test_H05_record_consistency_limits_and_observed_tokens(tmp_path, token):
    source = Source()
    if token is not None:
        source.initial_metadata["editingInfo"] = {"lastEditDate": token}
    fetch(tmp_path, source)
    checks = json.loads((tmp_path / "run/manifest.json").read_text())["source_checks"]
    assert checks["initial_edit_token"] == checks["final_edit_token"] == token
    assert checks["transactional_snapshot"] is False
    assert bool(checks["warnings"]) == (token is None)
    assert checks["initial_fingerprint"] == checks["final_fingerprint"]


def test_H05_unrequested_additions_and_inventory_order_are_not_drift(tmp_path):
    source = Source()
    source.final_metadata = deepcopy(source.initial_metadata)
    source.final_metadata["fields"].append({"name": "EXTRA", "type": "esriFieldTypeString"})
    source.final_ids = list(reversed(source.ids))
    assert len(fetch(tmp_path, source)) == 5
