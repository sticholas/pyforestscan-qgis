# PyForestScan API Coverage Matrix

Phase 20B audits the official PyForestScan documentation against the QGIS plugin. Status meanings:

- **Implemented**: exposed through Guided Mode or Advanced Toolbox and routed through the adapter.
- **Partially implemented**: some documented parameters/workflows are supported, but not the full public function surface.
- **Deferred**: valid PyForestScan capability, but requires more product design, cancellation/progress design, or manual QA.
- **Not applicable**: PyForestScan helper is superseded by QGIS UI or plugin architecture.

Sources reviewed: official usage pages for importing/preprocessing/writing, DTM, forest-structure intro, CHM, Rumple, PAD, PAI, FHD; API pages for calculate, filters, handlers, process, pipeline, visualize; examples and benchmarks where relevant.

## Calculate Module

| Function | Parameters/defaults | Return type | Plugin status | Where implemented | Missing/deferred parameters | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `assign_voxels` | `arr`, `voxel_resolution` | `(ndarray, extent)` | Implemented | Adapter product methods for PAD, PAI, Canopy Cover, FHD | None for current products | Advanced algorithms expose X/Y/z voxel resolution. |
| `calculate_chm` | `arr`, `voxel_resolution`, `interpolation='linear'`, `interp_valid_region=False`, `interp_clean_edges=False` | `(ndarray, extent)` | Implemented | `PyForestScanAdapter.create_chm`, Advanced CHM, Guided CHM | None | Advanced CHM exposes interpolation, valid-region interpolation, edge cleaning, X/Y resolution. |
| `calculate_pad` | `voxel_returns`, `voxel_height=1.0`, `beer_lambert_constant=1.0`, `drop_ground=True` | `ndarray` | Implemented | `create_pad`; internal PAI/Canopy Cover prerequisite | None | PAD output is multi-band GeoTIFF. |
| `calculate_pai` | `pad`, `voxel_height`, `min_height=1.0`, `max_height=None` | 2D `ndarray` | Implemented | `create_pai`, Advanced PAI | None | Beer-Lambert/drop-ground exposed for internal PAD. |
| `calculate_canopy_cover` | `pad`, `voxel_height`, `min_height=2.0`, `max_height=None`, `k=0.5` | 2D `ndarray` | Implemented | `create_canopy_cover`, Advanced Canopy Cover | None | Advanced exposes threshold, max height, k, and internal PAD settings. |
| `calculate_fhd` | `voxel_returns`, `voxel_height=1.0`, `min_height=0.0`, `max_height=None` | 2D `ndarray` | Implemented | `create_fhd`, Advanced FHD | None | Advanced exposes height range. |
| `calculate_rumple` | `chm`, `cell_resolution`, `min_height=None` | scalar `float` | Implemented | `create_rumple`, Advanced Rumple | None | Output is CSV summary, not raster. |
| `calculate_point_density` | `voxel_returns`, `per_area=False`, `cell_area=None` | 2D `ndarray` | Implemented | `PyForestScanAdapter.create_point_density`, Advanced Point Density | None | Phase 20C exposes exact `per_area` and `cell_area` controls. |
| `calculate_voxel_stat` | `arr`, `voxel_resolution`, `dimension`, `stat`, `z_index_range=None` | 2D `ndarray` | Implemented | `PyForestScanAdapter.create_voxel_stat`, Advanced Voxel Statistic | None | Phase 20C exposes `dimension`, documented `stat` values, and optional `z_index_range`. |
| `generate_dtm` | `ground_points`, `resolution=2.0` | `(ndarray, extent)` | Implemented | `PyForestScanAdapter.generate_dtm`, Advanced DTM | None | Advanced DTM can optionally classify ground first. |

## Filters Module

| Function | Parameters/defaults | Return type | Plugin status | Where implemented | Missing/deferred parameters | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `add_height_above_ground` | `existing_points`, `method=None`, `dtm=None` | list of arrays | Implemented | Advanced Point Cloud Preprocess | None | HAG/Normalize also supports read-time HAG. |
| `classify_ground_points` | SMRF wrapper with `ignore_class`, `cell`, `cut`, `returns`, `scalar`, `slope`, `threshold`, `window` | arrays | Implemented | Advanced DTM optional default step; Advanced Point Cloud Preprocess exposes full parameters | None for preprocess tool | Phase 20D closes full SMRF parameter parity. |
| `remove_outliers_and_clean` | `arrays`, `mean_k=8`, `multiplier=3.0`, `remove=False` | arrays | Implemented | Advanced Point Cloud Preprocess | None | Phase 20D exposes `remove`. |
| `filter_ground` | `arrays` | arrays | Implemented | Advanced Point Cloud Preprocess | None | Removes classification 2. |
| `filter_select_ground` | `arrays` | arrays | Implemented | Advanced DTM; Advanced Point Cloud Preprocess | None | Selects classification 2. |
| `filter_hag` | `arrays`, `lower_limit=0`, `upper_limit=None` | arrays | Implemented | Advanced Point Cloud Preprocess | None | Requires HAG dimension. |
| `filter_pointsourceid` | `arrays`, `pointsource_ids` | arrays | Implemented | Advanced Point Cloud Preprocess | None | Phase 20D exposes comma-separated PointSourceId values. |
| `downsample_poisson` | `arrays`, `thin_radius` | arrays | Implemented | Advanced Point Cloud Preprocess | None | Exposed as optional Poisson thinning radius. |
| `downsample_voxel` | `arrays`, `cell`, `mode` | arrays | Implemented | Advanced Point Cloud Preprocess | None | Exposes safe documented modes in UI. |

