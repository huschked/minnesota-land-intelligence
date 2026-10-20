"""Synthetic MapServer schemas, exact AOIs/IDs, wire replay and pinned flood runs."""
import json
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from io import BytesIO
from urllib.parse import parse_qs, urlsplit

import pytest

pytest.importorskip("shapely")
pytest.importorskip("pyproj")
from shapely.geometry import box

from mn_land.cli import build_parser, main
from mn_land.counties.isanti.flood_crs import FloodAlignment
from mn_land.flood_runs import acquire_floods, process
from mn_land.floods import query_groups
from mn_land.geometry import GeometryError
from mn_land.ingestion.spatial_capture import POLICY, SpatialCapture, SpatialReplay
from mn_land.ingestion.spatial_layers import fetch_polygons
from mn_land.provenance import sha256_file
from mn_land.runs import RunValidationError, read_artifact_json, read_json, validate_run
from mn_land.sources.fema_nfhl import (
    LAYERS,
    SERVICE,
    STUDIES,
    ZONES,
    fetch_studies,
    map_schema,
    service_contract,
)
from mn_land.utils.http import ArcGISError, UrllibJsonTransport
from mn_land.wetlands import esri_polygon


def metadata(spec):
    # Deliberately absent: objectIdField, nullable, hasZ/hasM, editingInfo.
    # These are real MapServer schema omissions, NOT assumed false declarations.
    result = {"id": spec.layer_id, "name": spec.name,
        "type": "Table" if spec == STUDIES else "Feature Layer",
        "capabilities": "Map,Query,Data", "maxRecordCount": 1,
        "fields": [{"name": n, "type": k} for n, k in spec.fields],
        "advancedQueryCapabilities": {"supportsPagination": True, "supportsOrderBy": True,
                                      "supportsTrueCurve": True}}
    if spec != STUDIES:
        result.update(geometryType="esriGeometryPolygon", extent={"spatialReference": {"wkid": 4269}})
    return result


def service():
    return {"currentVersion": 11.1, "capabilities": "Map,Query,Data",
            "spatialReference": {"wkid": 4269},
            "layers": [{"id": s.layer_id, "name": s.name} for s in LAYERS.values()],
            "tables": [{"id": 41, "name": "Study_Info"}],
            "serviceDescription": "", "description": "", "copyrightText": ""}


def feature(spec, shape=None, *, oid=1, study="27059C"):
    raw = dict.fromkeys(spec.names)
    raw.update(OBJECTID=oid)
    if spec == LAYERS["availability"]: raw.update(STUDY_ID=study)
    else: raw.update(DFIRM_ID=study)
    if spec == ZONES: raw.update(FLD_ZONE="AE", ZONE_SUBTY=None, SFHA_TF="T")
    if spec == LAYERS["panels"]: raw.update(FIRM_PAN=study+"0150D", EFF_DATE=1067990400000,
        SCALE="24000", PANEL_TYP="Countywide, Panel Printed")
    if spec == STUDIES:
        raw.update(INDX_EFFDT=218330035200000, DBREV_DT=None, H_DATUM="NAD83")
        return {"attributes": raw}
    return {"attributes": raw,
            "geometry": esri_polygon(box(-93.31, 45.54, -93.30, 45.55) if shape is None else shape)}


class Transport:
    def __init__(self, rows=None, mutation=None):
        self.specs = {s.url: s for s in [*LAYERS.values(), STUDIES]}
        self.rows = {s.url: ([] if n == "revisions" else [feature(s)])
                     for n, s in LAYERS.items()} if rows is None else rows
        self.rows.setdefault(STUDIES.url, [feature(STUDIES)])
        self.mutation, self.requests, self.calls = mutation, [], Counter()

    def get_json(self, url, params):
        self.requests.append((url, deepcopy(params)))
        base = url.removesuffix("/query")
        kind = "metadata" if not url.endswith("/query") else (
            "count" if params.get("returnCountOnly") else "ids" if params.get("returnIdsOnly") else "page")
        key = (base, kind)
        self.calls[key] += 1
        if url == SERVICE:
            result = service()
        elif kind == "metadata":
            result = metadata(self.specs[base])
        else:
            values = self.rows.get(base, [])
            if base == STUDIES.url and params.get("where") == "1=0":
                values = []
            if kind == "count": result = {"count": len(values)}
            elif kind == "ids": result = {"objectIdFieldName": "OBJECTID",
                "objectIds": [r["attributes"]["OBJECTID"] for r in values]}
            else:
                ids = list(map(int, params["objectIds"].split(","))) if "objectIds" in params else [
                    r["attributes"]["OBJECTID"] for r in values]
                result = {"features": [r for r in values if r["attributes"]["OBJECTID"] in ids],
                          "exceededTransferLimit": False}
                if base != STUDIES.url:
                    result.update(spatialReference={"wkid": 4269}, geometryType="esriGeometryPolygon")
        result = deepcopy(result)
        return self.mutation(self, key, result, params) if self.mutation else result


