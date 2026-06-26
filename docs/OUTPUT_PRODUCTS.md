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

## Phase 5 Planning Outputs

Dataset Explorer produces planning outputs rather than scientific products:

- JSON report: structured dataset metadata, warnings, product feasibility, and
  recommended next actions.
- CSV summary: long-form table intended for quick review in QGIS.
- HTML report: browser-readable inspection report with summary panels,
  classification chart, warnings, supported products, and next actions.

These outputs document whether future products appear feasible. They are not CHM,
PAI, PAD, FHD, canopy cover, rumple, raster, or vector scientific outputs.

## Phase 6 Product Plan Outputs

Product Planner produces planning reports, not scientific products:

- `product_plan.json`: structured processing plan and planned future outputs.
- `product_plan.csv`: tabular version of the plan.
- `product_plan.html`: browser-readable planning report.

The planned product paths in these reports are estimates consumed by Mission
Control processing. The planner itself does not create GeoTIFFs, CSV metric
outputs, or metadata files for scientific products. Implemented processing products currently include CHM, Canopy Cover, PAD, PAI, FHD, and Rumple. Rumple is a scalar CSV summary in PyForestScan 0.4.0 rather than a raster.
