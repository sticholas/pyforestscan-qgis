# Point Density

## What It Measures

Point count or density per X/Y voxel column as a single-band GeoTIFF.

## PyForestScan API Used

`assign_voxels`, `calculate_point_density`

## Key Parameters

X/Y resolution, `voxel_height`, `per_area`, `cell_area`.

## When To Use

Use Point Density as a QA layer before interpreting structural metrics.

## Output

The plugin writes the output into the active run folder or selected Processing Toolbox output path. Raster outputs are loaded into QGIS when requested; Rumple is written as CSV.

## Quality Checks

If `cell_area` is omitted, the adapter uses X resolution multiplied by Y resolution.

## Reproducibility

Record the input dataset, CRS, grid or voxel resolution, height thresholds, PyForestScan version, QGIS version, and plugin version when using this product in analysis.
