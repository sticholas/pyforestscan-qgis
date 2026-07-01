# PyForestScan Function Parameter Parity

Phase 20D maps each documented public function parameter to the Advanced QGIS Processing Toolbox, adapter, or an explicit deferral. In-memory objects such as `arr`, `arrays`, `pad`, `chm`, `voxel_returns`, and `ground_points` are mapped internally because QGIS users choose datasets and output paths, not Python objects.

## Legend

- **Yes**: exposed or mapped through adapter-backed Advanced Toolbox code.
- **Partial**: covered by plugin architecture but not every low-level option is user-facing on every product tool.
- **Deferred**: intentionally not exposed yet; reason documented.
- **N/A**: not meaningful as a QGIS Processing parameter.

## calculate

| Module | Function | Parameter | Type | Default | PyForestScan wording/description | QGIS Advanced Toolbox label | QGIS type | Status | Tool / mapping | Reason if not directly exposed | Test coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| calculate | `assign_voxels` | `arr` | array | required | spatial data points | Input lidar dataset | file | Yes | Adapter reads/merges arrays | In-memory array mapped internally | Yes |
| calculate | `assign_voxels` | `voxel_resolution` | tuple | required | x/y/z voxel resolution | X resolution, Y resolution, voxel height | number | Yes | Metrics tools | Split into QGIS-friendly controls | Yes |
| calculate | `calculate_chm` | `voxel_resolution` | tuple | required | resolution | X resolution, Y resolution | number | Yes | Advanced CHM | Tuple assembled by builder | Yes |
| calculate | `calculate_chm` | `interpolation` | string/None | `linear` | nearest, linear, cubic, None | Interpolation | enum | Yes | Advanced CHM | `none` maps to Python `None` | Yes |
| calculate | `calculate_chm` | `interp_valid_region` | bool | `False` | valid-region interpolation | Interpolate valid region only | boolean | Yes | Advanced CHM | Direct | Yes |
| calculate | `calculate_chm` | `interp_clean_edges` | bool | `False` | clean interpolation edges | Clean interpolation edges | boolean | Yes | Advanced CHM | Direct | Yes |
| calculate | `calculate_pad` | `voxel_height` | float | `1.0` | voxel height | Voxel height / height bin size | number | Yes | Advanced PAD | Direct | Yes |
| calculate | `calculate_pad` | `beer_lambert_constant` | float | `1.0` | Beer-Lambert constant | Beer-Lambert constant | number | Yes | Advanced PAD/PAI/Canopy Cover | Internal PAD prerequisite controls exposed | Yes |
| calculate | `calculate_pad` | `drop_ground` | bool | `True` | drop ground | Drop ground bin | boolean | Yes | Advanced PAD/PAI/Canopy Cover | Internal PAD prerequisite controls exposed | Yes |
| calculate | `calculate_pai` | `voxel_height` | float | required | voxel height | Voxel height | number | Yes | Advanced PAI | Direct | Yes |
| calculate | `calculate_pai` | `min_height` | float | `1.0` | min height | Minimum height | number | Yes | Advanced PAI | Direct | Yes |
| calculate | `calculate_pai` | `max_height` | float/None | `None` | max height | Optional maximum height | number optional | Yes | Advanced PAI | Direct | Yes |
| calculate | `calculate_canopy_cover` | `voxel_height` | float | required | voxel height | Voxel height | number | Yes | Advanced Canopy Cover | Direct | Yes |
| calculate | `calculate_canopy_cover` | `min_height` | float | `2.0` | minimum height threshold | Minimum height / canopy threshold | number | Yes | Advanced Canopy Cover | Label clarifies product meaning | Yes |
| calculate | `calculate_canopy_cover` | `max_height` | float/None | `None` | max height | Optional maximum height | number optional | Yes | Advanced Canopy Cover | Direct | Yes |
| calculate | `calculate_canopy_cover` | `k` | float | `0.5` | extinction coefficient | Extinction coefficient k | number | Yes | Advanced Canopy Cover | Direct | Yes |
| calculate | `calculate_fhd` | `voxel_height` | float | `1.0` | voxel height | Voxel height | number | Yes | Advanced FHD | Direct | Yes |
| calculate | `calculate_fhd` | `min_height` | float | `0.0` | minimum height | Minimum height | number | Yes | Advanced FHD | Direct | Yes |
| calculate | `calculate_fhd` | `max_height` | float/None | `None` | max height | Optional maximum height | number optional | Yes | Advanced FHD | Direct | Yes |
| calculate | `calculate_rumple` | `chm` | array | required | Canopy Height Model | Input lidar dataset | file | Yes | Advanced Rumple | CHM computed internally through adapter | Yes |
| calculate | `calculate_rumple` | `cell_resolution` | tuple | required | cell resolution | CHM X resolution, CHM Y resolution | number | Yes | Advanced Rumple | Tuple assembled by builder | Yes |
| calculate | `calculate_rumple` | `min_height` | float/None | `None` | min height | Optional minimum height | number optional | Yes | Advanced Rumple | Direct | Yes |
| calculate | `calculate_point_density` | `voxel_returns` | array | required | voxel returns | Input lidar dataset | file | Yes | Advanced Point Density | Voxel returns created internally | Yes |
| calculate | `calculate_point_density` | `per_area` | bool | `False` | per area | per_area | boolean | Yes | Advanced Point Density | Exact label | Yes |
| calculate | `calculate_point_density` | `cell_area` | float/None | `None` | cell area | cell_area | number optional | Yes | Advanced Point Density | Adapter uses X*Y if omitted | Yes |
| calculate | `calculate_voxel_stat` | `arr` | array | required | point cloud array | Input lidar dataset | file | Yes | Advanced Voxel Statistic | Array loaded internally | Yes |
| calculate | `calculate_voxel_stat` | `voxel_resolution` | tuple | required | voxel resolution | X resolution, Y resolution, voxel height | number | Yes | Advanced Voxel Statistic | Tuple assembled by builder | Yes |
| calculate | `calculate_voxel_stat` | `dimension` | string | required | dimension | dimension | string | Yes | Advanced Voxel Statistic | Exact label | Yes |
| calculate | `calculate_voxel_stat` | `stat` | enum | required | mean/sum/count/min/max/median/std | stat | enum | Yes | Advanced Voxel Statistic | Exact values | Yes |
| calculate | `calculate_voxel_stat` | `z_index_range` | tuple/None | `None` | z index range | z_index_range minimum/maximum | numbers optional | Yes | Advanced Voxel Statistic | Tuple split into QGIS numeric controls | Yes |
| calculate | `generate_dtm` | `ground_points` | array | required | classified ground points | Input lidar dataset | file | Yes | Advanced DTM | Ground selected internally | Yes |
| calculate | `generate_dtm` | `resolution` | float | `2.0` | DTM resolution | DTM resolution | number | Yes | Advanced DTM | Direct | Yes |

