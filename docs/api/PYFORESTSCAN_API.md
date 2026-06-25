# PyForestScan API Discovery

Phase 3A records the installed PyForestScan `0.4.0` API as observed from the
verified QGIS Python environment. This is documentation only. No plugin
processing behavior is implemented here.

## Runtime Inspected

- QGIS: `3.44.11-Solothurn` reported by plugin Environment Check.
- Python: `3.12.13`.
- PyForestScan: `0.4.0` installed in the Windows Python user site.
- PDAL Python bindings: `3.5.3`.
- GDAL: `3.13.1`.
- rasterio: `1.5.0` reported by plugin Environment Check.
- numpy: `2.4.6`.

The installed package path observed from QGIS/OSGeo4W Python was:

```text
C:\Users\Lama\AppData\Roaming\Python\Python312\site-packages\pyforestscan
```

## Package Structure

Installed modules:

```text
pyforestscan
pyforestscan.calculate
pyforestscan.filters
pyforestscan.handlers
pyforestscan.pipeline
pyforestscan.process
pyforestscan.utils
pyforestscan.visualize
```

There are no installed console-script entry points in `pyforestscan-0.4.0`; no
`entry_points.txt` is present in the distribution metadata. PyForestScan is used
as a Python library.

## Top-Level Public API

`pyforestscan.__init__` re-exports only calculation functions:

| Function | Purpose | Plugin Relevance |
| --- | --- | --- |
| `assign_voxels(arr, voxel_resolution)` | Bin structured point records into a 3D voxel count array. | Core precursor for PAD, PAI, FHD, canopy cover. |
| `calculate_chm(arr, voxel_resolution, interpolation='linear', interp_valid_region=False, interp_clean_edges=False)` | Create a 2D CHM from `HeightAboveGround`. | Future CHM algorithm. |
| `calculate_pad(voxel_returns, voxel_height=1.0, beer_lambert_constant=1.0, drop_ground=True)` | Convert voxel returns to PAD. | Future PAD and downstream metric workflows. |
| `calculate_pai(pad, voxel_height, min_height=1.0, max_height=None)` | Integrate PAD over height to PAI. | Future PAI product. |
| `calculate_fhd(voxel_returns, voxel_height=1.0, min_height=0.0, max_height=None)` | Compute entropy over vertical return proportions. | Future FHD product. |
| `calculate_canopy_cover(pad, voxel_height, min_height=2.0, max_height=None, k=0.5)` | Compute Beer-Lambert canopy cover from PAD. | Future canopy cover product. |
| `calculate_rumple(chm, cell_resolution, min_height=None)` | Compute canopy surface area / planar area ratio. | Future rumple metric. |
| `calculate_point_density(voxel_returns, per_area=False, cell_area=None)` | Sum voxel returns by XY column. | Possible QA or density output. |
| `calculate_voxel_stat(arr, voxel_resolution, dimension, stat, z_index_range=None)` | Compute per-column statistics for a point dimension. | Possible advanced metric interface. |
| `generate_dtm(ground_points, resolution=2.0)` | Build a DTM from ground-classified points. | Potential utility, but likely not first QGIS workflow. |

## Module API Inventory

### `pyforestscan.handlers`

Functions defined by the module:

| Function | Signature | Notes |
| --- | --- | --- |
| `simplify_crs` | `(crs_list) -> list` | Converts CRS definitions to EPSG integers using `pyproj.CRS`. Raises `CRSError` when conversion fails. |
| `load_polygon_from_file` | `(vector_file_path, index=0) -> tuple[str, str]` | Reads vector data with GeoPandas; returns polygon WKT and CRS string. Converts `MultiPolygon` to its first polygon. |
| `get_raster_epsg` | `(dtm_path) -> str` | Opens raster with rasterio and returns CRS string. |
| `validate_extensions` | `(las_file_path, dtm_file_path)` | Checks point cloud `.las`/`.laz` and DTM `.tif`; does not accept COPC in this helper. |
| `validate_crs` | `(crs_list) -> bool` | Confirms simplified EPSG values match. Empty list returns `True`. |
| `read_lidar` | `(input_file, srs, bounds=None, thin_radius=None, hag=False, hag_dtm=False, dtm=None, crop_poly=False, poly=None, reproject=False)` | Main point-cloud reader. Uses PDAL. Supports LAS, LAZ, COPC, COPC LAZ, EPT JSON. |
| `write_las` | `(arrays, output_file, srs=None, compress=True) -> None` | Writes LAS/LAZ with PDAL `writers.las`; `compress=True` requires `.laz`, false requires `.las`. |
| `create_geotiff` | `(layer, output_file, crs, spatial_extent, nodata=-9999) -> None` | Writes single-band GeoTIFF via rasterio. Converts NaN to `-9999`, transposes layer before writing. |

Private helpers in this module include `_is_url`, `_read_point_cloud`, and
`_build_pdal_pipeline`. They should not be called directly by the QGIS plugin.

### `pyforestscan.calculate`

This is the most relevant module for future Processing algorithms. It assumes
NumPy structured arrays and metric arrays, not QGIS layers.

Important field requirements:

- Point arrays for CHM and voxelization require `X`, `Y`, and `HeightAboveGround`.
- DTM generation requires `X`, `Y`, and `Z` in ground-point arrays.
- `calculate_voxel_stat` requires `HeightAboveGround` plus the requested field.

Supported `calculate_voxel_stat` statistics:

