# Rumple Index

Rumple measures canopy surface area relative to horizontal ground area. A flat surface is near 1; more complex canopy surfaces have higher values.

Selecting **Rumple Index** creates a dimensionless GeoTIFF. PyForestScan-QGIS generates or reuses a compatible CHM automatically, calculates one value for each valid 2x2 CHM surface patch, and writes an area scalar summary beside the raster. Upstream PyForestScan itself returns only the scalar; the raster is a spatial extension using the same triangle mathematics.

Rumple depends on CHM resolution, interpolation, minimum-height masking, and data gaps. NoData means a complete 2x2 surface could not be calculated. Compare rasters only when those settings match.
