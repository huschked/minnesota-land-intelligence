"""Offline spatial source reconciliation, wire capture and genuine pinned runs."""
import json
from copy import deepcopy
from datetime import UTC, datetime
from io import BytesIO
from urllib.parse import parse_qs, urlsplit

import pytest

pytest.importorskip("shapely")
pytest.importorskip("pyproj")
from shapely.geometry import box

from mn_land.cli import build_parser, main
from mn_land.geometry import GeometryError
from mn_land.ingestion.spatial_capture import POLICY, SpatialCapture, SpatialReplay
from mn_land.ingestion.spatial_layers import fetch_polygons
from mn_land.provenance import sha256_file
from mn_land.runs import RunValidationError, read_json, validate_run
from mn_land.sources.dnr_nwi import NWI, PROJECTS
from mn_land.utils.http import ArcGISError, UrllibJsonTransport
from mn_land.wetland_runs import acquire_wetlands
from mn_land.wetlands import esri_polygon


def meta(spec):
    return {"id": spec.layer_id, "name": spec.name, "objectIdField": "objectid",
            "maxRecordCount": 1, "capabilities": "Query,Extract",
            "geometryType": "esriGeometryPolygon", "hasZ": False, "hasM": False,
            "extent": {"spatialReference": {"wkid": 26915}}, "editingInfo": {"lastEditDate": 1},
            "advancedQueryCapabilities": {"supportsPagination": True, "supportsOrderBy": True,
                                          "supportsTrueCurve": True},
            "fields": [{"name": name, "type": kind, "nullable": name != "objectid"}
                       for name, kind in spec.fields]}


def feature(spec, oid=1, shape=None):
    shape = box(480000, 5040000, 480100, 5040100) if shape is None else shape
    attributes = dict.fromkeys(spec.names)
    attributes.update(objectid=oid)
    if spec == NWI:
        attributes.update(attribute="PEM1C", wetland_type="Freshwater Emergent Wetland")
    else:
        attributes.update(project_area="SYNTHETIC", project_area_name="Synthetic test",
                          delivery_date=1369353600000, spring_imagery_year="2010")
    return {"attributes": attributes, "geometry": esri_polygon(shape)}


class Transport:
    def __init__(self, features=None, mutation=None):
        self.features = {NWI.url: [feature(NWI)], PROJECTS.url: [feature(PROJECTS)]} if features is None else features
        self.mutation = mutation
        self.requests = []
        self.calls = {}

    def get_json(self, url, params):
        self.requests.append((url, params))
        layer = url.removesuffix("/query")
        spec = NWI if layer == NWI.url else PROJECTS
        assert layer == spec.url
        key = (url, "metadata" if not url.endswith("/query") else "count" if params.get("returnCountOnly")
               else "ids" if params.get("returnIdsOnly") else "page")
        self.calls[key] = self.calls.get(key, 0) + 1
        rows = self.features[layer]
        if not url.endswith("/query"):
            result = meta(spec)
        elif params.get("returnCountOnly"):
            result = {"count": len(rows)}
        elif params.get("returnIdsOnly"):
            result = {"objectIdFieldName": "objectid", "objectIds": [f["attributes"]["objectid"] for f in rows]}
        else:
            ids = list(map(int, params["objectIds"].split(",")))
            result = {"spatialReference": {"wkid": 26915}, "geometryType": "esriGeometryPolygon",
                      "features": [f for f in rows if f["attributes"]["objectid"] in ids],
                      "exceededTransferLimit": False}
        result = deepcopy(result)
        return self.mutation(self, key, result, params) if self.mutation else result


GROUPS = [esri_polygon(box(479900, 5039900, 480200, 5040200))]


def test_ordered_pages_duplicate_aois_union_exact_oid_membership():
    source = Transport({NWI.url: [feature(NWI), feature(NWI, 2)], PROJECTS.url: []})
    rows, checks = fetch_polygons(source.get_json, NWI, GROUPS * 2)
    assert len(rows) == checks["unique_count"] == 2
    assert checks["aoi_membership"] == [[1, 2], [1, 2]]
    assert checks["transactional_snapshot"] is False
    pages = [p for _, p in source.requests if "outFields" in p]
    assert len(pages) == 2 and all(p["returnTrueCurves"] == "true" for p in pages)
    assert [p["objectIds"] for p in pages] == ["1", "2"]


