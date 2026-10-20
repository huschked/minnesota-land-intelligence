"""Deterministic effective-NFHL overlap and independent evidence/coverage gates."""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from itertools import combinations
from math import ceil, isfinite

import shapely
from shapely.geometry import box
from shapely.ops import transform, unary_union

from mn_land.counties.isanti.flood_crs import FloodAlignment
from mn_land.geometry import ACRE_M2, GeometryError, digest, polygon
from mn_land.sources.fema_nfhl import LAYERS, category, study_id
from mn_land.wetlands import esri_polygon

PROCESSING_POLICY = {
    "version": "fema-effective-dissolve-clip-v1", "selected_parcels": 15,
    "query_margin_degrees": 0.00005, "group_size": 4,
    "native_vertices_per_feature": 1_000_000, "native_rings_per_feature": 10_000,
    "analysis_vertices_per_feature": 200_000, "analysis_vertices_per_layer": 1_000_000,
    "segment_degrees": 0.0001, "coarse_segment_degrees": 0.0002,
    "area_absolute_m2": 0.01, "area_relative": 0.000001,
    "roundtrip_metres": 0.001, "max_distinct_categories": 64,
    "coverage": "exact study-matched availability AND valid effective panels AND zone geometry",
    "date_gate": "1900..capture date; raw null/invalid/future dates never replaced",
    "revision_policy": "spatial context only; never added as hazard geometry or automatic LOMA relief",
    "empty_inventory": "null IDs only with explicit count zero plus independent empty feature page; start/end reconciled",
}


def query_groups(parcels: list[dict], alignment: FloodAlignment) -> list[dict]:
    if not 0 < len(parcels) <= PROCESSING_POLICY["selected_parcels"] or (
        len({r["parcel_id"] for r in parcels}) != len(parcels)
    ):
        raise GeometryError("Flood capture requires 1..15 unique validated parcels")
    windows = []
    for row in parcels:
        shape = shapely.from_wkb(row["analysis_wkb_hex"])
        if shape.is_empty or not shape.is_valid or shape.area <= 0:
            raise GeometryError("Invalid saved parcel analysis polygon")
        native = transform(alignment.inverse, shape)
        if not native.is_valid or any(not isfinite(v) for v in native.bounds):
            raise GeometryError("Invalid FEMA native query AOI")
        x1, y1, x2, y2 = native.bounds
        margin = PROCESSING_POLICY["query_margin_degrees"]
        # Query margin only, NEVER a coverage gap-filling buffer.
        windows.append(box(x1-margin, y1-margin, x2+margin, y2+margin))
    size = PROCESSING_POLICY["group_size"]
    return [esri_polygon(unary_union(windows[i:i+size])) for i in range(0, len(windows), size)]


def project_features(features: list[dict], layer: str, groups: list[dict],
                     alignment: FloodAlignment) -> list[dict]:
    spec = LAYERS[layer]
    window = unary_union([polygon(g, alignment.engine.policy) for g in groups])
    policy = replace(alignment.engine.policy,
        max_vertices=PROCESSING_POLICY["native_vertices_per_feature"],
        max_rings=PROCESSING_POLICY["native_rings_per_feature"])
    rows, count = [], 0
    step = PROCESSING_POLICY["segment_degrees"]
    for feature in features:
        raw = feature["attributes"]
        for field, kind in spec.fields:
            value = raw[field]
            if kind in ("esriFieldTypeString", "esriFieldTypeGlobalID") and (
                value is not None and not isinstance(value, str)
            ):
                raise GeometryError("FEMA text value contradicts field declaration")
        native = polygon(feature["geometry"], policy)
        if not native.intersects(window):
            raise GeometryError("FEMA geometry outside every requested native AOI")
        local = native.intersection(window)
        row = {"layer": layer, "object_id": raw["OBJECTID"], "raw_attributes": raw,
               "native_geometry_canonical_sha256": digest(feature["geometry"])}
        if local.area == 0:
            row.update(analysis_wkb_hex=None, status="query_boundary_only")
        else:
            if shapely.get_num_coordinates(local) + ceil(local.length / step) > (
                PROCESSING_POLICY["analysis_vertices_per_feature"]
            ):
                raise GeometryError("FEMA densification vertex budget exceeded")
            dense = shapely.segmentize(local, max_segment_length=step)
            count += int(shapely.get_num_coordinates(dense))
            if count > PROCESSING_POLICY["analysis_vertices_per_layer"]:
                raise GeometryError("FEMA aggregate analysis vertex budget exceeded")
            projected = alignment.project(dense)
            coarse = alignment.project(shapely.segmentize(local,
                max_segment_length=PROCESSING_POLICY["coarse_segment_degrees"]))
            error = abs(projected.area - coarse.area)
            if error > max(PROCESSING_POLICY["area_absolute_m2"],
                           projected.area * PROCESSING_POLICY["area_relative"]):
                raise GeometryError("FEMA projection area convergence failed")
            row.update(analysis_wkb_hex=projected.wkb_hex, status="validated",
                       analysis_vertices=int(shapely.get_num_coordinates(projected)),
                       area_convergence_m2=error)
        rows.append(row)
    return rows


