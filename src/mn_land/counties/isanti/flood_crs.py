"""Explicit FEMA NAD83 geographic -> Isanti adjusted-datum equal-area bridge."""
from __future__ import annotations

from math import isfinite
from pathlib import Path

import shapely
from pyproj import CRS
from pyproj.enums import TransformDirection
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

from mn_land.counties.isanti.wetland_crs import REFERENCE_ROOT, WetlandAlignment
from mn_land.geometry import GeometryError


class FloodAlignment:
    """Reuse the audited grid/controls, not the DNR UTM input transformation."""

    def __init__(self, reference: Path = REFERENCE_ROOT) -> None:
        self.bridge = WetlandAlignment(reference)
        self.engine = self.bridge.engine
        self.source = CRS(4269)
        self.geod = self.source.get_geod()
        if not self.source.equals(self.bridge.utm.geodetic_crs, ignore_axis_order=True):
            raise GeometryError("FEMA native NAD83 geographic differs from reviewed grid input")

    def forward(self, x, y):
        lon, lat = self.bridge.grid.transform(x, y, errcheck=True)
        return self.bridge.laea_angles.transform(lon, lat, errcheck=True)

    def inverse(self, x, y):
        direction = TransformDirection.INVERSE
        lon, lat = self.bridge.laea_angles.transform(x, y, direction=direction, errcheck=True)
        return self.bridge.grid.transform(lon, lat, direction=direction, errcheck=True)

    def project(self, shape: BaseGeometry) -> BaseGeometry:
        result = transform(self.forward, shape)
        if result.is_empty or not result.is_valid or not isfinite(result.area):
            raise GeometryError("FEMA alignment produced invalid/nonfinite geometry")
        back = transform(self.inverse, result)
        before, after = shapely.get_coordinates(shape), shapely.get_coordinates(back)
        if before.shape != after.shape:
            raise GeometryError("FEMA roundtrip changed vertex correspondence")
        distances = self.geod.inv(before[:, 0], before[:, 1], after[:, 0], after[:, 1])[2]
        if any(not isfinite(d) or abs(d) > 0.001 for d in distances):
            raise GeometryError("FEMA datum roundtrip exceeds 1 mm numerical gate")
        return result

    def evidence(self) -> dict:
        bridge = self.bridge.evidence()
        return {"policy": "fema-nad83-geographic-isanti-epsg1706-v1",
                "source_wkt2": self.source.to_wkt(), "source_axis_order": "longitude,latitude",
                "source_units": "degree; never used directly for area",
                "analysis_units": "metre", "area_units": "square metre",
                "grid": bridge["grid"], "grid_sha256": bridge["grid_sha256"],
                "grid_pipeline": bridge["grid_pipeline"], "operation": bridge["operation"],
                "operation_stated_accuracy_metres": bridge["operation_stated_accuracy_metres"],
                "county_bridge": bridge["county_bridge"],
                "control_results": bridge["control_results"],
                "controls_canonical_sha256": bridge["controls_canonical_sha256"],
                "same_native_datum_laea_pipeline": bridge["same_native_datum_laea_pipeline"],
                "analysis": bridge["analysis"], "network_enabled": bridge["network_enabled"],
                "limitations": bridge["limitations"],
                "input_gate": "native FEMA EPSG:4269 equals the reviewed NAD83 grid input; no UTM stage"}
