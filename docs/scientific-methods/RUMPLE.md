# Rumple Index

## What It Measures

Canopy surface complexity as a scalar CSV summary.

## PyForestScan API Used

`calculate_chm`, `calculate_rumple`

## Key Parameters

CHM resolution, interpolation, edge handling, `min_height`.

## When To Use

Use Rumple for whole-dataset canopy surface roughness/complexity.

## Output

The plugin writes the output into the active run folder or selected Processing Toolbox output path. Raster outputs are loaded into QGIS when requested; Rumple is written as CSV.

## Quality Checks

Rumple is a table output in the plugin, not a raster layer.

## Reproducibility

Record the input dataset, CRS, grid or voxel resolution, height thresholds, PyForestScan version, QGIS version, and plugin version when using this product in analysis.
