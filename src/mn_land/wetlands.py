"""Deterministic mapped wetland screening. No legal/remaining-acre inference."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, date, datetime
from itertools import combinations
from math import ceil, isfinite

import shapely
from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import transform, unary_union

from mn_land.geometry import ACRE_M2, GeometryError, digest, polygon
from mn_land.sources.dnr_nwi import INCLUSION_POLICY, category

MAX_VERTICES = 1_000_000


def esri_polygon(shape) -> dict:
    parts = [shape] if isinstance(shape, Polygon) else list(shape.geoms)
    rings = []
    for part in parts:
        part = orient(part, sign=-1)
        rings.append([list(p) for p in part.exterior.coords])
        rings.extend([[list(p) for p in hole.coords] for hole in part.interiors])
    return {"rings": rings}


def query_groups(parcels: list[dict], alignment) -> list[dict]:
    if not 0 < len(parcels) <= 50 or len({r["parcel_id"] for r in parcels}) != len(parcels):
        raise GeometryError("Wetland capture requires 1..50 unique validated parcels")
    windows = []
    for row in parcels:
        shape = shapely.from_wkb(row["analysis_wkb_hex"])
        if shape.is_empty or not shape.is_valid or shape.area <= 0:
            raise GeometryError("Invalid selected parcel analysis shape")
        native = transform(alignment.inverse, shape)
        if not native.is_valid or any(not isfinite(v) for v in native.bounds):
            raise GeometryError("Invalid inverse-aligned query AOI")
        # Window expansion is only query completeness margin, NEVER coverage.
        x1, y1, x2, y2 = native.bounds
        windows.append(box(x1 - 2, y1 - 2, x2 + 2, y2 + 2))
    return [esri_polygon(unary_union(windows[i:i + 4])) for i in range(0, len(windows), 4)]


def project_features(features: list[dict], groups: list[dict], alignment, *, projects=False,
                     inclusion_policy: dict = INCLUSION_POLICY):
    window = unary_union([polygon(g, alignment.engine.policy) for g in groups])
    projected = []
    vertices = 0
    for feature in features:
        # A connected river/project may extend far beyond the selected parcels.
        # Bound and validate that original before clipping the analysis copy;
        # the much smaller local densification/aggregate budgets still apply.
        native = polygon(feature["geometry"], replace(
            alignment.engine.policy, max_vertices=1_000_000, max_rings=10_000))
        if not native.intersects(window):
            raise GeometryError("Source feature lies outside all queried native AOIs")
        local = native.intersection(window)
        label = "project" if projects else category(feature["attributes"], inclusion_policy)
        row = {"object_id": feature["attributes"]["objectid"],
               "native_geometry_canonical_sha256": digest(feature["geometry"]),
               "raw_attributes": feature["attributes"], "category": label}
        if local.area == 0:
            row.update(analysis_wkb_hex=None, status="query_boundary_only")
        else:
            if shapely.get_num_coordinates(local) + ceil(local.length / 10) > 200_000:
                raise GeometryError("Thematic densification vertex budget exceeded")
            dense = shapely.segmentize(local, max_segment_length=10)
            vertices += int(shapely.get_num_coordinates(dense))
            if vertices > MAX_VERTICES:
                raise GeometryError("Aggregate thematic analysis vertex budget exceeded")
            shape = alignment.project(dense)
            # Coarser 20 m conversion bounds nonlinear edge processing error.
            coarse = alignment.project(shapely.segmentize(local, max_segment_length=20))
            convergence = abs(shape.area - coarse.area)
            if convergence > max(0.01, shape.area * 0.000001):
                raise GeometryError("Thematic area convergence check failed")
            row.update(analysis_wkb_hex=shape.wkb_hex, status="validated",
                       analysis_vertices=int(shapely.get_num_coordinates(shape)),
                       area_convergence_m2=convergence)
        projected.append(row)
    return projected


def project_dates(raw: dict, as_of: date) -> dict:
    """Independent dates; raw anomalies/nulls never become capture date."""
    delivery = raw.get("delivery_date")
    normalized = None
    status = "unknown" if delivery is None else "invalid"
    if type(delivery) is int:
        try:
            day = datetime.fromtimestamp(delivery / 1000, UTC).date()
            if date(1900, 1, 1) <= day <= as_of:
                normalized, status = day.isoformat(), "valid"
        except (ValueError, OSError, OverflowError):
            pass
    imagery = raw.get("spring_imagery_year")
    years = None
    if isinstance(imagery, str) and re.fullmatch(r"[0-9]{4}(?:, ?[0-9]{4})*", imagery):
        parsed = sorted(set(map(int, imagery.split(","))))
        if all(1900 <= year <= as_of.year for year in parsed):
            years = parsed
    return {"raw_delivery_date": delivery, "delivery_date": normalized,
            "delivery_date_status": status, "raw_imagery_years": imagery, "imagery_years": years}


def overlap(parcels: list[dict], wetlands: list[dict], projects: list[dict], *, as_of: date) -> list[dict]:
    """Per-category dissolve then clip. Unknown/partial evidence gives null metrics.

    Different-category positive-area overlap is an explicit classification conflict.
    Touching boundaries have zero area, not a positive constraint. A zero overall
    observation requires independent complete project coverage and known classes.
    """
    kinds = [*INCLUSION_POLICY["wetland_numerator"], "deepwater", "riverine_mixed", "unknown"]
    unions = {
        kind: unary_union([shapely.from_wkb(r["analysis_wkb_hex"]) for r in wetlands
                           if r["category"] == kind and r["analysis_wkb_hex"] is not None])
        for kind in kinds
    }
    project_shapes = [(r, shapely.from_wkb(r["analysis_wkb_hex"])) for r in projects
                      if r["analysis_wkb_hex"] is not None]
    coverage = unary_union([shape for _, shape in project_shapes])
    results = []
    for row in parcels:
        parcel = shapely.from_wkb(row["analysis_wkb_hex"])
        total = parcel.area
        if not parcel.is_valid or parcel.is_empty or not isfinite(total) or total <= 0:
            raise GeometryError("Invalid parcel for wetland calculation")
        clipped = {kind: parcel.intersection(shape) for kind, shape in unions.items()}
        covered = parcel.intersection(coverage)
        uncovered = parcel.difference(coverage)
        coverage_status = "complete" if uncovered.is_empty else (
            "missing" if covered.area == 0 else "partial")
        conflict = unary_union([a.intersection(b) for a, b in combinations(clipped.values(), 2)])
        holds = []
        if coverage_status != "complete":
            holds.append("project_inventory_coverage_" + coverage_status)
        if clipped["unknown"].area > 0:
            holds.append("unknown_or_inconsistent_source_classification")
        if conflict.area > 0:
            holds.append("overlapping_different_source_categories")
        included = unary_union([clipped[k] for k in INCLUSION_POLICY["wetland_numerator"]])
        all_mapped = unary_union(list(clipped.values()))
        if included.area > total + 1e-7 or all_mapped.area > total + 1e-7:
            raise GeometryError("Clipped mapped area exceeds measured parcel area")
        contexts = []
        for source, shape in project_shapes:
            section = parcel.intersection(shape)
            if section.area > 0:
                raw = source["raw_attributes"]
                contexts.append({"project_object_id": source["object_id"],
                                 "project_area": raw.get("project_area"),
                                 "project_area_name": raw.get("project_area_name"),
                                 "project_partner": raw.get("project_partner"),
                                 "intersected_m2": section.area,
                                 "intersection_wkb_hex": section.wkb_hex,
                                 **project_dates(raw, as_of)})
        contributors = []
        for source in wetlands:
            if source["analysis_wkb_hex"] is None:
                continue
            section = parcel.intersection(shapely.from_wkb(source["analysis_wkb_hex"]))
            if not section.is_empty:
                contributors.append({"object_id": source["object_id"], "category": source["category"],
                                     "intersected_m2_before_dissolve": section.area,
                                     "boundary_only": section.area == 0})
        results.append({
            "parcel_id": row["parcel_id"], "parcel_object_id": row["object_id"],
            "parcel_measured_m2": total, "parcel_measured_acres": total / ACRE_M2,
            "saved_deeded_acres": row["saved_deeded_acres"],
            "new_parcel_gis_deeded_acres": row["new_gis_deeded_acres"],
            "deeded_discrepancy": row["deeded_discrepancy"],
            "coverage_status": coverage_status, "covered_m2": covered.area,
            "uncovered_m2": uncovered.area, "uncovered_wkb_hex": uncovered.wkb_hex,
            "project_contexts": contexts,
            "project_date_note": "spatial project context; no single imagery date inferred",
            "status": "held" if holds else "complete", "holds": holds,
            "mapped_wetland_m2": None if holds else included.area,
            "mapped_wetland_acres": None if holds else included.area / ACRE_M2,
            "mapped_wetland_percent": None if holds else round(100 * included.area / total, 8),
            "mapped_wetland_wkb_hex": None if holds else included.wkb_hex,
            "mapped_water_and_wetland_m2": None if holds else all_mapped.area,
            "classification_conflict_m2": conflict.area,
            "classification_conflict_wkb_hex": conflict.wkb_hex,
            "observed_categories": {k: {"m2": v.area, "acres": v.area / ACRE_M2,
                                         "wkb_hex": v.wkb_hex} for k, v in clipped.items()},
            "source_contributors": contributors,
            "warnings": ["Mapped inventory only; not a regulatory delineation or dry/buildable land",
                         "Riverine mixes wetlands/deepwater and is excluded from wetland numerator",
                         "Category/observed amounts are not complete totals when status is held"],
        })
    return results