```text
mean, sum, count, min, max, median, std
```

### `pyforestscan.filters`

Public filter wrappers operate on PDAL array lists and return PDAL output arrays:

| Function | Purpose |
| --- | --- |
| `filter_hag(arrays, lower_limit=0, upper_limit=None)` | Keep points within a HAG range. |
| `filter_ground(arrays)` | Remove ground classification `2`. |
| `filter_select_ground(arrays)` | Keep only ground classification `2`. |
| `filter_pointsourceid(arrays, pointsource_ids)` | Keep selected `PointSourceId` values. |
| `remove_outliers_and_clean(arrays, mean_k=8, multiplier=3.0, remove=False)` | Label or remove statistical outliers. |
| `classify_ground_points(...)` | Apply PDAL SMRF ground classification. |
| `downsample_poisson(arrays, thin_radius)` | Apply PDAL `filters.sample`. |
| `downsample_voxel(arrays, cell, mode)` | Apply PDAL `filters.voxeldownsize`. |

These wrappers are useful but still close to PDAL. The plugin should call them
through an adapter only after inputs, parameter ranges, and cancellation behavior
are defined.

### `pyforestscan.utils`

| Function | Purpose |
| --- | --- |
| `get_srs_from_ept(ept_file)` | Reads local or URL EPT JSON and returns `AUTHORITY:HORIZONTAL`, or `None`. |
| `get_bounds_from_ept(ept_file)` | Reads local or URL EPT JSON and returns `(min_x, max_x, min_y, max_y, min_z, max_z)`. |
| `tile_las_in_memory(las_file, tile_width, tile_height, overlap, output_dir, srs=None)` | Loads a whole LAS/LAZ/COPC into memory and writes uncompressed LAS tiles. |

`tile_las_in_memory` prints progress to stdout and fully loads input into memory;
it is not appropriate for direct QGIS Processing use without an adapter.

### `pyforestscan.process`

`process_with_tiles(...)` is a high-level EPT tiling workflow. It supports
metrics `chm`, `fhd`, `pai`, and `cover`. It writes GeoTIFF tiles directly to an
output directory.

Key traits:

- Reads EPT tiles with PDAL `readers.ept`.
- Uses `tqdm` for progress and `print` for per-tile warnings.
- Writes files during processing with names like `tile_i_j_chm.tif`.
- Supports HAG from Delaunay or DTM, outlier removal, Poisson thinning,
  voxel-grid downsampling, tile buffers, and skip-existing behavior.
- Does not support rumple directly.

For QGIS, this function is useful as design reference but should not be the
first integration target because it owns progress, tiling, output naming, and
warning behavior internally.

### `pyforestscan.visualize`

Visualization helpers use Matplotlib:

- `plot_2d(...)`
- `plot_metric(...)`
- `plot_pad(...)`

These are not appropriate for QGIS Processing algorithms. QGIS should use QGIS
layers, renderers, and style files instead.

## Entry Points and CLI

No packaged CLI entry points were found in `pyforestscan-0.4.0.dist-info`.
The installed package provides library modules only.

## Project Creation

No project object, workspace object, configuration class, or session manager was
found in the installed package. A QGIS plugin should therefore create its own
plugin-side request/configuration objects and pass plain values into PyForestScan
functions.

## Recommended Adapter Interface

Recommended future adapter module: `pyforestscan_qgis/core/pyforestscan_adapter.py`.
Do not implement this yet.

Suggested interface shape:

```python
load_point_cloud(input_path, crs, *, bounds=None, hag=False, hag_dtm=False,
                 dtm_path=None, crop_polygon=None, reproject=False,
                 thin_radius=None) -> PointCloudResult

create_chm(point_cloud, cell_size, *, interpolation='linear',
           valid_region=False, clean_edges=False) -> RasterProduct

create_voxels(point_cloud, voxel_size) -> VoxelProduct

create_pad(voxels, voxel_height, *, beer_lambert_constant=1.0,
           drop_ground=True) -> VoxelProduct

create_pai(pad, voxel_height, *, min_height=1.0, max_height=None) -> RasterProduct

create_fhd(voxels, voxel_height, *, min_height=0.0, max_height=None) -> RasterProduct

create_canopy_cover(pad, voxel_height, *, min_height=2.0,
                    max_height=None, k=0.5) -> RasterProduct

create_rumple(chm, cell_resolution, *, min_height=None) -> ScalarMetric

write_raster(product, output_path, crs, extent, *, nodata=-9999) -> Path
```

Adapter responsibilities:

- Convert QGIS parameters into PyForestScan primitive values.
- Validate file paths, CRS, units, and mutually exclusive options before calling
  PyForestScan.
- Own output naming and metadata capture.
- Convert PyForestScan exceptions into QGIS Processing errors.
- Emit progress through QGIS feedback, not `print` or `tqdm`.
- Keep all direct PyForestScan imports in the adapter/core boundary.

## Do Not Call Directly From QGIS

Avoid direct QGIS algorithm calls to:

- `pyforestscan.pipeline._*` private helpers.
- `pyforestscan.handlers._read_point_cloud` and `_build_pdal_pipeline`.
- `pyforestscan.process.process_with_tiles` until wrapped for QGIS feedback,
  cancellation, output naming, and error handling.
- `pyforestscan.utils.tile_las_in_memory` for large data or default workflows.
- `pyforestscan.visualize.*` from Processing algorithms.
