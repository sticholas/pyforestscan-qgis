# Rumple Index

Rumple can reuse or internally calculate a source-local CHM without parsing a CRS. Its `(R-1) x (C-1)` half-cell grid is derived in source coordinates, and both the raster and scalar summary retain explicit source-local provenance without an invented EPSG identifier.

## What It Measures

Whole-area canopy surface complexity as a scalar value.

## PyForestScan API Used

`calculate_chm`, `calculate_rumple`

Native PyForestScan `calculate_rumple(chm, cell_resolution, min_height=None)` returns a single scalar value. The plugin preserves that behavior.

## Key Parameters

CHM resolution, interpolation, edge handling, `min_height`.

## Internal CHM

Users do not need to select CHM as an output to calculate Rumple. The plugin builds a CHM internally using the Rumple CHM parameters. In local adapter execution, a compatible CHM produced earlier in the same session can be reused; otherwise the CHM is internally generated. Supporting CHM is not saved unless a future explicit option enables it.

## Output

Rumple writes a CSV/table summary, not a raster. The CSV includes the scalar value, CHM/source note, resolution, minimum height, CRS, extent, and interpretation note.

## Localized Extension

Localized Rumple Raster is a PyForestScan QGIS extension, not native PyForestScan Rumple. The QGIS-free math core is implemented and tested; full QGIS raster execution remains gated until QA approves window defaults.

## Quality Checks

Rumple is sensitive to CHM resolution, minimum canopy height, analysis extent, and NoData handling. Treat small-area values cautiously.

## Reproducibility

Record the input dataset, CRS, grid resolution, CHM interpolation settings, minimum height, PyForestScan version, QGIS version, and plugin version when using this product in analysis.
# Source-local CRS behavior

Rumple may derive from a compatible source-local CHM without a named CRS. Rumple mathematics is unchanged. The raster and scalar summary retain unresolved/source-local provenance; spatial alignment still requires a resolved CRS.
