# PyForestScan Full API Surface

Phase 20D inventories public documented functions, installed public functions, and internal helpers found in the installed package source.

## calculate

| Function | Signature | Return | Plugin status |
| --- | --- | --- | --- |
| `generate_dtm` | `generate_dtm(ground_points, resolution=2.0)` | `(ndarray, extent)` | Implemented by Advanced DTM; `ground_points` mapped internally. |
| `assign_voxels` | `assign_voxels(arr, voxel_resolution)` | `(voxel_returns, extent)` | Implemented internally by voxel products and Advanced Point Density. |
| `calculate_pad` | `calculate_pad(voxel_returns, voxel_height=1.0, beer_lambert_constant=1.0, drop_ground=True)` | `ndarray` | Implemented by Advanced PAD and internal prerequisites. |
| `calculate_pai` | `calculate_pai(pad, voxel_height, min_height=1.0, max_height=None)` | `ndarray` | Implemented by Advanced PAI. |
| `calculate_canopy_cover` | `calculate_canopy_cover(pad, voxel_height, min_height=2.0, max_height=None, k=0.5)` | `ndarray` | Implemented by Advanced Canopy Cover. |
| `calculate_fhd` | `calculate_fhd(voxel_returns, voxel_height=1.0, min_height=0.0, max_height=None)` | `ndarray` | Implemented by Advanced FHD. |
| `calculate_point_density` | `calculate_point_density(voxel_returns, per_area=False, cell_area=None)` | `ndarray` | Implemented by Advanced Point Density. |
| `calculate_voxel_stat` | `calculate_voxel_stat(arr, voxel_resolution, dimension, stat, z_index_range=None)` | `ndarray, extent` | Implemented by Advanced Voxel Statistic. |
| `calculate_chm` | `calculate_chm(arr, voxel_resolution, interpolation='linear', interp_valid_region=False, interp_clean_edges=False)` | `(ndarray, extent)` | Implemented by Advanced CHM. |
| `calculate_rumple` | `calculate_rumple(chm, cell_resolution, min_height=None)` | `float` | Implemented by Advanced Rumple as CSV. |

## filters

| Function | Signature | Return | Plugin status |
| --- | --- | --- | --- |
| `filter_hag` | `filter_hag(arrays, lower_limit=0, upper_limit=None)` | `List` | Implemented by Advanced Point Cloud Preprocess / Filters. |
| `filter_ground` | `filter_ground(arrays)` | `List` | Implemented by Advanced Point Cloud Preprocess / Filters. |
| `filter_select_ground` | `filter_select_ground(arrays)` | `List` | Implemented by Advanced DTM and Advanced Point Cloud Preprocess / Filters. |
| `filter_pointsourceid` | `filter_pointsourceid(arrays, pointsource_ids)` | `List` | Implemented in Phase 20D by Advanced Point Cloud Preprocess / Filters. |
| `remove_outliers_and_clean` | `remove_outliers_and_clean(arrays, mean_k=8, multiplier=3.0, remove=False)` | `List` | Implemented in Phase 20D with exact `remove` flag. |
| `classify_ground_points` | `classify_ground_points(arrays, ignore_class='Classification[7:7]', cell=1.0, cut=0.0, returns='last,only', scalar=1.25, slope=0.15, threshold=0.5, window=18.0)` | `List` | Implemented in Phase 20D with full SMRF parameter surface in Advanced Point Cloud Preprocess / Filters. |
| `downsample_poisson` | `downsample_poisson(arrays, thin_radius)` | `List` | Implemented by Advanced Point Cloud Preprocess / Filters. |
| `downsample_voxel` | `downsample_voxel(arrays, cell, mode)` | `List` | Implemented by Advanced Point Cloud Preprocess / Filters. |

## handlers

