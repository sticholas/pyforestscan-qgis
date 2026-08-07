# Sparse Core Mosaicing

CHM finalization accepts only verified `Complete` core rasters. `SkippedOutsidePolygon` and `CompleteNoData` do not require tile files. GDAL builds the global aligned grid with the plan NoData value, leaving missing valid cells as NoData. If every required core is valid NoData, finalization creates an aligned all-NoData raster directly.

The exact polygon mask still runs after mosaicing, preserving irregular boundaries and holes. Only the final verified, masked raster is registered; core rasters remain checkpoint artifacts.