GROUPS = [esri_polygon(box(-93.32, 45.53, -93.29, 45.56))]


def test_mapserver_metadata_omissions_retained_unknown_and_not_mutated():
    raw = metadata(ZONES)
    before = deepcopy(raw)
    result = map_schema(raw, ZONES)
    assert result["has_z"] is result["has_m"] is None
    assert all(value is None for value in result["nullable_declarations"].values())
    assert result["edit_token"] is None and raw == before
    assert service_contract(service())["source_notices"]["copyrightText"] == ""


@pytest.mark.parametrize("change", ["id", "name", "type", "query", "pagination", "order", "oid",
    "oid_conflict", "duplicate", "field", "nullable", "dimension", "curves", "wkid", "hashed_oid", "source_sr"])
def test_fema_schema_capability_identity_type_dimension_holds(change):
    raw = metadata(ZONES)
    if change == "id": raw["id"] = 27
    if change == "name": raw["name"] = "Preliminary Flood Zones"
    if change == "type": raw["type"] = "Table"
    if change == "query": raw["capabilities"] = "Map"
    if change == "pagination": raw["advancedQueryCapabilities"]["supportsPagination"] = False
    if change == "order": raw["advancedQueryCapabilities"]["supportsOrderBy"] = False
    if change == "oid": raw["fields"][0]["type"] = "esriFieldTypeInteger"
    if change == "oid_conflict": raw["objectIdField"] = "OTHER"
    if change == "hashed_oid": raw["uniqueIdInfo"] = {"OIDFieldContainsHashValue": True}
    if change == "duplicate": raw["fields"].append(raw["fields"][0])
    if change == "field": raw["fields"][1]["type"] = "esriFieldTypeDouble"
    if change == "nullable": raw["fields"][1]["nullable"] = "false"
    if change == "dimension": raw["hasZ"] = True
    if change == "curves": raw["advancedQueryCapabilities"]["supportsTrueCurve"] = False
    if change == "wkid": raw["extent"]["spatialReference"] = {"wkid": 4326}
    if change == "source_sr": raw["sourceSpatialReference"] = {"wkid": 3857}
    with pytest.raises(GeometryError): map_schema(raw, ZONES)


def test_aoi_not_county_where_filter_and_exact_oid_union_pages():
    source = Transport({ZONES.url: [feature(ZONES), feature(ZONES, oid=2, study="27095C")]})
    rows, checks = fetch_polygons(source.get_json, ZONES, GROUPS*2, schema=map_schema)
    assert len(rows) == checks["unique_count"] == 2
    assert checks["aoi_membership"] == [[1, 2], [1, 2]]
    assert all(p["where"] == "1=1" for u, p in source.requests if u.endswith("/query"))
    pages = [p for _, p in source.requests if "outFields" in p]
    assert [p["objectIds"] for p in pages] == ["1", "2"]
    assert all(p["outSR"] == 4269 and p["returnTrueCurves"] == "true" for p in pages)


@pytest.mark.parametrize("change", ["count", "ids", "transfer_ids", "missing", "duplicate",
    "unexpected", "order", "field", "geometry", "transfer_page", "quantized", "page_sr", "edit"])
def test_mapserver_completeness_and_drift_holds(change):
    def mutate(source, key, result, params):
        if key[1] == "metadata":
            result["maxRecordCount"] = 10
            if change == "edit": result["editingInfo"] = {"lastEditDate": source.calls[key]}
        if key[1] == "count" and change == "count" and source.calls[key] == 2: result["count"] = 3
        if key[1] == "ids":
            if change == "ids" and source.calls[key] == 2: result["objectIds"] = [2, 3]
            if change == "transfer_ids": result["exceededTransferLimit"] = True
        if key[1] == "page":
            values = result["features"]
            if change == "missing": result["features"] = values[:1]
            if change == "duplicate": values[1] = values[0]
            if change == "unexpected": values[1]["attributes"]["OBJECTID"] = 3
            if change == "order": result["features"] = list(reversed(values))
            if change == "field": del values[0]["attributes"]["FLD_ZONE"]
            if change == "geometry": values[0]["geometry"] = None
            if change == "transfer_page": result["exceededTransferLimit"] = True
            if change == "quantized": result["transform"] = {}
            if change == "page_sr": result["spatialReference"] = {"wkid": 3857}
        return result
    source = Transport({ZONES.url: [feature(ZONES), feature(ZONES, oid=2)]}, mutation=mutate)
    with pytest.raises((GeometryError, ArcGISError)):
        fetch_polygons(source.get_json, ZONES, GROUPS, schema=map_schema)


