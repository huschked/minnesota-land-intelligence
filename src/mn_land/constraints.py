"""Preliminary mapped-constraint remainder. No network, repairs or legal conclusions."""
from __future__ import annotations

import hashlib
from math import isfinite

import shapely
from shapely.ops import unary_union

from mn_land.geometry import ACRE_M2, GeometryError, digest

POLICY = {
    "version": "mapped-water-sfha-union-remainder-v1",
    "included_dnr_categories": ["vegetated_or_other_wetland", "open_water_wetland",
                                "deepwater", "riverine_mixed"],
    "water_policy": "Deepwater and mixed riverine are separate mapped water constraints, not reclassified wetlands",
    "included_fema_metric": "sfha",
    "floodway": "Already contained in SFHA; never add separately",
    "excluded_fema_metrics": ["annual_chance_0_2pct", "minimal_hazard"],
    "excluded_context": "Availability, panels and revisions are not hazard constraints",
    "formula": "C = parcel intersection union(included DNR categories, SFHA); R = parcel difference C",
    "denominator": "Measured equal-area parcel square metres, never deeded acres",
    "international_acre_m2": ACRE_M2,
    "held_inputs": "Any upstream hold or incomplete coverage gives null combined/remaining metrics",
    "numerical_area_gate": "max(0.01 m2, measured parcel m2 * 1e-6); diagnostic only, no gap filling or clamping",
    "exact_identity": "Topologically equal full-parcel results reuse the original parcel geometry; empty subtraction is identity",
    "interpretation": "Estimated usable acres under this mapped-constraint policy only; not verified upland, dry or legally buildable land",
    "max_parcels": 15,
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise GeometryError(reason)


def shape(value: str):
    require(isinstance(value, str), "Missing constraint/coverage WKB")
    result = shapely.from_wkb(value)
    require(result.is_valid and not result.has_z and not result.has_m
            and isfinite(result.area), "Invalid/nonfinite/dimensional constraint geometry")
    require(result.is_empty or result.geom_type in {
        "Polygon", "MultiPolygon", "LineString", "MultiLineString", "Point", "MultiPoint",
        "GeometryCollection"}, "Unsupported constraint geometry")
    return result


def measure(value, total: float) -> dict:
    return {"m2": value.area, "acres": value.area / ACRE_M2,
            "percent": round(100 * value.area / total, 8), "wkb_hex": value.wkb_hex}


def index(rows: list[dict], identities: set[str], label: str) -> dict[str, dict]:
    require(isinstance(rows, list), f"Malformed {label} observations")
    mapped = {r["parcel_id"]: r for r in rows}
    require(len(mapped) == len(rows) and set(mapped) == identities,
            f"Missing/duplicate/unexpected {label} parcel identities")
    return mapped


def combine(parcels: list[dict], wetlands: list[dict], floods: list[dict]) -> list[dict]:
    """Combine only validated, compatible saved observations in one equal-area CRS.

    The run service enforces completed source graphs, CRS, hashes and source policy
    identity. This pure calculation also enforces row identity, area and coverage
    gates. Held rows retain source diagnostics; fragments never become totals.
    """
    require(1 <= len(parcels) <= POLICY["max_parcels"], "Select 1–15 compatible parcels")
    ids = {p["parcel_id"] for p in parcels}
    require(len(ids) == len(parcels), "Duplicate parcel selection")
    wet, flood = index(wetlands, ids, "wetland"), index(floods, ids, "flood")
    results = []
    for p in parcels:
        parcel = shape(p["analysis_wkb_hex"])
        total = parcel.area
        require(parcel.geom_type in {"Polygon", "MultiPolygon"} and total > 0,
                "Invalid measured parcel polygon")
        require(hashlib.sha256(bytes.fromhex(p["analysis_wkb_hex"])).hexdigest()
                == p["analysis_wkb_sha256"], "Parcel analysis geometry hash differs")
        tolerance = max(0.01, total * 1e-6)
        w, f = wet[p["parcel_id"]], flood[p["parcel_id"]]
        for source in (w, f):
            require(source["parcel_object_id"] == p["object_id"]
                    and source["parcel_measured_m2"] == total,
                    "Source parcel identity/measured area differs")
            require(source["status"] in {"complete", "held"}, "Unknown source status")
        wet_gap = shape(w["uncovered_wkb_hex"])
        flood_gaps = {name: shape(c["uncovered"]["wkb_hex"])
                      for name, c in f["coverage"].items()}
        require(set(flood_gaps) == {"availability", "effective_panels", "zone_geometry", "study_matched"},
                "Missing independent flood coverage checks")
        gaps = {"wetland_project": wet_gap, **flood_gaps}
        for gap in gaps.values():
            require(gap.difference(parcel).area <= tolerance, "Coverage gap outside selected parcel")
        uncovered = unary_union(list(gaps.values()))
        holds = [f"{name}:{reason}" for name, source in (("wetlands", w), ("floods", f))
                 for reason in source["holds"]]
        for name, source in (("wetlands", w), ("floods", f)):
            if source["status"] != "complete":
                holds.append(name + ":upstream_held")
        if not wet_gap.is_empty or w["coverage_status"] != "complete":
            holds.append("wetlands:incomplete_project_coverage")
        if any(not gap.is_empty or f["coverage"][name]["status"] != "complete"
               for name, gap in flood_gaps.items()):
            holds.append("floods:incomplete_independent_coverage")
        row = {
            "parcel_id": p["parcel_id"], "parcel_object_id": p["object_id"],
            "analysis_wkb_sha256": p["analysis_wkb_sha256"],
            "measured_parcel": measure(parcel, total),
            "saved_deeded_acres": p["saved_deeded_acres"],
            "new_parcel_gis_deeded_acres": p["new_gis_deeded_acres"],
            "deeded_discrepancy": p["deeded_discrepancy"],
            "source_observation_sha256": {"wetlands": digest(w), "floods": digest(f)},
            "source_status": {"wetlands": w["status"], "floods": f["status"]},
            "coverage_gaps": {name: measure(gap, total) for name, gap in gaps.items()},
            "combined_evidence_gap": measure(uncovered, total),
            "independently_covered": measure(parcel.difference(uncovered), total),
            "status": "held" if holds else "complete", "holds": sorted(set(holds)),
            "components": None, "shared_water_sfha": None, "combined_constraint": None,
            "estimated_usable": None, "area_reconciliation": None,
            "interpretation": POLICY["interpretation"],
            "warnings": ["Remainder may contain unmapped wetlands/water, flood hazards or other constraints",
                         "No access, terrain, zoning, septic, legal or economic suitability determination",
                         "Zero evidence gap does not override upstream classification/panel/date holds",
                         "Source dates remain independent in pinned observations; this is not a fresh inventory"],
        }
        if not holds:
            components = {name: shape(w["observed_categories"][name]["wkb_hex"])
                          for name in POLICY["included_dnr_categories"]}
            require(f["metrics"]["sfha"] is not None, "Complete flood row lacks SFHA metric")
            sfha = shape(f["metrics"]["sfha"]["wkb_hex"])
            components["sfha"] = sfha
            for value in components.values():
                # Clipping creates analysis copies, not source edits or repairs.
                require(value.difference(parcel).area <= tolerance,
                        "Constraint geometry outside selected parcel")
            components = {name: parcel.intersection(value) for name, value in components.items()}
            water = unary_union([components[name] for name in POLICY["included_dnr_categories"]])
            sfha = components["sfha"]
            shared = water.intersection(sfha)
            union = parcel.intersection(unary_union([water, sfha]))
            # GEOS can reorder a full-parcel ring and shift floating summation by
            # one ULP. Only EXACT topological equality permits the original shape;
            # no distance/area tolerance, snapping or numeric clamping is involved.
            if union.equals(parcel):
                union = parcel
            remainder = parcel if union.is_empty else parcel.difference(union)
            if remainder.equals(parcel):
                remainder = parcel
            partition_residual = total - union.area - remainder.area
            addition_residual = union.area - (water.area + sfha.area - shared.area)
            if (not 0 <= union.area <= total or not 0 <= remainder.area <= total
                or abs(partition_residual) > tolerance or abs(addition_residual) > tolerance):
                row["status"] = "held"
                row["holds"] = ["combined_geometry_area_bounds_or_reconciliation"]
            else:
                row.update(components={k: measure(v, total) for k, v in components.items()},
                           shared_water_sfha=measure(shared, total),
                           combined_constraint=measure(union, total),
                           estimated_usable=measure(remainder, total))
            row["area_reconciliation"] = {"parcel_minus_constraint_minus_remaining_m2": partition_residual,
                "union_minus_inclusion_exclusion_m2": addition_residual,
                "numerical_gate_m2": tolerance, "clamped": False}
        results.append(row)
    return results
