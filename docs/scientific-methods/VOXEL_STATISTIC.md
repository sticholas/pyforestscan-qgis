# Voxel Statistic

## What It Measures

A selected statistic for a point-cloud dimension as a single-band GeoTIFF.

## PyForestScan API Used

`calculate_voxel_stat`

## Key Parameters

X/Y/Z voxel resolution, `dimension`, `stat`, optional `z_index_range`.

## When To Use

Use Voxel Statistic for expert QA or custom raster summaries of point dimensions.

## Output

The plugin writes the output into the active run folder or selected Processing Toolbox output path. Raster outputs are loaded into QGIS when requested; Rumple is written as CSV.

## Quality Checks

The selected dimension must exist in the dataset; invalid dimensions fail before output creation.

## Reproducibility

Record the input dataset, CRS, grid or voxel resolution, height thresholds, PyForestScan version, QGIS version, and plugin version when using this product in analysis.
