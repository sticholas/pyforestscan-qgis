# Plant Area Index (PAI)

## What It Measures

Integrated plant area over a selected height range as a single-band GeoTIFF.

## PyForestScan API Used

`calculate_pad`, `calculate_pai`

## Key Parameters

X/Y resolution, `voxel_height`, `min_height`, `max_height`, `beer_lambert_constant`, `drop_ground`.

## When To Use

Use PAI for area-integrated canopy structure summaries.

## Output

The plugin writes the output into the active run folder or selected Processing Toolbox output path. Raster outputs are loaded into QGIS when requested; Rumple is written as CSV.

## Quality Checks

Confirm the height range and Beer-Lambert settings match the study design.

## Reproducibility

Record the input dataset, CRS, grid or voxel resolution, height thresholds, PyForestScan version, QGIS version, and plugin version when using this product in analysis.
