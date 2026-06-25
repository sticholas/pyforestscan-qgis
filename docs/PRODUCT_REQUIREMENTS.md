# Product Requirements

## Target Users

- Forest ecologists and lidar analysts using QGIS.
- GIS technicians supporting forest inventory workflows.
- Researchers who need reproducible products without writing Python scripts.
- Educators demonstrating lidar-derived canopy structure metrics.

## Initial Product Scope

The first functional releases should focus on a small number of high-confidence
Processing algorithms before expanding to batch and advanced workflows.

## Required Capabilities

- Validate plugin runtime dependencies.
- Expose PyForestScan-backed workflows as QGIS Processing algorithms.
- Accept standard QGIS-compatible input paths and layers.
- Produce documented raster, vector, and tabular outputs.
- Surface clear warnings for unsupported coordinate systems, missing metadata,
  invalid parameters, and dependency problems.
- Record enough metadata for reproducibility.

## Future Product Capabilities

- CHM generation.
- Forest structural metric products.
- Batch processing for multiple lidar tiles.
- Polygon zonal summaries.
- Visualization styles for common output products.
- Export-ready maps and tables.
- Model Builder compatible workflows.

## Quality Requirements

- Deterministic behavior for equivalent inputs and versions.
- Automated tests for validation and algorithm wiring.
- Documentation for every public Processing algorithm.
- Compatibility policy for QGIS and PyForestScan versions.

