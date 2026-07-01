# Canopy Cover

## What It Measures

GEDI-style canopy cover above a height threshold as a single-band GeoTIFF.

## PyForestScan API Used

`calculate_pad`, `calculate_canopy_cover`

## Key Parameters

X/Y resolution, `voxel_height`, `min_height`, `max_height`, `k`, `beer_lambert_constant`, `drop_ground`.

## When To Use

Use Canopy Cover to estimate cover above a defined canopy threshold.

## Output

The plugin writes the output into the active run folder or selected Processing Toolbox output path. Raster outputs are loaded into QGIS when requested; Rumple is written as CSV.

## Quality Checks

Threshold and extinction coefficient choices should be documented for reproducibility.

## Reproducibility

Record the input dataset, CRS, grid or voxel resolution, height thresholds, PyForestScan version, QGIS version, and plugin version when using this product in analysis.
