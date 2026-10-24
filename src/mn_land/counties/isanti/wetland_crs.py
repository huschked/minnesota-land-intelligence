"""Explicit MnDOT county-projection bridge + NOAA Minnesota HARN operation.

No from_crs fallback across the adjusted datum. Projection-only inverse returns
the county's NAD83(1996) geographic angles, checked against published MnDOT pairs.
NWI NAD83(1986) angles receive EPSG:1706's actual grid shift, never relabeling.
"""

from __future__ import annotations

from importlib.resources import files
from math import isfinite
from pathlib import Path

from pyproj import CRS, Transformer, network
from pyproj.enums import TransformDirection
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

from mn_land.counties.isanti.geometry import ANALYSIS, native_crs
from mn_land.geometry import GeometryAnalysis, GeometryError, digest
from mn_land.provenance import sha256_file
from mn_land.runs import read_json

GRID_NAME = "us_noaa_mnhpgn.tif"
GRID_HASH = "e6b5da45fea4fa0f050a5656e34379e81c5175e90bf535b8a8498dbdb1e4554c"
REFERENCE_ROOT = Path(str(files("mn_land").joinpath("resources")))


class WetlandAlignment:
    def __init__(self, reference: Path = REFERENCE_ROOT) -> None:
        grid = reference / GRID_NAME
        if grid.is_symlink() or not grid.is_file() or sha256_file(grid) != GRID_HASH:
            raise GeometryError("Required pinned Minnesota HARN grid missing or changed")
        self.reference = reference
        self.engine = GeometryAnalysis(native_crs({"wkid": 103736}), ANALYSIS)
        self.utm = CRS(26915)
        network.set_network_enabled(False)
        self.utm_angles = Transformer.from_crs(
            self.utm, self.utm.geodetic_crs, always_xy=True, allow_ballpark=False, only_best=True,
        )
        self.laea_angles = Transformer.from_crs(
            self.engine.source.geodetic_crs, self.engine.target,
            always_xy=True, allow_ballpark=False, only_best=True,
        )
        # Explicit regional operation, not a ranking/fallback from TransformerGroup.
        self.template = (
            '+proj=pipeline +step +proj=unitconvert +xy_in=deg +xy_out=rad '
            '+step +proj=hgridshift +grids="{grid}" '
            '+step +proj=unitconvert +xy_in=rad +xy_out=deg'
        )
        # Preserve Windows' native \\?\ extended-path spelling. Converting it
        # to //?/ with as_posix() makes PROJ fail once nested evidence exceeds
        # MAX_PATH. This is the identical hash-verified retained file, not a
        # different grid, search-path fallback, download or transformation.
        self.grid = Transformer.from_pipeline(self.template.format(grid=str(grid)))
        self.controls = read_json(reference / "isanti_alignment_controls.json")
        if digest(self.controls) != "105f11494b3a604e5cc90a6cfff87ff0a80501a55684d01366b5b13bbf21050d":
            raise GeometryError("Reviewed MnDOT control definitions changed")
        self.control_results = self._controls()

    def _controls(self) -> list[dict]:
        def dms(values):
            return values[0] + values[1] / 60 + values[2] / 3600

        results = []
        geod = CRS(4152).get_geod()
        for row in self.controls["controls"]:
            lat = dms(row["nad83_1996_latitude_dms"])
            lon = -dms(row["nad83_1996_west_longitude_dms"])
            x, y = self.engine.geographic.transform(*row["county_1996_feet"], errcheck=True)
            projection_error = geod.inv(x, y, lon, lat)[2]
            x, y = self.grid.transform(
                -dms(row["nad83_1986_west_longitude_dms"]),
                dms(row["nad83_1986_latitude_dms"]), errcheck=True,
            )
            grid_error = geod.inv(x, y, lon, lat)[2]
            if not (isfinite(projection_error) and isfinite(grid_error)) or (
                projection_error > 0.001 or grid_error > 0.25
            ):
                raise GeometryError("Published Isanti projection/HARN control failed")
            results.append({"gsid": row["gsid"], "projection_error_metres": projection_error,
                            "grid_control_error_metres": grid_error})
        if len(results) != 2:
            raise GeometryError("Both reviewed alignment controls required")
        return results

    def evidence(self) -> dict:
        return {
            "policy": "mndot-isanti-1996-epsg1706-v1", "grid": GRID_NAME,
            "grid_sha256": GRID_HASH, "grid_pipeline": self.template,
            "operation": "EPSG:1706 NAD83 to NAD83(HARN) (42), explicit regional choice",
            "operation_stated_accuracy_metres": 0.05,
            "county_bridge": "MnDOT adjusted Lambert inverse -> NAD83(1996) geographic angles",
            "control_results": self.control_results,
            "controls_canonical_sha256": digest(self.controls),
            "dnr_wkt2": self.utm.to_wkt(),
            "utm_projection_pipeline": self.utm_angles.definition,
            "same_native_datum_laea_pipeline": self.laea_angles.definition,
            "analysis": self.engine.evidence(),
            "network_enabled": network.is_network_enabled(),
            "limitations": [
                "Explicit legacy Minnesota grid, not automatically newest/best-ranked operation",
                "0.25 m control gate is not a parcel-specific uncertainty guarantee",
                "No vertical coordinate conversion or inferred parcel epoch",
            ],
        }

    def forward(self, x, y):
        """NWI NAD83 UTM metres -> the pinned native-datum LAEA metres."""
        lon, lat = self.utm_angles.transform(x, y, errcheck=True)
        lon, lat = self.grid.transform(lon, lat, errcheck=True)
        return self.laea_angles.transform(lon, lat, errcheck=True)

    def inverse(self, x, y):
        direction = TransformDirection.INVERSE
        lon, lat = self.laea_angles.transform(x, y, direction=direction, errcheck=True)
        lon, lat = self.grid.transform(lon, lat, direction=direction, errcheck=True)
        return self.utm_angles.transform(lon, lat, direction=direction, errcheck=True)

    def project(self, shape: BaseGeometry) -> BaseGeometry:
        result = transform(self.forward, shape)
        if result.is_empty or not result.is_valid or not isfinite(result.area):
            raise GeometryError("Wetland alignment produced invalid/nonfinite shape")
        back = transform(self.inverse, result)
        if shape.hausdorff_distance(back) > 0.001:
            raise GeometryError("Wetland datum alignment roundtrip exceeds 1 mm numerical gate")
        return result
