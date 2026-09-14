# Rumple Raster Method Review

## Upstream behavior

Current PyForestScan `main` was reviewed on 2026-08-25. `calculate_rumple(chm, cell_resolution, min_height=None)` returns one scalar. It masks CHM cells below `min_height`, requires four finite cells per 2x2 patch, splits each patch into two triangles, sums their 3D areas, and divides by `valid_patch_count * dx * dy`. No valid patch returns NaN. The official guide explicitly calls the result scalar and warns that CHM interpolation can fill gaps while smoothing the surface.

Sources: [PyForestScan source](https://github.com/iosefa/PyForestScan/blob/main/pyforestscan/calculate.py), [official Rumple guide](https://pyforestscan.sefa.ai/usage/forest-structure/rumple/), [Kane et al. 2010](https://doi.org/10.1139/X10-064), and [NEON-SD structural diversity product](https://pmc.ncbi.nlm.nih.gov/articles/PMC11522374/).

## Spatial interpretations

1. **Patch field:** each valid 2x2 CHM patch stores its two-triangle surface area divided by `dx*dy`.
2. **Moving window:** sum patch surface areas inside a neighborhood and divide by valid planar area.
3. **Non-overlapping blocks:** area summaries on an analysis grid.

Literature consistently defines Rumple as canopy surface area divided by projected area and shows dependence on CHM grain, smoothing, and plot scale. It does not establish one universal local neighborhood. Phase 30A therefore chooses the patch field: it adds no arbitrary scale and its valid-cell arithmetic mean is exactly the upstream scalar because every patch has equal planar area. Moving-window and block products are valid study-design choices but remain future advanced options.

## Interpretation

The raster is a **PyForestScan-QGIS spatial extension**, not an upstream raster API. Values are dimensionless, flat patches equal 1, and rougher patches exceed 1. Comparisons require compatible CHM resolution, interpolation, height threshold, and validity behavior.