## Handlers Module

| Function | Parameters/defaults | Return type | Plugin status | Where implemented | Missing/deferred parameters | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `read_lidar` | `input_file`, `srs`, `bounds=None`, `thin_radius=None`, `hag=False`, `hag_dtm=False`, `dtm=None`, `crop_poly=False`, `poly=None`, `reproject=False` | arrays or `None` | Partially implemented | All adapter product reads; HAG/Normalize exposes bounds/thin/crop/reproject/HAG/DTM | Product algorithms do not expose crop/bounds yet | Advanced HAG is the read-option utility; product algorithms stay product-focused. |
| `write_las` | `arrays`, `output_file`, `srs=None`, `compress=True` | `None` | Implemented | HAG/Normalize; Advanced Point Cloud Preprocess | None | Exposed only where point-cloud output is honest. |
| `create_geotiff` | `layer`, `output_file`, `crs`, `spatial_extent`, `nodata=-9999` | `None` | Partially implemented | Adapter products; Advanced DTM exposes nodata | Product algorithms do not expose nodata yet | Product nodata remains default to preserve output consistency. |
| `load_polygon_from_file` | `vector_file_path`, `index=0` | `(wkt, crs)` | Deferred | None | All parameters | Polygon crop support uses WKT/path passthrough in HAG; full vector selection needs QGIS layer UX. |
| `get_raster_epsg` | `dtm_path` | CRS string | Deferred | None | All parameters | QGIS CRS/provider APIs can inspect rasters; not useful as standalone Processing output yet. |
| `simplify_crs` | `crs_list` | list | Not applicable | QGIS CRS handling | N/A | QGIS CRS widgets/auth IDs are preferred. |
| `validate_crs` | `crs_list` | bool | Not applicable | QGIS CRS validation and adapter checks | N/A | Not exposed as standalone algorithm. |
| `validate_extensions` | `las_file_path`, `dtm_file_path` | validation/no return | Not applicable | Adapter path validation | N/A | Narrow LAS/DTM helper; plugin supports COPC/EPT too. |

## Process and Pipeline Modules

| Function/workflow | Parameters/defaults | Return type | Plugin status | Where implemented | Missing/deferred parameters | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `process_with_tiles` | `ept_file`, `tile_size`, `output_path`, `metric`, `voxel_size`, plus HAG, bounds, interpolation, outlier, cover/PAI/FHD, skip, thinning, voxelgrid, tile index controls | `None` | Deferred | None | Full surface | High-value future Advanced workflow, but owns progress, tiling, output naming, and verbose printing. Needs adapter wrapper with cancellation and summary files. |
| Pipeline private helpers | internal | internal | Deferred / not applicable | None | N/A | Private helpers should not be called directly from QGIS. |

## Visualize Module

| Function | Parameters/defaults | Return type | Plugin status | Where implemented | Missing/deferred parameters | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `plot_2d` | point dimensions, color, alpha, size, figure title, slicing, save path | `None` | Not applicable | QGIS layer/table/map canvas workflows | All | QGIS visualization tools are preferred. |
| `plot_metric` | title, metric, extent, metric name, colormap, figure size, save path | `None` | Not applicable | QGIS raster rendering | All | Plugin styling is QGIS-native. |
| `plot_pad` | PAD array, slice/axis/color settings | `None` | Not applicable | PAD RGB/QGIS symbology | All | QGIS band rendering is preferred. |

## Usage Workflows

| Workflow | Coverage status | Notes |
| --- | --- | --- |
| Import/read LAS/LAZ/COPC/EPT | Implemented | Dataset Explorer and adapter reads support these formats; HAG tool exposes advanced read options. |
| HAG from read_lidar | Implemented | HAG/Normalize and product reads use `hag=True`; DTM HAG supported in HAG tool. |
| In-memory HAG after filters | Implemented | Advanced Point Cloud Preprocess exposes `add_height_above_ground`. |
| Export LAS/LAZ | Implemented | HAG/Normalize and Point Cloud Preprocess. |
| DTM generation | Implemented | Advanced DTM. |
| Forest metrics CHM/PAD/PAI/FHD/Rumple/Canopy Cover | Implemented | Guided and Advanced paths. |
| Polygon/bounds crop | Partially implemented | HAG utility exposes bounds/crop passthrough; product-level crop is deferred. |
| Large EPT tiled processing | Deferred | Future advanced algorithm after progress/cancellation design. |
| Benchmarks | Deferred | Benchmark docs inform future runtime calibration; not a Processing algorithm. |