@pytest.mark.parametrize("change", ["count", "duplicate_ids", "wrong_ids", "transfer_ids", "metadata",
    "edit", "curve_capability", "z", "m", "wkid", "field", "null_geometry", "missing_field",
    "unexpected_oid", "transfer", "empty", "oversized", "quantized", "page_sr", "dimension"])
def test_refuse_source_drift_missing_truncated_unsupported(change):
    def mutation(source, key, result, params):
        call = source.calls[key]
        if key[1] == "metadata":
            if change == "metadata" and call == 2: result["maxRecordCount"] = 2
            if change == "edit" and call == 2: result["editingInfo"]["lastEditDate"] = 2
            if change == "curve_capability": result["advancedQueryCapabilities"]["supportsTrueCurve"] = False
            if change == "z": result["hasZ"] = True
            if change == "m": result["hasM"] = True
            if change == "wkid": result["extent"]["spatialReference"] = {"wkid": 3857}
            if change == "field": result["fields"][1]["type"] = "esriFieldTypeDouble"
        if key[1] == "count" and change == "count" and call == 2: result["count"] = 2
        if key[1] == "ids":
            if change == "duplicate_ids": result["objectIds"] = [1, 1]
            if change == "wrong_ids" and call == 2: result["objectIds"] = [2]
            if change == "transfer_ids": result["exceededTransferLimit"] = True
        if key[1] == "page":
            values = result["features"]
            if change == "null_geometry": values[0]["geometry"] = None
            if change == "missing_field": del values[0]["attributes"]["attribute"]
            if change == "unexpected_oid": values[0]["attributes"]["objectid"] = 100
            if change == "transfer": result["exceededTransferLimit"] = True
            if change == "empty": result["features"] = []
            if change == "oversized": values.append(values[0])
            if change == "quantized": result["transform"] = {}
            if change == "page_sr": result["spatialReference"] = {"wkid": 4269}
            if change == "dimension": result["hasM"] = True
        return result
    with pytest.raises((GeometryError, ArcGISError)):
        fetch_polygons(Transport(mutation=mutation).get_json, NWI, GROUPS)


def test_empty_nwi_reconciles_but_is_not_coverage_proof():
    source = Transport({NWI.url: [], PROJECTS.url: []})
    rows, checks = fetch_polygons(source.get_json, NWI, GROUPS)
    assert rows == [] and checks["unique_count"] == 0
    assert checks["membership_reconciled"]


@pytest.mark.parametrize("retry", [False, True])
def test_wire_capture_replay_and_exact_body_integrity(tmp_path, monkeypatch, retry):
    class Response(BytesIO):
        status = 200
        headers = None
    source = Transport()
    calls = 0
    def opener(request, timeout):
        nonlocal calls
        calls += 1
        if retry and calls == 1:
            failed = Response(b'{}')
            failed.status = 503
            return failed
        url = urlsplit(request.full_url)
        params = {k: v[0] for k, v in parse_qs(url.query).items()}
        return Response(json.dumps(source.get_json(url._replace(query="").geturl(), params)).encode())
    monkeypatch.setattr("mn_land.utils.http.urlopen", opener)
    transport = UrllibJsonTransport(policy=POLICY, sleep=lambda _: None)
    start = datetime.now(UTC).isoformat()
    with SpatialCapture(tmp_path / "capture", transport) as captured:
        expected, checks = fetch_polygons(captured.request, NWI, GROUPS)
    manifest = {"capture_started_at": start, "capture_finished_at": datetime.now(UTC).isoformat(),
                "requests": captured.records, "wire_bytes_retained": True}
    replay = SpatialReplay(captured.path, manifest)
    assert fetch_polygons(replay.request, NWI, GROUPS) == (expected, checks)
    replay.complete()
    (captured.path / "http/attempt_00004.body").write_bytes(b"changed")
    replay = SpatialReplay(captured.path, manifest)
    with pytest.raises(GeometryError, match="budget/hash"):
        fetch_polygons(replay.request, NWI, GROUPS)


def test_byte_budget_split_and_single_oversize_hold():
    source = Transport({NWI.url: [feature(NWI), feature(NWI, 2)], PROJECTS.url: []})
    original = source.get_json
    def sized(url, params):
        result = original(url, params)
        if not url.endswith("/query"): result["maxRecordCount"] = 100
        if "," in params.get("objectIds", ""):
            raise ArcGISError("Response exceeds configured body byte budget")
        return result
    rows, checks = fetch_polygons(sized, NWI, GROUPS)
    assert len(rows) == checks["unique_count"] == 2
    def single_oversize(url, params):
        if "objectIds" in params:
            raise ArcGISError("Response exceeds configured body byte budget")
        return original(url, params)
    with pytest.raises(ArcGISError, match="body byte budget"):
        fetch_polygons(single_oversize, NWI, GROUPS)


