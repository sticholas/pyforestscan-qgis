# Digital Terrain Model (DTM)

## What It Measures

Ground surface elevation as a single-band GeoTIFF.

## PyForestScan API Used

`filter_select_ground`, `generate_dtm`

## Key Parameters

DTM `resolution`, optional ground classification, `nodata`.

## When To Use

Use DTM for terrain inspection and height-normalization support.

## Output

The plugin writes the output into the active run folder or selected Processing Toolbox output path. Raster outputs are loaded into QGIS when requested; Rumple is written as CSV.

## Quality Checks

DTM quality depends on ground classification quality and should be inspected visually.

## Reproducibility

Record the input dataset, CRS, grid or voxel resolution, height thresholds, PyForestScan version, QGIS version, and plugin version when using this product in analysis.
