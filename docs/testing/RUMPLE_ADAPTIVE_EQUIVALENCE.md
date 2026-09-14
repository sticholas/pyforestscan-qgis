# Rumple Adaptive Equivalence

Synthetic tests establish the global `(R-1, C-1)` shape, half-cell transform, one-cell CHM halo derivation, four-boundary and corner ownership, complete area coverage, and no duplicate seam ownership. Streaming scalar totals combine only core patches.

Release-level live equivalence still requires whole-raster and adaptive runs over the same source and polygon, comparing CRS, transform, dimensions, NoData mask, pixel values, scalar, and seam diagnostics at more than one safe work-unit size. Until that live matrix is recorded, coordinator integration is implemented and synthetically validated, not claimed as passed live.
