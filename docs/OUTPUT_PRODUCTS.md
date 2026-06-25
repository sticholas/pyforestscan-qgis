# Output Products

This document defines the planned output product families. It does not define
final algorithms yet.

## Raster Products

- Canopy Height Model (CHM)
- Plant Area Index (PAI)
- Plant Area Density (PAD)
- Foliage Height Diversity (FHD)
- Canopy cover
- Rumple index
- Structural complexity rasters

## Vector and Table Products

- Polygon summary layers.
- Per-polygon metric tables.
- Batch processing summaries.
- Provenance tables.

## Metadata Expectations

Outputs should preserve or record:

- Input source paths or stable identifiers.
- Coordinate reference system.
- Pixel size or spatial resolution.
- Processing parameters.
- PyForestScan version.
- Plugin version.
- QGIS version.
- Processing timestamp.

## Styling Expectations

Where technically appropriate, outputs should load with documented QGIS styles
that help users inspect results without changing the scientific values.

