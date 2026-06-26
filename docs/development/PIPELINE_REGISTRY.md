# Pipeline Registry

Phase 9A registers placeholder pipelines for the six planned user-facing product
families:

- Canopy Height Model (CHM)
- Plant Area Index (PAI)
- Plant Area Density (PAD)
- Foliage Height Diversity (FHD)
- Canopy Cover
- Rumple Index

The registry maps Product Planner product identifiers to `Pipeline` objects. It
is intentionally plain Python and has no QGIS imports.

## Registered Products

| Product ID | Pipeline ID | Status |
| --- | --- | --- |
| `chm` | `chm-pipeline` | Validation only |
| `pai` | `pai-pipeline` | Validation only |
| `pad` | `pad-pipeline` | Validation only |
| `fhd` | `fhd-pipeline` | Validation only |
| `canopy_cover` | `canopy_cover-pipeline` | Validation only |
| `rumple` | `rumple-pipeline` | Validation only |

## Extension Pattern

Future product work should replace or extend the registered product pipeline
without changing Mission Control or QGIS Processing shells. The expected path is:

1. Add product-specific adapter methods.
2. Add tested pipeline steps that call the adapter.
3. Register those steps for the target product.
4. Keep output naming, events, cancellation, and summaries in the pipeline/job
   framework.

## Non-Goals

The registry does not import PyForestScan, PDAL, rasterio, GDAL, or QGIS. It does
not create rasters or execute scientific calculations.
