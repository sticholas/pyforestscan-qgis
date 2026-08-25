# Product Execution Capabilities

`core/product_capabilities.py` is authoritative for output kind, renderer, HAG need, partition/fast-path support, mosaic and mask semantics, QGIS loading, and validation status.

CHM, canopy cover, DTM, FHD, PAI, point density, voxel statistic, and Rumple are continuous rasters. PAD is a multiband raster with the established 5/3/2 renderer. Rumple depends on CHM, stores patch-centered values, applies the exact polygon mask, and writes a secondary scalar summary. Its one-cell halo is mathematically validated, but durable work-unit execution remains disabled until wired and tested. Legacy CSV records are typed `rumple_summary`, never raster.
