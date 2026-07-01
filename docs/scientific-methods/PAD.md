# Plant Area Density (PAD)

## What It Measures

Vertical plant area distribution as a multi-band GeoTIFF.

## PyForestScan API Used

`assign_voxels`, `calculate_pad`

## Key Parameters

X/Y resolution, `voxel_height`, `beer_lambert_constant`, `drop_ground`.

## When To Use

Use PAD to inspect vertical canopy structure by height bin.

## Output

The plugin writes the output into the active run folder or selected Processing Toolbox output path. Raster outputs are loaded into QGIS when requested; Rumple is written as CSV.

## Quality Checks

PAD bands are height bins; review band count and QGIS band mapping before interpretation.

## Reproducibility

Record the input dataset, CRS, grid or voxel resolution, height thresholds, PyForestScan version, QGIS version, and plugin version when using this product in analysis.
