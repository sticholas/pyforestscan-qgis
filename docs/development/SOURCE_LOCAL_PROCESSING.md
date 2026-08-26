# Source-Local Processing

Source-local mode represents native X/Y coordinates without geographic authority. It is not an EPSG code and cannot be used for reprojection, polygon alignment, or cross-source mosaicking.

For standalone CHM and Rumple, the adapter reads LAS/LAZ/COPC directly through PDAL without a `spatialreference` override. CHM source-local mode requires an existing usable `HeightAboveGround` dimension; it does not trigger a new Delaunay HAG calculation. Rumple reuses the compatible current CHM where available.

Source-local GeoTIFFs have `crs=None` and tags including `PYFORESTSCAN_SPATIAL_REFERENCE=SOURCE_LOCAL`, `SOURCE_CRS_RESOLVED=false`, source/output CRS status, resolution source, confidence, and transformation flag. QGIS may load the raster in its native coordinate frame but no CRS is silently assigned.
