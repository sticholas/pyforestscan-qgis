# Canopy Height Model (CHM)

When HAG is absent, PBM may prepare it from a compatible DTM, observed class-2 ground, or validated automatic SMRF ground. CHM metadata records HAG method and preparation signature. Vegetation classes 3/4/5 are not required.

For standalone LAS/LAZ without CRS metadata, CHM may run in explicit source-local mode only when PBM verifies an existing normalized-height dimension. Coordinates and resolution remain in source units, no CRS is assigned, and ground normalization is not recalculated or silently substituted. A mismatch between inspected and execution dimensions is reported as `SOURCE_DIMENSION_MISMATCH`.

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
