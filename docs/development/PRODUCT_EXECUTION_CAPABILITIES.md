# Product Execution Capabilities

Standalone source-local CHM and Rumple are PBM-capable when the execution read contains an existing normalized-height dimension. Other source-local products remain unchanged; polygon processing still requires a resolved CRS.

Phase 30C changes workflow state only. CHM/Rumple dependency reuse, adaptive Rumple mathematics, masking, routing, and output contracts are unchanged. A single LAS request containing CHM and Rumple is normalized through the same immutable Batch launch contract as a multi-file folder request.

`core/product_capabilities.py` is authoritative for output kind, renderer, HAG need, partition/fast-path support, mosaic and mask semantics, QGIS loading, and validation status.

CHM, canopy cover, DTM, FHD, PAI, point density, voxel statistic, and Rumple are continuous rasters. PAD is a multiband raster with the established 5/3/2 renderer. Rumple depends on CHM, stores patch-centered values, applies the exact polygon mask, and writes a secondary scalar summary. Its one-cell halo is mathematically validated, but durable work-unit execution remains disabled until wired and tested. Legacy CSV records are typed `rumple_summary`, never raster.
# Phase 30B Update

Rumple is partitionable through the durable coordinator for EPT/COPC adaptive jobs. Its primary raster, secondary scalar, and supporting CHM roles are explicit. Live large-source equivalence remains an RC validation item.
# Phase 30D prerequisite clarification

CHM and Rumple may execute from usable height-above-ground data without vegetation classes 3/4/5. Unknown CRS is informational for standalone source-coordinate science and blocking only when transformation or polygon alignment requires it.
# Phase 30E CRS capability

Standalone CHM, Rumple, PAD, PAI, FHD, Canopy Cover, Point Density, Voxel Statistic, and DTM calculations are classified as source-local capable when their scientific inputs and source units are valid. Phase 30E production integration enables CHM/Rumple first. Polygon alignment, reprojection, and multi-source mosaicking require a named source CRS.
