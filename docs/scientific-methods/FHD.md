# Foliage Height Diversity (FHD)

## What It Measures

Vertical distribution diversity as a single-band GeoTIFF.

## PyForestScan API Used

`assign_voxels`, `calculate_fhd`

## Key Parameters

X/Y resolution, `voxel_height`, `min_height`, `max_height`.

## When To Use

Use FHD to summarize vertical canopy distribution complexity.

## Output

The plugin writes the output into the active run folder or selected Processing Toolbox output path. Raster outputs are loaded into QGIS when requested; Rumple is written as CSV.

## Quality Checks

Low point density or missing height support can make diversity values unstable.

## Reproducibility

Record the input dataset, CRS, grid or voxel resolution, height thresholds, PyForestScan version, QGIS version, and plugin version when using this product in analysis.