@pytest.mark.parametrize("change", ["missing", "order", "identity", "field", "geometry", "transfer", "drift"])
def test_study_table_exact_membership_identity_fields_and_drift(change):
    def mutate(source, key, result, params):
        if key[0] != STUDIES.url: return result
        if key[1] == "metadata": result["maxRecordCount"] = 10
        if key[1] == "ids" and change == "drift" and source.calls[key] == 2: result["objectIds"] = [3, 4]
        if key[1] == "page":
            if change == "missing": result["features"] = result["features"][:1]
            if change == "order": result["features"].reverse()
            if change == "identity": result["features"][0]["attributes"]["DFIRM_ID"] = "27095C"
            if change == "field": del result["features"][0]["attributes"]["INDX_EFFDT"]
            if change == "geometry": result["features"][0]["geometry"] = None
            if change == "transfer": result["exceededTransferLimit"] = True
        return result
    source = Transport({STUDIES.url: [feature(STUDIES), feature(STUDIES, oid=2)]}, mutation=mutate)
    with pytest.raises((GeometryError, ArcGISError)): fetch_studies(source.get_json, ["27059C"])


def test_unsafe_or_oversized_study_selection_precedes_network():
    for ids in (["27059C' OR 1=1"], ["27059C", "27059C"], ["27059C"]*21):
        source = Transport()
        with pytest.raises(GeometryError): fetch_studies(source.get_json, ids)
        assert not source.requests


@pytest.mark.parametrize("bad", [None, "nonempty", "missing", "truncated", "positive_count"])
def test_null_empty_ids_require_zero_count_and_independent_empty_page(bad):
    spec = LAYERS["revisions"]
    def mutate(source, key, result, params):
        if key[1] == "ids":
            result["objectIds"] = None
            if bad == "missing": del result["objectIds"]
        if key[1] == "count" and bad == "positive_count": result["count"] = 1
        if key[1] == "page":
            if bad == "nonempty": result["features"] = [feature(spec)]
            if bad == "truncated": result["exceededTransferLimit"] = True
        return result
    source = Transport({spec.url: []}, mutation=mutate)
    if bad is None:
        rows, checks = fetch_polygons(source.get_json, spec, GROUPS,
                                     schema=map_schema, confirm_null_empty=True)
        assert rows == [] and checks["unique_count"] == 0
        assert source.calls[(spec.url, "page")] == 2  # independent start AND end proof
        assert all(p["outFields"] == "OBJECTID" for _, p in source.requests if "outFields" in p)
        # DNR's default contract was not globally weakened.
        with pytest.raises(ArcGISError): fetch_polygons(source.get_json, spec, GROUPS, schema=map_schema)
    else:
        with pytest.raises((GeometryError, ArcGISError)):
            fetch_polygons(source.get_json, spec, GROUPS, schema=map_schema, confirm_null_empty=True)


def test_null_empty_study_inventory_also_requires_independent_page():
    def mutate(source, key, result, params):
        if key[0] == STUDIES.url and key[1] == "ids": result["objectIds"] = None
        return result
    source = Transport({STUDIES.url: []}, mutate)
    rows, checks = fetch_studies(source.get_json, [])
    assert rows == [] and checks["unique_count"] == 0
    assert source.calls[(STUDIES.url, "page")] == 2


def test_empty_proof_uses_advertised_bounded_cap_not_truncated_one_record_scan():
    spec = LAYERS["revisions"]
    def mutate(source, key, result, params):
        if key[1] == "metadata": result["maxRecordCount"] = 2000
        if key[1] == "ids": result["objectIds"] = None
        if key[1] == "page" and params["resultRecordCount"] == 1:
            result["exceededTransferLimit"] = True
        return result
    source = Transport({spec.url: []}, mutate)
    rows, checks = fetch_polygons(source.get_json, spec, GROUPS,
                                 schema=map_schema, confirm_null_empty=True)
    assert rows == [] and checks["unique_count"] == 0
    assert [p["resultRecordCount"] for _, p in source.requests if "outFields" in p] == [2000, 2000]


