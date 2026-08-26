# Canopy Height Model (CHM)

## What It Measures

Canopy surface height above ground as a single-band GeoTIFF.

## PyForestScan API Used

`calculate_chm`

## Key Parameters

X/Y resolution, interpolation, `interp_valid_region`, `interp_clean_edges`.

## When To Use

Use CHM to inspect canopy surface height and as an internal prerequisite for Rumple.

## Output

The plugin writes the output into the active run folder or selected Processing Toolbox output path. Raster outputs are loaded into QGIS when requested; Rumple is written as CSV.

## Quality Checks

Check CRS, extent, height range, ground normalization, and interpolation artifacts.

## Reproducibility

Record the input dataset, CRS, grid or voxel resolution, height thresholds, PyForestScan version, QGIS version, and plugin version when using this product in analysis.
# Source-local CRS behavior

CHM mathematics may run in native source X/Y coordinates when valid `HeightAboveGround` already exists. The output remains unassigned and explicitly tagged source-local. Polygon alignment and new HAG normalization still require resolved spatial context.