| Function | Signature | Return | Plugin status |
| --- | --- | --- | --- |
| `simplify_crs` | `simplify_crs(crs_list)` | `List` | Deferred; QGIS CRS widgets and provider CRS APIs are preferred. |
| `load_polygon_from_file` | `load_polygon_from_file(vector_file_path, index=0)` | `(wkt, crs)` | Deferred; QGIS native vector-layer selection UX is preferred before exposing this as a tool. |
| `get_raster_epsg` | `get_raster_epsg(dtm_path)` | `str` | Deferred; QGIS raster provider CRS inspection is preferred. |
| `validate_extensions` | `validate_extensions(las_file_path, dtm_file_path)` | validation/no return | Deferred; adapter path validation handles broader plugin formats. |
| `validate_crs` | `validate_crs(crs_list)` | `bool` | Deferred; QGIS CRS validation and adapter checks are used. |
| `read_lidar` | `read_lidar(input_file, srs, bounds=None, thin_radius=None, hag=False, hag_dtm=False, dtm=None, crop_poly=False, poly=None, reproject=False)` | arrays or `None` | Partially implemented across Dataset Explorer, HAG/Normalize, preprocessing, and products. |
| `write_las` | `write_las(arrays, output_file, srs=None, compress=True)` | `None` | Implemented by HAG/Normalize and Advanced Point Cloud Preprocess / Filters. |
| `create_geotiff` | `create_geotiff(layer, output_file, crs, spatial_extent, nodata=-9999)` | `None` | Implemented by raster products; Advanced DTM exposes `nodata`; other product nodata is deferred for output consistency. |

## process

| Function | Signature | Return | Plugin status |
| --- | --- | --- | --- |
| `process_with_tiles` | `process_with_tiles(ept_file, tile_size, output_path, metric, voxel_size, voxel_height=1, buffer_size=0.1, srs=None, hag=False, hag_dtm=False, dtm=None, bounds=None, interpolation=None, remove_outliers=False, outlier_mean_k=8, outlier_multiplier=3.0, cover_min_height=2.0, cover_k=0.5, pai_min_height=1.0, fhd_min_height=0.0, skip_existing=False, verbose=False, thin_radius=None, voxelgrid_cell=None, voxelgrid_mode='first', tile_indices=None, outliers_before_hag=False)` | `None` | Deferred; needs a dedicated QGIS-safe tiling design with cancellation, summaries, and progress. |

## pipeline

Installed `pipeline.py` contains only underscored helper stage builders such as `_hag_delaunay`, `_hag_raster`, `_filter_hag`, `_filter_pointsourceid`, `_filter_smrf`, and `_filter_voxeldownsize`. These are internal implementation helpers, not public plugin targets. The plugin uses public `filters` and `handlers` wrappers instead.

## utils

| Function | Signature | Return | Plugin status |
| --- | --- | --- | --- |
| `get_srs_from_ept` | `get_srs_from_ept(ept_file)` | `str or None` | Deferred; Dataset Explorer inspects EPT metadata and QGIS CRS handling remains plugin-owned. |
| `get_bounds_from_ept` | `get_bounds_from_ept(ept_file)` | 6-value bounds tuple | Deferred; Dataset Explorer already inspects bounds through adapter metadata paths. |
| `tile_las_in_memory` | `tile_las_in_memory(las_file, tile_width, tile_height, overlap, output_dir, srs=None)` | `None` | Deferred; memory-heavy tiling needs a separate safe workflow and QA. |

## visualize

| Function | Signature | Return | Plugin status |
| --- | --- | --- | --- |
| `plot_2d` | `plot_2d(points, x_dim='X', y_dim='Z', color_by='HeightAboveGround', color_map='viridis', colorbar_label=None, alpha=1.0, point_size=1, fig_size=None, fig_title=None, slice_dim=None, slice_val=0.0, slice_tolerance=5, save_fname=None)` | `None` | Deferred / not applicable; QGIS map canvas, point-cloud rendering, and layer styling are preferred. |
| `plot_metric` | `plot_metric(title, metric, extent, metric_name=None, cmap='viridis', fig_size=None, vmin=None, vmax=None, zero_as_nan=False, nodata_value=None, save_fname=None)` | `None` | Deferred / not applicable; plugin writes GeoTIFFs and uses QGIS raster styling. |
| `plot_pad` | `plot_pad(pad, slice_index=None, axis='x', cmap='viridis', hag_values=None, horizontal_values=None, title=None, save_fname=None)` | `None` | Deferred / not applicable; PAD is displayed as QGIS multi-band raster/RGB composite. |