def date_observation(value: object, as_of: date) -> dict:
    result = {"raw": value, "date": None, "decoded_date": None,
              "status": "unknown" if value is None else "invalid"}
    if type(value) in (int, float):
        try:
            if not isfinite(value) or int(value) != value:
                return result
            day = (datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=value)).date()
            result["decoded_date"] = day.isoformat()
            if day.year < 1900:
                result["status"] = "outside_reviewed_date_range"
            elif day > as_of:
                result["status"] = "future_or_placeholder"
            else:
                result.update(date=day.isoformat(), status="valid")
        except (OverflowError, ValueError):
            pass
    return result


def panel_context(raw: dict, as_of: date) -> dict:
    effective = date_observation(raw.get("EFF_DATE"), as_of)
    panel, identity, scale = raw.get("FIRM_PAN"), study_id(raw.get("DFIRM_ID")), raw.get("SCALE")
    valid_id = bool(identity and isinstance(panel, str) and re.fullmatch(identity+r"[0-9]{4}[A-Z]", panel))
    printed = raw.get("PANEL_TYP") in ("Countywide, Panel Printed", "Community Based, Panel Printed")
    return {"effective_date": effective, "preliminary_date": date_observation(raw.get("PRE_DATE"), as_of),
            "eligible_effective_coverage": valid_id and printed and effective["status"] == "valid",
            "scale_denominator": int(scale) if isinstance(scale, str)
                and re.fullmatch(r"[1-9][0-9]{0,7}", scale) else None}


def measure(shape) -> dict:
    return {"m2": shape.area, "acres": shape.area / ACRE_M2, "wkb_hex": shape.wkb_hex}


def coverage(parcel, shape) -> dict:
    gap = parcel.difference(shape)
    return {"status": "complete" if gap.is_empty else "missing" if parcel.intersection(shape).area == 0
            else "partial", "uncovered": measure(gap)}