def test_fema_wire_capture_replay_and_request_tamper(tmp_path, monkeypatch):
    source = Transport()
    class Response(BytesIO):
        status = 200
        headers = None
    def opener(request, timeout):
        url = urlsplit(request.full_url)
        params = {k: v[0] for k, v in parse_qs(url.query).items()}
        return Response(json.dumps(source.get_json(url._replace(query="").geturl(), params)).encode())
    monkeypatch.setattr("mn_land.utils.http.urlopen", opener)
    started = datetime.now(UTC).isoformat()
    with SpatialCapture(tmp_path / "capture", UrllibJsonTransport(policy=POLICY, sleep=lambda _: None)) as capture:
        expected = fetch_polygons(capture.request, ZONES, GROUPS, schema=map_schema)
    manifest = {"capture_started_at": started, "capture_finished_at": datetime.now(UTC).isoformat(),
                "requests": capture.records, "wire_bytes_retained": True}
    replay = SpatialReplay(capture.path, manifest)
    assert fetch_polygons(replay.request, ZONES, GROUPS, schema=map_schema) == expected
    replay.complete()
    changed = deepcopy(manifest)
    changed["requests"][0]["url"] = SERVICE.replace("NFHL", "Preliminary") + "/28"
    with pytest.raises(GeometryError):
        fetch_polygons(SpatialReplay(capture.path, changed).request, ZONES, GROUPS, schema=map_schema)


def test_full_process_rejects_service_inventory_drift():
    def mutate(source, key, result, params):
        if key[0] == SERVICE and source.calls[key] == 2: result["currentVersion"] = 999
        return result
    from test_floods import parcel
    alignment = FloodAlignment()
    group = query_groups([parcel()], alignment)[0]
    from mn_land.geometry import polygon
    window = polygon(group, alignment.engine.policy)
    source = Transport({s.url: [] if n == "revisions" else [feature(s, window)] for n, s in LAYERS.items()}, mutate)
    with pytest.raises(GeometryError, match="service contract drift"):
        process(source.get_json, [parcel()], alignment, datetime.now(UTC).date())


def test_genuine_flood_publication_offline_replay_held_and_semantic_tamper(viewer_data, tmp_path):
    from test_geometry_acquisition import Transport as ParcelTransport

    from mn_land.geometry import polygon
    from mn_land.geometry_runs import acquire_geometry
    root, _, review = viewer_data()
    geometry = acquire_geometry(review, view="prior", output_root=tmp_path / "geometry", transport=ParcelTransport())
    parcels = read_artifact_json(validate_run(geometry, "parcel_geometry"), "polygons.json")
    alignment = FloodAlignment()
    group = query_groups(parcels, alignment)[0]
    window = polygon(group, alignment.engine.policy)
    source = Transport({s.url: [] if n == "revisions" else [feature(s, window)] for n, s in LAYERS.items()})
    before = {p.relative_to(root).as_posix(): sha256_file(p) for p in root.rglob("*") if p.is_file()}
    output = acquire_floods(geometry, output_root=tmp_path / "floods", transport=source)
    result = validate_run(output, "flood_analysis")
    assert result.manifest["summary"]["positive_mapped_sfha"] == 1
    row = read_json(output / "floods.json")[0]
    assert row["metrics"]["sfha"]["percent"] == 100
    assert row["study_contexts"][0]["index_effective_date"]["date"] is None
    assert main(["validate-floods", "--snapshot", str(output)]) == 0
    assert before == {p.relative_to(root).as_posix(): sha256_file(p) for p in root.rglob("*") if p.is_file()}
    held = acquire_floods(geometry, output_root=tmp_path / "floods",
        transport=Transport({s.url: [] for s in LAYERS.values()}))
    assert validate_run(held, "flood_analysis").manifest["summary"]["held_results"] == 1
    assert read_json(held / "floods.json")[0]["metrics"]["sfha"] is None
    geometry.rename(geometry.with_name("moved-original-geometry"))
    validate_run(output, "flood_analysis")
    payload = read_json(output / "floods.json")
    payload[0]["metrics"]["sfha"]["acres"] = 999
    (output / "floods.json").write_text(json.dumps(payload), encoding="utf-8")
    completion = read_json(output / "completion.json")
    entry = next(e for e in completion["artifacts"] if e["path"] == "floods.json")
    entry.update(bytes=(output / "floods.json").stat().st_size, sha256=sha256_file(output / "floods.json"))
    (output / "completion.json").write_text(json.dumps(completion), encoding="utf-8")
    with pytest.raises(RunValidationError) as exc: validate_run(output, "flood_analysis")
    assert "does not reproduce" in str(exc.value.__cause__)


def test_cli_requires_explicit_geometry_and_rejects_old_incomplete(tmp_path):
    with pytest.raises(SystemExit): build_parser().parse_args(["analyze-floods", "--county", "isanti"])
    assert main(["validate-floods", "--snapshot", str(tmp_path)]) == 2
