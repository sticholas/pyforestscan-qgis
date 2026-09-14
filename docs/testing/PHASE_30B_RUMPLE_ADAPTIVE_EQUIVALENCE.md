# Phase 30B Rumple Adaptive Equivalence

Adaptive Rumple uses one global aligned CHM grid, a one-cell CHM halo, half-cell Rumple patch centers, non-overlapping core extents, and one final exact polygon mask. This preserves the same 2 x 2 patch-surface definition across work-unit boundaries.

Required equivalence checks cover left/right, top/bottom, four-way corners, NoData boundaries, polygon edges, and single-pass versus adaptive scalar aggregation. Each final Rumple core must match the current source-plan signature, Rumple grid signature, method identifier, and checksum before mosaicking.

The scalar summary is calculated by blockwise accumulation over the final masked raster. Halo pixels therefore cannot be counted twice, and the final scalar describes the same support area as the published GeoTIFF.
