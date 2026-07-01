# PyForestScan Advanced Gap Analysis

Phase 20B compared Phase 20A Advanced Toolbox coverage against the full official PyForestScan documentation. Phase 20C then closed exact `calculate.py` parameter parity gaps for point density and voxel statistics.

## Gaps Closed In Phase 20B

- Added Advanced DTM using `filter_select_ground`, optional `classify_ground_points`, `generate_dtm`, and `create_geotiff`.
- Added Advanced Point Cloud Preprocess / Filters using safe public filter wrappers and `write_las`.
- Expanded HAG/Normalize to expose `read_lidar` bounds, thinning radius, crop polygon, DTM-backed HAG, reprojection, and LAS/LAZ writing.
- Added QGIS-free builders and tests for DTM, preprocessing, HAG options, and bounds parsing.

## Gaps Closed In Phase 20C

- Added Advanced Point Density using `assign_voxels`, `calculate_point_density`, `per_area`, and `cell_area`.
- Added Advanced Voxel Statistic using `calculate_voxel_stat`, `dimension`, the documented `stat` enum, and optional `z_index_range`.
- Added `docs/api/PYFORESTSCAN_EXACT_PARAMETER_MATRIX.md` as the parameter-by-parameter source for Advanced Toolbox parity.

## Gaps Closed In Phase 20D

- Added full SMRF `classify_ground_points` parameters to Advanced Point Cloud Preprocess / Filters.
- Added `filter_pointsourceid` with comma-separated PointSourceId parsing.
- Added `remove_outliers_and_clean(remove=...)` and HAG method `auto` mapping.

## Remaining Deferred Items

| Area | Deferred capability | Reason |
| --- | --- | --- |
| Tiled EPT processing | `process_with_tiles` | Needs adapter wrapper for cancellation, progress, output naming, tile summaries, and avoiding `print`/`tqdm` UX inside QGIS. |
| Product-level clipping | Bounds/polygon options on CHM/PAD/PAI/FHD/cover/rumple | HAG/read utility exposes low-level crop; product crop should use a consistent QGIS vector/bounds UX. |
| Visualization helpers | `plot_2d`, `plot_metric`, `plot_pad` | QGIS has native map canvas, raster symbology, histograms, profiles, layouts, and layer styling. |

## Product Decision

Mission Control remains simple and guided. Advanced Toolbox is the expert surface for lower-level controls. No new advanced controls were added to Mission Control.

## HAG / Normalization Decision

PyForestScan supports HAG during read and after in-memory filtering. The plugin exposes both paths:

- HAG/Normalize: direct `read_lidar` HAG options and optional LAS/LAZ output.
- Point Cloud Preprocess: filter-chain HAG via `add_height_above_ground`.

The plugin does not claim to create a special normalized format beyond LAS/LAZ writing through PyForestScan `write_las`.