def test_capture_aggregate_and_logical_budgets(tmp_path, monkeypatch):
    monkeypatch.setattr("mn_land.ingestion.spatial_capture.MAX_REQUESTS", 1)
    with SpatialCapture(tmp_path / "logical", Transport()) as captured:
        captured.request(NWI.url, {"f": "json"})
        with pytest.raises(GeometryError, match="logical request budget"):
            captured.request(NWI.url, {"f": "json"})
    monkeypatch.setattr("mn_land.ingestion.spatial_capture.MAX_CAPTURE_BYTES", 1)
    with SpatialCapture(tmp_path / "bytes", Transport()) as captured, pytest.raises(
        GeometryError, match="aggregate byte budget",
    ):
        captured.request(NWI.url, {"f": "json"})


@pytest.mark.parametrize("bad", [[], GROUPS * 14])
def test_aoi_budget_refuses_before_network(bad):
    source = Transport()
    with pytest.raises(GeometryError): fetch_polygons(source.get_json, NWI, bad)
    assert not source.requests


def test_genuine_pinned_wetland_publication_held_states_and_tampering(viewer_data, tmp_path):
    # Reuse genuine county-completion fixture builders; no actual county data.
    from test_geometry_acquisition import Transport as ParcelTransport

    from mn_land.counties.isanti.wetland_crs import WetlandAlignment
    from mn_land.geometry_runs import acquire_geometry
    from mn_land.runs import read_artifact_json
    from mn_land.wetlands import query_groups

    root, _, review = viewer_data()
    geometry = acquire_geometry(review, view="prior", output_root=tmp_path / "geometry", transport=ParcelTransport())
    rows = read_artifact_json(validate_run(geometry, "parcel_geometry"), "polygons.json")
    groups = query_groups(rows, WetlandAlignment())
    # Native query envelope contains the selected parcel; complete project coverage.
    from mn_land.counties.isanti.geometry import ANALYSIS
    from mn_land.geometry import polygon
    window = polygon(groups[0], ANALYSIS)
    source = Transport({NWI.url: [feature(NWI, shape=window)], PROJECTS.url: [feature(PROJECTS, shape=window)]})
    baseline = {p.relative_to(root).as_posix(): sha256_file(p) for p in root.rglob("*") if p.is_file()}
    output = acquire_wetlands(geometry, output_root=tmp_path / "wetlands", transport=source)
    validated = validate_run(output, "wetland_analysis")
    assert validated.manifest["summary"]["numeric_results"] == 1
    result = read_json(output / "wetlands.json")[0]
    assert result["mapped_wetland_percent"] == 100
    assert result["project_contexts"][0]["imagery_years"] == [2010]
    assert baseline == {p.relative_to(root).as_posix(): sha256_file(p) for p in root.rglob("*") if p.is_file()}
    assert main(["validate-wetlands", "--snapshot", str(output)]) == 0
    held = acquire_wetlands(geometry, output_root=tmp_path / "wetlands",
                            transport=Transport({NWI.url: [], PROJECTS.url: []}))
    assert validate_run(held, "wetland_analysis").manifest["summary"]["held_results"] == 1
    assert read_json(held / "wetlands.json")[0]["mapped_wetland_acres"] is None
    geometry.rename(geometry.with_name("moved-original-geometry"))
    validate_run(output, "wetland_analysis")
    payload = read_json(output / "wetlands.json")
    payload[0]["mapped_wetland_acres"] = 999
    (output / "wetlands.json").write_text(json.dumps(payload), encoding="utf-8")
    completion = read_json(output / "completion.json")
    entry = next(e for e in completion["artifacts"] if e["path"] == "wetlands.json")
    entry.update(bytes=(output / "wetlands.json").stat().st_size, sha256=sha256_file(output / "wetlands.json"))
    (output / "completion.json").write_text(json.dumps(completion), encoding="utf-8")
    with pytest.raises(RunValidationError) as error:
        validate_run(output, "wetland_analysis")
    assert "does not reproduce" in str(error.value.__cause__)


def test_cli_does_not_default_to_latest():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["analyze-wetlands", "--county", "isanti"])
