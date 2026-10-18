"""Offline polygon validation and same-datum equal-area screening. No repairs.

GIS dependencies are optional: only explicit geometry operations import this module.
Original Esri objects are never mutated. Tolerances concern numerical processing,
not the accuracy of the county's boundaries.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from itertools import pairwise
from math import ceil, hypot, isfinite

import pyproj
import shapely
from pyproj import CRS, Transformer, database, datadir, network
from pyproj.crs import ProjectedCRS
from pyproj.crs.coordinate_operation import LambertAzimuthalEqualAreaConversion
from pyproj.enums import TransformDirection
from pyproj.transformer import TransformerGroup
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import transform
from shapely.validation import explain_validity

ACRE_M2 = 4046.8564224  # international acre; not US-survey-foot squared


class GeometryError(ValueError):
    """Hold: evidence cannot support a validated analysis polygon/area."""


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class AnalysisPolicy:
    latitude: float
    longitude: float
    # A reviewed screening envelope in the source's own geographic datum.
    bounds: tuple[float, float, float, float]
    max_vertices: int = 200_000
    max_rings: int = 1_000
    segment_metres: float = 10.0
    roundtrip_metres: float = 0.001
    area_absolute_m2: float = 0.01
    area_relative: float = 0.000001
    geodesic_relative: float = 0.00001
    deeded_absolute_acres: float = 0.1
    deeded_relative: float = 0.02


def polygon(geometry: object, policy: AnalysisPolicy) -> MultiPolygon:
    """Esri clockwise shells, counterclockwise holes; strict containment/topology.

    A hole belongs to the smallest strictly containing shell. Islands may be
    separate shells inside holes. Intersecting/nested filled shells fail validity.
    No auto-closing, orientation correction, buffer(0), make_valid or snapping.
    """
    if not isinstance(geometry, dict) or set(geometry) - {"rings", "spatialReference"}:
        raise GeometryError("Unsupported geometry (including curves/Z/M); original retained")
    rings = geometry.get("rings")
    if not isinstance(rings, list) or not 0 < len(rings) <= policy.max_rings:
        raise GeometryError("Missing/empty/oversized rings")
    shells, holes = [], []
    total = 0
    for ring in rings:
        if not isinstance(ring, list) or len(ring) < 4 or ring[0] != ring[-1]:
            raise GeometryError("Ring must be explicitly closed with at least four vertices")
        total += len(ring)
        if total > policy.max_vertices:
            raise GeometryError("Native vertex budget exceeded")
        for point in ring:
            if not isinstance(point, list) or len(point) != 2 or any(
                type(v) not in (int, float) or not isfinite(v) for v in point
            ):
                raise GeometryError("Nonfinite, malformed or unsupported-dimensional coordinate")
        shape = Polygon(ring)
        if shape.is_empty or not shape.is_valid or shape.area <= 0:
            raise GeometryError(f"Invalid native ring: {explain_validity(shape)}")
        (holes if shape.exterior.is_ccw else shells).append(shape)
    if not shells:
        raise GeometryError("No clockwise exterior shell; no orientation repair")
    assigned: list[list] = [[] for _ in shells]
    for hole in holes:
        containers = [i for i, shell in enumerate(shells) if shell.contains(hole)]
        if not containers:
            raise GeometryError("Orphan/intersecting hole")
        owner = min(containers, key=lambda i: shells[i].area)
        assigned[owner].append(hole.exterior.coords)
    result = MultiPolygon([
        Polygon(shell.exterior.coords, interiors) for shell, interiors in zip(shells, assigned)
    ])
    if result.is_empty or not result.is_valid or result.area <= 0:
        raise GeometryError(f"Invalid native polygon: {explain_validity(result)}")
    return result


class GeometryAnalysis:
    def __init__(self, source: CRS, policy: AnalysisPolicy) -> None:
        self.policy = policy
        self.source = source
        if not source.is_projected or len(source.axis_info) != 2:
            raise GeometryError("A reviewed two-dimensional projected native CRS is required")
        self.unit = source.axis_info[0].unit_conversion_factor
        if not isfinite(self.unit) or self.unit <= 0 or any(
            axis.unit_conversion_factor != self.unit for axis in source.axis_info
        ):
            raise GeometryError("Unknown/inconsistent native units")
        self.target = ProjectedCRS(
            name="Native-datum local LAEA screening v1",
            geodetic_crs=source.geodetic_crs,
            conversion=LambertAzimuthalEqualAreaConversion(policy.latitude, policy.longitude),
        )
        # Deliberately no network/grid downloads or datum fallback. Same datum
        # means no uncertain cross-datum operation is needed or authorized.
        network.set_network_enabled(False)
        group = TransformerGroup(source, self.target, always_xy=True, allow_ballpark=False)
        if not group.best_available or len(group.transformers) != 1:
            raise GeometryError("Exact unique available same-datum transformation required")
        self.transformer = group.transformers[0]
        if self.transformer.accuracy != 0 or "ballpark" in self.transformer.description.lower():
            raise GeometryError("Unapproved approximate transformation")
        self.geographic = Transformer.from_crs(
            source, source.geodetic_crs, always_xy=True, allow_ballpark=False, only_best=True,
        )
        self.geod = source.get_geod()

    def evidence(self) -> dict:
        from pathlib import Path

        proj_db = Path(datadir.get_data_dir()) / "proj.db"
        return {
            "algorithm": "esri-linear-rings-native-laea-v1",
            "native_wkt2": self.source.to_wkt(), "analysis_wkt2": self.target.to_wkt(),
            "native_units": [axis.unit_name for axis in self.source.axis_info],
            "native_unit_to_metres": self.unit,
            "native_datum": self.source.datum.name,
            "analysis_units": "metre", "area_units": "square metre",
            "acre_m2": ACRE_M2, "axis_order": "always_xy: easting,northing",
            "coordinate_precision": "float64; no snapping or rounding",
            "repair": "unsupported; invalid shapes held, originals retained",
            "policy": json.loads(json.dumps(asdict(self.policy))),
            "pipeline": self.transformer.definition,
            "transform_accuracy_metres": self.transformer.accuracy,
            "grids": [
                {"name": grid.short_name, "available": grid.available}
                for operation in self.transformer.operations for grid in operation.grids
            ],
            "network_enabled": network.is_network_enabled(),
            "shapely": shapely.__version__, "geos": shapely.geos_version_string,
            "pyproj": pyproj.__version__, "proj": pyproj.proj_version_str,
            "proj_database_sha256": hashlib.sha256(proj_db.read_bytes()).hexdigest(),
            "epsg_database_version": database.get_database_metadata("EPSG.VERSION"),
            "esri_database_version": database.get_database_metadata("ESRI.VERSION"),
        }

    def _densify(self, shape: MultiPolygon, step_metres: float) -> MultiPolygon:
        # Count prospective vertices before allocation. Native straight edges are
        # densified ONLY on analysis copies to preserve their projected curves.
        total = 0

        def ring(coords):
            nonlocal total
            pairs = list(coords)
            output = []
            for a, b in pairwise(pairs):
                count = max(1, ceil(hypot(b[0] - a[0], b[1] - a[1]) * self.unit / step_metres))
                total += count
                if total + 1 > self.policy.max_vertices:
                    raise GeometryError("Densified vertex budget exceeded")
                output.extend([
                    (a[0] + (b[0] - a[0]) * i / count, a[1] + (b[1] - a[1]) * i / count)
                    for i in range(count)
                ])
            return output + [pairs[-1]]

        return MultiPolygon([
            Polygon(ring(part.exterior.coords), [ring(h.coords) for h in part.interiors])
            for part in shape.geoms
        ])

    def project(self, geometry: dict, deeded_acres: float | None) -> tuple[dict, MultiPolygon]:
        shape = polygon(geometry, self.policy)
        native = self._densify(shape, self.policy.segment_metres)
        geographic = transform(lambda x, y: self.geographic.transform(x, y, errcheck=True), native)
        west, south, east, north = self.policy.bounds
        x1, y1, x2, y2 = geographic.bounds
        if not (west <= x1 <= x2 <= east and south <= y1 <= y2 <= north):
            raise GeometryError("Coordinates outside reviewed analysis envelope / wrong axis order")
        projected = transform(
            lambda x, y: self.transformer.transform(x, y, errcheck=True), native,
        )
        if not projected.is_valid or projected.is_empty or not isfinite(projected.area):
            raise GeometryError("Invalid/nonfinite transformed polygon")
        coarse = transform(
            lambda x, y: self.transformer.transform(x, y, errcheck=True),
            self._densify(shape, self.policy.segment_metres * 2),
        )
        convergence = abs(projected.area - coarse.area)
        tolerance = max(self.policy.area_absolute_m2, projected.area * self.policy.area_relative)
        if convergence > tolerance:
            raise GeometryError("Area densification convergence failed")
        back = transform(
            lambda x, y: self.transformer.transform(
                x, y, direction=TransformDirection.INVERSE, errcheck=True,
            ), projected,
        )
        roundtrip = native.hausdorff_distance(back) * self.unit
        if not isfinite(roundtrip) or roundtrip > self.policy.roundtrip_metres:
            raise GeometryError("Transform round-trip tolerance failed")
        geodesic = sum(abs(self.geod.geometry_area_perimeter(p)[0]) for p in geographic.geoms)
        if projected.area <= 0 or abs(geodesic - projected.area) > max(
            self.policy.area_absolute_m2, projected.area * self.policy.geodesic_relative,
        ):
            raise GeometryError("Independent ellipsoidal area control failed")
        measured = projected.area / ACRE_M2
        if deeded_acres is not None and (
            type(deeded_acres) not in (float, int) or not isfinite(deeded_acres) or deeded_acres < 0
        ):
            raise GeometryError("Invalid deeded acreage; cannot substitute measured value")
        difference = None if deeded_acres is None else measured - deeded_acres
        discrepancy = None if difference is None else abs(difference) > max(
            self.policy.deeded_absolute_acres, deeded_acres * self.policy.deeded_relative,
        )
        return {
            "native_geometry_sha256": digest(geometry),
            "analysis_wkb_hex": projected.wkb_hex,
            "analysis_wkb_sha256": hashlib.sha256(projected.wkb).hexdigest(),
            "parts": len(shape.geoms), "holes": sum(len(p.interiors) for p in shape.geoms),
            "analysis_vertices": int(shapely.get_num_coordinates(projected)),
            "measured_m2": projected.area, "measured_acres": measured,
            "new_gis_deeded_acres": deeded_acres,
            "difference_acres": difference, "deeded_discrepancy": discrepancy,
            "roundtrip_error_metres": roundtrip, "convergence_m2": convergence,
            "ellipsoidal_control_m2": geodesic,
            "native_valid": True, "analysis_valid": True, "repaired": False,
        }, shape
