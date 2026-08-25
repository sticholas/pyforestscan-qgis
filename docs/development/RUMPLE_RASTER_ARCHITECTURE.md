# Rumple Raster Architecture

An `R x C` CHM produces an `(R-1) x (C-1)` float Rumple field. For each valid patch, `r=(A_triangle1+A_triangle2)/(dx*dy)`. Invalid patches are NoData. Raster bounds are inset by half a CHM cell on all sides, placing pixel centers at patch centers without stretching.

The default analysis scale is exactly one 2x2 CHM patch. It is not a moving-window visualization. The required work-unit halo is one CHM cell; buffered CHM calculation followed by core extraction makes tiled and whole-array results equivalent. Final polygon masking occurs after surface calculation so boundary context is not removed early.

GeoTIFF tags record method, units, CHM resolution, analysis scale, threshold, valid patch count, and upstream scalar. The renderer is continuous single-band grayscale; values are not classified or altered for display.
# Phase 30B Production Integration

Adaptive execution now derives one global half-cell-inset Rumple grid from the CHM grid, owns patch cells without seam duplication, mosaics verified cores, applies the exact polygon mask using the Rumple transform, and computes the published scalar on final valid support. See [Rumple Adaptive Processing](RUMPLE_ADAPTIVE_PROCESSING.md).
