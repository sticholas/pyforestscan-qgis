# Product Execution Capabilities

`core/product_capabilities.py` is authoritative for output kind, renderer, HAG need, partition/fast-path support, mosaic and mask semantics, QGIS loading, and validation status.

CHM, canopy cover, DTM, FHD, PAI, point density, and voxel statistic are grayscale rasters. PAD is a multiband raster with the established 5/3/2 renderer. Rumple is a localized scalar/table product and must not be treated as a raster mosaic. All current contracts preserve existing algorithms; the metadata prevents planners and Results from guessing.
