# Rumple Adaptive Processing

The production dependency graph is LiDAR to normalized heights to one shared CHM, then optional published CHM plus Rumple raster and scalar summary. Rumple-only jobs retain CHM as supporting work-unit data and do not publish it.

Each Rumple value uses a 2 by 2 CHM patch, requiring one neighboring CHM cell at work-unit boundaries. A single global Rumple grid is derived from the global CHM grid: dimensions are `(R-1, C-1)`, bounds are inset by half a CHM cell, and resolution is unchanged. Patch ownership uses the lower-left CHM cell, so adjacent cores meet without duplicate or missing seam rows/columns.

For adaptive EPT/COPC work, each unit reads bounded LiDAR once, produces buffered CHM once, extracts any requested CHM core, derives its Rumple core, and checkpoints structured product state and area totals. Verified cores are mosaicked on the global grid and exact polygon masking uses the Rumple transform. The final scalar uses valid final-raster support; work-unit totals remain available for streaming/recovery diagnostics.

Small jobs retain the monolithic fast path. Adaptive selection remains resource-driven rather than based on a fixed polygon-area threshold.