## filters

| Module | Function | Parameter | Type | Default | Description | QGIS Advanced Toolbox label | QGIS type | Status | Tool / mapping | Reason if not directly exposed | Test coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| filters | `add_height_above_ground` | `existing_points` | arrays | required | existing point arrays | Input lidar dataset | file | Yes | Advanced Point Cloud Preprocess | Arrays loaded internally | Yes |
| filters | `add_height_above_ground` | `method` | string/None | `None` | HAG method | method | enum auto/delaunay/dtm | Yes | Advanced Point Cloud Preprocess | `auto` maps to `None` | Yes |
| filters | `add_height_above_ground` | `dtm` | path/None | `None` | DTM raster | dtm | file optional | Yes | Advanced Point Cloud Preprocess | Direct | Yes |
| filters | `classify_ground_points` | `arrays` | arrays | required | arrays | Input lidar dataset | file | Yes | Advanced Point Cloud Preprocess | Arrays loaded internally | Yes |
| filters | `classify_ground_points` | `ignore_class` | string | `Classification[7:7]` | ignore class | ignore_class | string | Yes | Advanced Point Cloud Preprocess | Direct | Yes |
| filters | `classify_ground_points` | `cell` | float | `1.0` | SMRF cell | cell | number | Yes | Advanced Point Cloud Preprocess | Direct | Yes |
| filters | `classify_ground_points` | `cut` | float | `0.0` | SMRF cut | cut | number | Yes | Advanced Point Cloud Preprocess | Direct | Yes |
| filters | `classify_ground_points` | `returns` | string | `last,only` | returns | returns | string | Yes | Advanced Point Cloud Preprocess | Direct | Yes |
| filters | `classify_ground_points` | `scalar` | float | `1.25` | scalar | scalar | number | Yes | Advanced Point Cloud Preprocess | Direct | Yes |
| filters | `classify_ground_points` | `slope` | float | `0.15` | slope | slope | number | Yes | Advanced Point Cloud Preprocess | Direct | Yes |
| filters | `classify_ground_points` | `threshold` | float | `0.5` | threshold | threshold | number | Yes | Advanced Point Cloud Preprocess | Direct | Yes |
| filters | `classify_ground_points` | `window` | float | `18.0` | window | window | number | Yes | Advanced Point Cloud Preprocess | Direct | Yes |
| filters | `downsample_poisson` | `arrays` | arrays | required | arrays | Input lidar dataset | file | Yes | Advanced Point Cloud Preprocess | Arrays loaded internally | Yes |
| filters | `downsample_poisson` | `thin_radius` | float | required | thinning radius | thin_radius | number optional | Yes | Advanced Point Cloud Preprocess | Direct | Yes |
| filters | `downsample_voxel` | `arrays` | arrays | required | arrays | Input lidar dataset | file | Yes | Advanced Point Cloud Preprocess | Arrays loaded internally | Yes |
| filters | `downsample_voxel` | `cell` | float | required | voxel cell | cell | number optional | Yes | Advanced Point Cloud Preprocess | Direct | Yes |
| filters | `downsample_voxel` | `mode` | string | required | voxel mode | mode | enum | Yes | Advanced Point Cloud Preprocess | Direct | Yes |
| filters | `filter_ground` | `arrays` | arrays | required | remove ground | Ground filter action = remove_ground | enum | Yes | Advanced Point Cloud Preprocess | Direct action | Yes |
| filters | `filter_hag` | `arrays` | arrays | required | arrays | Input lidar dataset | file | Yes | Advanced Point Cloud Preprocess | Arrays loaded internally | Yes |
| filters | `filter_hag` | `lower_limit` | float | `0` | lower limit | lower_limit | number | Yes | Advanced Point Cloud Preprocess | Direct | Yes |
| filters | `filter_hag` | `upper_limit` | float/None | `None` | upper limit | upper_limit | number optional | Yes | Advanced Point Cloud Preprocess | Direct | Yes |
| filters | `filter_pointsourceid` | `arrays` | arrays | required | arrays | Input lidar dataset | file | Yes | Advanced Point Cloud Preprocess | Arrays loaded internally | Yes |
| filters | `filter_pointsourceid` | `pointsource_ids` | sequence | required | point source IDs | pointsource_ids | string list | Yes | Advanced Point Cloud Preprocess | CSV string parsed to tuple | Yes |
| filters | `filter_select_ground` | `arrays` | arrays | required | select ground | Ground filter action = select_ground | enum | Yes | Advanced Point Cloud Preprocess / Advanced DTM | Direct action | Yes |
| filters | `remove_outliers_and_clean` | `arrays` | arrays | required | arrays | Input lidar dataset | file | Yes | Advanced Point Cloud Preprocess | Arrays loaded internally | Yes |
| filters | `remove_outliers_and_clean` | `mean_k` | int | `8` | mean k | mean_k | integer | Yes | Advanced Point Cloud Preprocess | Direct | Yes |
| filters | `remove_outliers_and_clean` | `multiplier` | float | `3.0` | multiplier | multiplier | number | Yes | Advanced Point Cloud Preprocess | Direct | Yes |
| filters | `remove_outliers_and_clean` | `remove` | bool | `False` | remove outliers | remove | boolean | Yes | Advanced Point Cloud Preprocess | Direct | Yes |

## handlers, process, utils, visualize

Detailed status for non-calculate/filter functions is maintained in `PYFORESTSCAN_FULL_API_SURFACE.md` and `PYFORESTSCAN_DEFERRED_FEATURES.md`. In brief: `write_las`, DTM `create_geotiff(nodata)`, HAG read options, and product GeoTIFF creation are implemented; standalone CRS/polygon helpers, `process_with_tiles`, memory tiling utilities, and matplotlib visualization helpers are deferred with reasons.
