# Raster grid and mosaicing

One `AlignedRasterGrid` owns CRS, resolution, origin, extent, dimensions, NoData, and type. Work-unit extents are integer grid slices, preventing independent rounding gaps or shifts.

CHM reads include a buffer while only core pixels survive. Mosaicing accepts verified cores with matching CRS/resolution, writes transactionally, preserves NoData, then applies the exact polygon mask. Intermediates never enter the final registry.
