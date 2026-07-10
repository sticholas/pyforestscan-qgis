# Rumple Index

Native PyForestScan Rumple is a scalar whole-area value calculated from a CHM:

`calculate_rumple(chm, cell_resolution, min_height=None)`

PyForestScan QGIS preserves that native behavior as a CSV or structured table result. It does not claim that native Rumple is a raster.

## Internal CHM

Users do not need to select CHM as a visible output to calculate Rumple. The adapter calculates a CHM internally using the Rumple CHM parameters. In local QGIS-Python execution, a compatible CHM calculated earlier in the same adapter session can be reused. If no compatible CHM exists, one is generated internally.

The Rumple CSV records whether the CHM was reused or internally generated, the scalar value, grid resolution, minimum height, CRS, and an interpretation note.

## Interpretation

Rumple describes canopy surface complexity over the CHM area being analyzed. It is sensitive to CHM resolution, minimum canopy height, and analysis extent.
