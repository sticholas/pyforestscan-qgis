# Advanced Toolbox Parameter Coverage

This document maps Advanced Toolbox algorithms to PyForestScan functions and parameters.

| Algorithm | PyForestScan functions | Safe parameters exposed | Deferred parameters/workflows |
| --- | --- | --- | --- |
| Advanced CHM | `read_lidar(hag=True)`, `calculate_chm`, `create_geotiff` | CRS, output, X/Y resolution, interpolation, valid-region interpolation, edge cleaning, add to project | Product-level crop/bounds, nodata |
| Advanced PAD | `read_lidar(hag=True)`, `assign_voxels`, `calculate_pad` | CRS, output, X/Y resolution, voxel height, Beer-Lambert constant, drop ground, add to project | Product-level crop/bounds, per-band metadata |
| Advanced PAI | `assign_voxels`, `calculate_pad`, `calculate_pai` | CRS, output, X/Y resolution, voxel height, min/max height, internal PAD Beer-Lambert/drop-ground | Product-level crop/bounds, nodata |
| Advanced Canopy Cover | `assign_voxels`, `calculate_pad`, `calculate_canopy_cover` | CRS, output, X/Y resolution, voxel height, min/max height, k, internal PAD Beer-Lambert/drop-ground | Product-level crop/bounds, nodata |
| Advanced FHD | `assign_voxels`, `calculate_fhd` | CRS, output, X/Y resolution, voxel height, min/max height | Product-level crop/bounds, nodata |
| Advanced Rumple | `calculate_chm`, `calculate_rumple` | CRS, CSV output, X/Y CHM resolution, CHM interpolation, valid-region interpolation, edge cleaning, min height | Optional internal CHM export |
| Generate Height Above Ground / Normalize Heights | `read_lidar`, `write_las` | CRS, HAG/HAG DTM, DTM path, reproject, bounds, thinning radius, crop polygon/WKT, LAS/LAZ output, compression | In-memory output visualization, vector-layer polygon selection |
| Advanced DTM | `read_lidar`, optional `classify_ground_points`, `filter_select_ground`, `generate_dtm`, `create_geotiff` | CRS, DTM resolution, optional classify ground, nodata, add to project | DTM smoothing/QA workflows, product-level DTM reuse |
| Advanced Point Cloud Preprocess / Filters | `remove_outliers_and_clean`, `classify_ground_points`, `filter_ground`, `filter_select_ground`, `add_height_above_ground`, `filter_hag`, `downsample_poisson`, `downsample_voxel`, `write_las` | Outlier mean/multiplier, classify ground, ground action, HAG method/DTM, HAG range, thinning, voxel downsample, compression | PointSourceId filter, full SMRF tuning, process summaries |

## Validation Policy

Advanced request builders validate mechanical correctness only: positive resolutions, valid output extensions, CRS presence, height range ordering, valid enum selections, and required DTM paths. They do not guarantee that an expert parameter choice is scientifically appropriate for a specific forest, sensor, or acquisition design.
