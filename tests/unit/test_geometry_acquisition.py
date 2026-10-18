"""Exact identity, bounded retrieval, immutable completion; all sources synthetic."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

pytest.importorskip("shapely")
pytest.importorskip("pyproj")

from mn_land.cli import build_parser, main
from mn_land.counties.isanti.geometry import (
    FIELDS,
    LAYER,
    MAX_REQUESTS,
    acquire,
    capture,
    schema,
)
from mn_land.geometry import GeometryError
from mn_land.geometry_runs import acquire_geometry, analyze, selection
from mn_land.provenance import sha256_file
from mn_land.runs import RunValidationError, read_json, validate_run
from mn_land.utils.http import ArcGISError

FIXTURE = json.loads((Path(__file__).parents[1] / "fixtures/geometry.json").read_text())


def feature(oid=123, pin="020010200", shift=0):
    geometry = deepcopy(FIXTURE["square"])
    geometry["rings"] = [[[x + shift, y] for x, y in ring] for ring in geometry["rings"]]
    return {"attributes": {"OBJECTID": oid, "PARCELID": pin[:2] + "." + pin[2:5] + "." + pin[5:],
                           "UNFORMATTEDPIN": pin, "DEEDEDACRES": 25.5}, "geometry": geometry}


def metadata():
    return {
        "id": 0, "name": "TaxParcels_Public", "objectIdField": "OBJECTID",
        "capabilities": "Query,Extract", "maxRecordCount": 100,
        "geometryType": "esriGeometryPolygon", "hasZ": False, "hasM": False,
        "extent": {"spatialReference": FIXTURE["spatialReference"]},
        "editingInfo": {"lastEditDate": 123456},
        "advancedQueryCapabilities": {"supportsTrueCurve": True,
                                      "supportsOrderBy": True, "supportsPagination": True},
        "fields": [{"name": name, "nullable": name != "OBJECTID", "type": (
            "esriFieldTypeOID" if name == "OBJECTID" else "esriFieldTypeDouble"
            if name == "DEEDEDACRES" else "esriFieldTypeString")} for name in FIELDS],
    }


class Transport:
    def __init__(self, features=None, mutation=None):
        self.features = [feature()] if features is None else features
        self.mutation = mutation
        self.requests = []
        self.counts = self.ids = self.metadata_calls = 0

    def get_json(self, url, params):
        self.requests.append((url, params))
        if url == LAYER:
            self.metadata_calls += 1
            result = metadata()
        elif params.get("returnCountOnly"):
            self.counts += 1
            result = {"count": len(self.features)}
        elif params.get("returnIdsOnly"):
            self.ids += 1
            result = {"objectIdFieldName": "OBJECTID",
                      "objectIds": [f["attributes"]["OBJECTID"] for f in self.features]}
        else:
            ids = list(map(int, params["objectIds"].split(",")))
            result = {"geometryType": "esriGeometryPolygon",
                      "spatialReference": FIXTURE["spatialReference"],
                      "features": [f for f in self.features if f["attributes"]["OBJECTID"] in ids],
                      "exceededTransferLimit": False}
        if self.mutation:
            result = self.mutation(self, deepcopy(result), params)
        return result


def request(transport):
    return lambda params, query=True: transport.get_json(LAYER + ("/query" if query else ""), params)


def tree(path):
    return {p.relative_to(path).as_posix(): sha256_file(p) for p in path.rglob("*") if p.is_file()}


def test_native_true_curves_exact_batched_identity():
    source = Transport([feature(), feature(456, "020010201", 3000)])
    result, checks = acquire(request(source), ["020010200", "020010201"], batch_size=1)
    assert len(result) == 2 and checks["membership_reconciled"]
    assert source.counts == source.ids == source.metadata_calls == 2
    pages = [params for _, params in source.requests if "outFields" in params]
    assert len(pages) == 2
    for params in pages:
        assert params["returnTrueCurves"] == params["returnZ"] == params["returnM"] == "true"
        assert params["outSR"] == 103736
        assert params["outFields"] == ",".join(FIELDS)
        assert not {"geometryPrecision", "maxAllowableOffset", "quantizationParameters"} & params.keys()
    assert checks["transactional_snapshot"] is False


@pytest.mark.parametrize("change", ["count", "ids", "duplicate_ids", "schema", "edit_token",
    "true_curves", "hasZ", "hasM", "field", "sr", "type", "transfer", "missing", "extra",
    "oid", "pin", "conflict", "numeric_pin", "null_geometry", "missing_field", "page_sr",
    "page_z", "quantized", "unordered", "duplicate_pin", "duplicate_oid", "missing_geometry",
    "malformed_feature", "field_type", "bad_transfer", "max_count", "nonobject",
])
def test_refuse_incomplete_ambiguous_changed_or_unsupported(change):
    def mutate(source, result, params):
        if "outFields" in params:
            values = result["features"]
            if change == "type": result["geometryType"] = "esriGeometryPolyline"
            if change == "transfer": result["exceededTransferLimit"] = True
            if change == "bad_transfer": result["exceededTransferLimit"] = 1
            if change == "missing": result["features"] = values[:-1]
            if change == "extra": values.append(deepcopy(values[0]))
            if change == "oid": values[0]["attributes"]["OBJECTID"] = 99999
            if change == "pin": values[0]["attributes"]["UNFORMATTEDPIN"] = "999999999"
            if change == "conflict": values[0]["attributes"]["PARCELID"] = "99.999.9999"
            if change == "numeric_pin": values[0]["attributes"]["UNFORMATTEDPIN"] = 20010200
            if change == "null_geometry": values[0]["geometry"] = None
            if change == "missing_geometry": del values[0]["geometry"]
            if change == "missing_field": del values[0]["attributes"]["DEEDEDACRES"]
            if change == "page_sr": result["spatialReference"] = {"wkid": 26915}
            if change == "page_z": result["hasZ"] = True
            if change == "quantized": result["transform"] = {}
            if change == "unordered": result["features"] = list(reversed(values))
            if change == "duplicate_pin": values[1]["attributes"].update({
                "UNFORMATTEDPIN": "020010200", "PARCELID": "02.001.0200"})
            if change == "duplicate_oid": values[1]["attributes"]["OBJECTID"] = 123
            if change == "malformed_feature": values[0] = None
        if "count" in result and source.counts == 2 and change == "count": result["count"] = 1
        if "objectIds" in result:
            if source.ids == 2 and change == "ids": result["objectIds"] = [123, 999]
            if change == "duplicate_ids": result["objectIds"] = [123, 123]
        if "fields" in result:
            if source.metadata_calls == 2 and change == "schema": result["maxRecordCount"] = 10
            if source.metadata_calls == 2 and change == "edit_token":
                result["editingInfo"]["lastEditDate"] = 9999
            if change == "true_curves": result["advancedQueryCapabilities"]["supportsTrueCurve"] = False
            if change == "hasZ": result["hasZ"] = True
            if change == "hasM": result["hasM"] = True
            if change == "field": result["objectIdField"] = "OTHER"
            if change == "sr": result["extent"]["spatialReference"] = {"wkid": 4326}
            if change == "field_type": result["fields"][-1]["type"] = "esriFieldTypeString"
            if change == "max_count": result["maxRecordCount"] = 0
        return None if change == "nonobject" else result
    source = Transport([feature(), feature(456, "020010201", 3000)], mutate)
    with pytest.raises((GeometryError, ArcGISError)):
        acquire(request(source), ["020010200", "020010201"])


@pytest.mark.parametrize("pins", [[], ["020010200"] * 2, ["02001020"], [20010200], ["1' OR 1=1"]])
def test_selection_budget_and_query_safety_before_network(pins):
    source = Transport()
    with pytest.raises(GeometryError):
        acquire(request(source), pins)
    assert not source.requests


def test_selected_count_ambiguity_fails_before_fetch():
    source = Transport([feature(), feature(456, "020010200", 3000)])
    with pytest.raises(GeometryError, match="count differs"):
        acquire(request(source), ["020010200"])
    assert len(source.requests) == 2


def test_oversized_batch_split_retains_failed_attempt(tmp_path):
    source = Transport([feature(), feature(456, "020010201", 3000)])
    original = source.get_json

    def sized(url, params):
        if "objectIds" in params and "," in params["objectIds"]:
            raise ArcGISError("Response exceeds configured body byte budget")
        return original(url, params)
    source.get_json = sized
    result, checks, records, wire = capture(tmp_path / "capture", ["020010200", "020010201"], source)
    assert len(result) == checks["count"] == 2
    assert not wire and any(r.get("failure") == "body_budget" for r in records)
    assert (tmp_path / "capture/receipt_004.json").is_file()


def test_single_oversized_polygon_is_not_densified_or_published(tmp_path):
    source = Transport()
    original = source.get_json
    def sized(url, params):
        if "objectIds" in params:
            raise ArcGISError("Response exceeds configured body byte budget")
        return original(url, params)
    source.get_json = sized
    with pytest.raises(ArcGISError):
        capture(tmp_path / "capture", ["020010200"], source)
    assert read_json(tmp_path / "capture/receipt_004.json")["failure"] == "body_budget"


def test_no_edit_token_explicitly_unknown():
    def mutation(source, result, params):
        result.pop("editingInfo", None)
        return result
    _, checks = acquire(request(Transport(mutation=mutation)), ["020010200"])
    assert checks["same_id_consistency"].startswith("UNKNOWN")


def test_complete_graph_pin_dates_reproduction_and_unchanged_old_results(viewer_data, tmp_path):
    root, _, review = viewer_data()
    before = tree(root)
    output = acquire_geometry(review, view="prior", output_root=tmp_path / "geometry", transport=Transport())
    run = validate_run(output, "parcel_geometry")
    assert tree(root) == before
    assert run.manifest["geometry_capture_started"] > "2026-01-01"
    assert run.manifest["wire_bytes_retained"] is False
    assert run.completion["row_counts"] == {"polygons.json": 1}
    assert read_json(output / "selection.json")[0]["saved_deeded_acres"] == "25.5"
    assert read_json(output / "polygons.json")[0]["deeded_discrepancy"] is True
    assert run.source("candidates") != review
    # No original path dependency; the pinned graph is fully contained.
    review.rename(review.with_name("moved-review"))
    validate_run(output, "parcel_geometry")
    assert main(["validate-geometry", "--snapshot", str(output)]) == 0


@pytest.mark.parametrize("shape", ["invalid", "curve", "z", "empty", "nonfinite"])
def test_bad_shape_retains_raw_and_hold_but_no_completion(viewer_data, tmp_path, shape):
    _, _, review = viewer_data()
    record = feature()
    if shape == "invalid": record["geometry"]["rings"][0][1] = [451000, 200000]
    if shape == "curve": record["geometry"] = {"curveRings": [[[0, 0]]]}
    if shape == "z": record["geometry"]["rings"][0][0].append(1)
    if shape == "empty": record["geometry"] = {"rings": []}
    if shape == "nonfinite": record["geometry"]["rings"][0][1][0] = float("inf")
    out = tmp_path / "geometry"
    with pytest.raises((GeometryError, ValueError)):
        acquire_geometry(review, view="prior", output_root=out, transport=Transport([record]))
    run = next(p for p in out.iterdir() if p.is_dir())
    assert (run / "failure.json").is_file()
    assert not (run / "completion.json").exists()
    assert not (out / "latest.json").exists()
    assert (run / "capture/request_004.json").is_file()
    if shape != "nonfinite":
        assert (run / "capture/response_004.json").is_file()
        assert read_json(run / "geometry_hold.json")["area"] is None
    with pytest.raises(RunValidationError):
        validate_run(run, "parcel_geometry")


def test_identical_shapes_across_ids_are_held():
    source = [feature(), feature(456, "020010201")]
    selected = [{"parcel_id": f["attributes"]["UNFORMATTEDPIN"], "saved_deeded_acres": "25.5"}
                for f in source]
    # Change vertex start index: topological equality, not only serialized hash.
    ring = source[1]["geometry"]["rings"][0][:-1]
    source[1]["geometry"]["rings"][0] = ring[1:] + ring[:1] + [ring[1]]
    with pytest.raises(GeometryError, match="Duplicate topological"):
        analyze(source, selected, schema(metadata()))


@pytest.mark.parametrize("held,empty,view", [(True, False, "prior"), (False, True, "prior"),
                                          (False, False, "nonsense")])
def test_held_empty_invalid_view_never_requests(viewer_data, tmp_path, held, empty, view):
    _, _, review = viewer_data(held=held, empty=empty)
    source = Transport()
    with pytest.raises(GeometryError):
        acquire_geometry(review, view=view, output_root=tmp_path / "geometry", transport=source)
    assert not source.requests


def test_request_budget(tmp_path, monkeypatch):
    from mn_land.counties.isanti.geometry import Capture
    monkeypatch.setattr("mn_land.counties.isanti.geometry.MAX_REQUESTS", 1)
    capture = Capture(tmp_path, Transport())
    capture.request({"f": "json"}, query=False)
    with pytest.raises(GeometryError, match="request budget"):
        capture.request({"f": "json"}, query=False)
    assert MAX_REQUESTS == 100


@pytest.mark.parametrize("target", ["polygons.json", "selection.json", "capture/response_004.json",
                                   "inputs/candidates/{review}/summary.json"])
def test_changed_evidence_fails_no_latest_substitution(viewer_data, tmp_path, target):
    _, _, review = viewer_data()
    output = acquire_geometry(review, view="prior", output_root=tmp_path / "geometry", transport=Transport())
    file = output / target.format(review=review.name)
    file.write_bytes(file.read_bytes() + b"changed")
    with pytest.raises(RunValidationError):
        validate_run(output, "parcel_geometry")


@pytest.mark.parametrize("args", [[], ["--snapshot", "x"], ["--snapshot", "x", "--view", "latest"]])
def test_cli_requires_explicit_snapshot_view_and_county(args):
    with pytest.raises(SystemExit):
        build_parser().parse_args(["acquire-geometry", *args])


def test_selection_is_explicit_not_latest(viewer_data, monkeypatch):
    _, _, review = viewer_data()
    def prohibited(*args, **kwargs):
        pytest.fail("Geometry selected latest")
    monkeypatch.setattr("mn_land.runs.select_latest", prohibited)
    assert selection(review, "prior")[0]["parcel_id"] == "020010200"


def test_actual_wire_transport_and_rehashed_semantic_tampering(viewer_data, tmp_path, monkeypatch):
    from io import BytesIO
    from urllib.parse import parse_qs, urlsplit

    from mn_land.counties.isanti.geometry import POLICY
    from mn_land.utils.http import UrllibJsonTransport

    _, _, review = viewer_data()
    source = Transport()

    class Response(BytesIO):
        status = 200
        headers = None

    def opener(request, timeout):
        assert timeout == 30
        url = urlsplit(request.full_url)
        params = {key: values[0] for key, values in parse_qs(url.query).items()}
        return Response(json.dumps(source.get_json(url._replace(query="").geturl(), params)).encode())

    monkeypatch.setattr("mn_land.utils.http.urlopen", opener)
    transport = UrllibJsonTransport(policy=POLICY, sleep=lambda _: None)
    output = acquire_geometry(review, view="prior", output_root=tmp_path / "geometry", transport=transport)
    run = validate_run(output, "parcel_geometry")
    assert run.manifest["wire_bytes_retained"] is True
    assert len(list((output / "capture/http").glob("*.body"))) == 7
    assert transport.attempt_count == 7
    rows = read_json(output / "polygons.json")
    rows[0]["measured_acres"] = 999
    (output / "polygons.json").write_text(json.dumps(rows), encoding="utf-8")
    completion = read_json(output / "completion.json")
    entry = next(e for e in completion["artifacts"] if e["path"] == "polygons.json")
    entry.update(bytes=(output / "polygons.json").stat().st_size,
                 sha256=sha256_file(output / "polygons.json"))
    (output / "completion.json").write_text(json.dumps(completion), encoding="utf-8")
    with pytest.raises(RunValidationError, match="does not reproduce"):
        validate_run(output, "parcel_geometry")


def test_aggregate_capture_budget(tmp_path, monkeypatch):
    monkeypatch.setattr("mn_land.counties.isanti.geometry.MAX_CAPTURE_BYTES", 10)
    with pytest.raises(GeometryError, match="Aggregate retained"):
        capture(tmp_path / "capture", ["020010200"], Transport())


def test_aggregate_analysis_budget(monkeypatch):
    monkeypatch.setattr("mn_land.geometry_runs.MAX_ANALYSIS_VERTICES", 10)
    with pytest.raises(GeometryError, match="Aggregate analysis"):
        analyze([feature()], [{"parcel_id": "020010200", "saved_deeded_acres": "25.5"}],
                schema(metadata()))


def test_output_inside_or_above_candidate_graph_refused(viewer_data):
    _, _, review = viewer_data()
    before = tree(review)
    for output in (review, review / "geometry", review.parent):
        source = Transport()
        with pytest.raises(GeometryError, match="dedicated geometry root"):
            acquire_geometry(review, view="prior", output_root=output, transport=source)
        assert not source.requests
    assert tree(review) == before
