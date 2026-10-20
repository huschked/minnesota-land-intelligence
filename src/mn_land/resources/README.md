# Coordinate reference resource

`us_noaa_mnhpgn.tif` is the 9,324-byte NOAA NADCON Minnesota HPGN/HARN grid,
downloaded unchanged from https://cdn.proj.org/us_noaa_mnhpgn.tif on 2026-10-19
(client research date). SHA-256:
`e6b5da45fea4fa0f050a5656e34379e81c5175e90bf535b8a8498dbdb1e4554c`.

The PROJ-data publisher's notice at https://cdn.proj.org/us_noaa_README.txt
identifies these NOAA NAD83 -> HARN/HPGN grids as **Public Domain** and describes
their conversion to GeoTIFF. NOAA source:
https://www.ngs.noaa.gov/PC_PROD/NADCON/NADCON.zip . The grid is a computational
reference, not county parcel or wetland data. EPSG operation 1706 applies it in
Minnesota; this explicit regional selection does not claim automatic newest/best
operation selection or survey accuracy. No optional/null-grid fallback is allowed.

The accompanying JSON contains two manually checked historical MnDOT coordinate
pairs (GSID 12519 and 12549), not observations of their current monument condition.
Sources and PDF hashes are retained in the JSON; original sheets/renderings remain
in ignored dated preparation evidence. They test projection and datum processing,
not the accuracy of a parcel boundary or an on-ground survey.