def overlap(parcels: list[dict], features: list[dict], studies: list[dict], *, as_of: date) -> list[dict]:
    """Retain exact category tuples, dissolve duplicates, never add LOMR footprints."""
    layers = {name: [(r, shapely.from_wkb(r["analysis_wkb_hex"])) for r in features
        if r["layer"] == name and r["analysis_wkb_hex"] is not None] for name in LAYERS}
    groups = defaultdict(list)
    for r, shape in layers["zones"]:
        raw = r["raw_attributes"]
        key = tuple(raw.get(k) for k in ("FLD_ZONE", "ZONE_SUBTY", "SFHA_TF"))
        if any(value is not None and not isinstance(value, str) for value in key):
            raise GeometryError("Malformed FEMA category tuple")
        groups[key].append(shape)
    if len(groups) > PROCESSING_POLICY["max_distinct_categories"]:
        raise GeometryError("FEMA category inventory exceeds budget")
    category_shapes = {key: unary_union(values) for key, values in groups.items()}
    availability = unary_union([s for _, s in layers["availability"]])
    valid_panels = [(r, s) for r, s in layers["panels"]
        if panel_context(r["raw_attributes"], as_of)["eligible_effective_coverage"]]
    panel_union = unary_union([s for _, s in valid_panels])
    zone_union = unary_union(list(category_shapes.values()))
    ids = sorted({s for r in features for s in [study_id(r["raw_attributes"].get(
        "STUDY_ID" if r["layer"] == "availability" else "DFIRM_ID"))] if s})
    matched = unary_union([
        unary_union([s for r, s in layers["availability"] if r["raw_attributes"].get("STUDY_ID") == identity])
        .intersection(unary_union([s for r, s in valid_panels if r["raw_attributes"].get("DFIRM_ID") == identity]))
        .intersection(unary_union([s for r, s in layers["zones"] if r["raw_attributes"].get("DFIRM_ID") == identity]))
        for identity in ids])
    results = []
    for parcel_row in parcels:
        parcel = shapely.from_wkb(parcel_row["analysis_wkb_hex"])
        if parcel.is_empty or not parcel.is_valid or not isfinite(parcel.area) or parcel.area <= 0:
            raise GeometryError("Invalid parcel for FEMA area calculation")
        holds, warnings = [], []
        checks = {name: coverage(parcel, shape) for name, shape in (
            ("availability", availability), ("effective_panels", panel_union),
            ("zone_geometry", zone_union), ("study_matched", matched))}
        for name, check in checks.items():
            if check["status"] != "complete":
                holds.append(name + "_coverage_" + check["status"])
        clips = {key: parcel.intersection(shape) for key, shape in category_shapes.items()}
        conflict = unary_union([a.intersection(b) for a, b in combinations(clips.values(), 2)])
        if conflict.area > 0:
            holds.append("overlapping_different_fema_categories")
        masks = defaultdict(list)
        category_rows = []
        for key, shape in clips.items():
            raw = dict(zip(("FLD_ZONE", "ZONE_SUBTY", "SFHA_TF"), key))
            label = category(raw)
            masks[label].append(shape)
            category_rows.append({**raw, "classification": label, "observed_overlap": measure(shape)})
            if label == "unknown" and shape.area > 0:
                holds.append("unknown_or_inconsistent_fema_classification")
        contexts, relevant_studies = [], set()
        for layer, values in layers.items():
            for source, shape in values:
                section = parcel.intersection(shape)
                if section.is_empty:
                    continue
                raw = source["raw_attributes"]
                identity = study_id(raw.get("STUDY_ID" if layer == "availability" else "DFIRM_ID"))
                if identity:
                    relevant_studies.add(identity)
                elif section.area > 0:
                    holds.append("invalid_source_study_identity")
                context = {"layer": layer, "object_id": source["object_id"],
                    "raw_attributes": raw, "intersection": measure(section),
                    "boundary_only": section.area == 0}
                if layer == "panels":
                    detail = panel_context(raw, as_of)
                    context.update(detail)
                    if section.area > 0 and not detail["eligible_effective_coverage"]:
                        holds.append("unverified_panel_type_identity_or_effective_date")
                if layer == "revisions":
                    detail = date_observation(raw.get("EFF_DATE"), as_of)
                    context.update(effective_date=detail, used_as_hazard_geometry=False)
                    if section.area > 0 and (raw.get("STATUS") != "Effective" or detail["status"] != "valid"
                        or not isinstance(raw.get("CASE_NO"), str) or not raw["CASE_NO"].strip()):
                        holds.append("unverified_revision_status_identity_or_effective_date")
                contexts.append(context)
        study_contexts = []
        for identity in sorted(relevant_studies):
            selected = [s for s in studies if s.get("DFIRM_ID") == identity]
            if len(selected) != 1:
                holds.append("study_metadata_missing_or_ambiguous")
            for raw in selected:
                index = date_observation(raw.get("INDX_EFFDT"), as_of)
                revision = date_observation(raw.get("DBREV_DT"), as_of)
                study_contexts.append({"raw_attributes": raw, "index_effective_date": index,
                                       "database_revision_date": revision})
                if index["status"] != "valid" or revision["status"] != "valid":
                    warnings.append("Study index/database dates unavailable; not substituted by panel or capture dates")
        sfha = unary_union(masks["sfha_floodway"] + masks["sfha_other"])
        measures = {"sfha": sfha, "floodway": unary_union(masks["sfha_floodway"]),
                    "annual_chance_0_2pct": unary_union(masks["annual_chance_0_2pct"]),
                    "minimal_hazard": unary_union(masks["minimal_hazard"])}
        if any(s.area > parcel.area + 1e-7 for s in measures.values()):
            raise GeometryError("FEMA clipped area exceeds measured parcel")
        held = bool(holds)
        results.append({"parcel_id": parcel_row["parcel_id"], "parcel_object_id": parcel_row["object_id"],
            "parcel_measured_m2": parcel.area, "parcel_measured_acres": parcel.area / ACRE_M2,
            "saved_deeded_acres": parcel_row["saved_deeded_acres"],
            "new_parcel_gis_deeded_acres": parcel_row["new_gis_deeded_acres"],
            "deeded_discrepancy": parcel_row["deeded_discrepancy"],
            "status": "held" if held else "complete", "holds": sorted(set(holds)),
            "coverage": checks, "observed_categories": category_rows,
            "classification_conflict": measure(conflict),
            "metrics": {name: None if held else {**measure(shape),
                "percent": round(100 * shape.area / parcel.area, 8)} for name, shape in measures.items()},
            "source_contexts": contexts, "study_contexts": study_contexts,
            "distinct_revision_cases": sorted({r["raw_attributes"]["CASE_NO"] for r in contexts
                if r["layer"] == "revisions" and isinstance(r["raw_attributes"].get("CASE_NO"), str)}),
            "warnings": sorted(set(warnings)) + [
                "Mapped effective inventory only, not no flood risk or regulatory/insurance/buildability advice",
                "Floodway is a subset of SFHA; revision footprints are context, not added hazard acres",
                "Observed category fragments are not complete totals on held rows",
                "No wetland combination, remaining-acre estimate, score or refreshed tax balance"],
        })
    return results
