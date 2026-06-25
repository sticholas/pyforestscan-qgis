# PyForestScan Products

This document maps PyForestScan `0.4.0` functions to product types relevant to
the QGIS plugin roadmap.

## Point Cloud Inputs

Supported by `handlers.read_lidar`:

- LAS: `.las`
- LAZ: `.laz`
- COPC: `.copc`
- COPC LAZ: `.copc.laz`
- EPT: `ept.json`

The input must be local unless it is an EPT source. EPT JSON metadata helpers can
read local files or URLs with `http://`, `https://`, or `s3://` prefixes.

## Vector Inputs

Polygon clipping accepts:

- WKT `POLYGON` or `MULTIPOLYGON` strings.
- Vector files readable by GeoPandas.

QGIS should pass validated/transformed WKT rather than relying on PyForestScan to
handle CRS transformation.

## Raster Inputs

HAG from DTM accepts a `.tif` raster path. `get_raster_epsg` reads CRS with
rasterio.

## Raster Products

| Product | Function Path | Output Type | Notes |
| --- | --- | --- | --- |
| CHM | `calculate_chm(point_array, voxel_resolution)` | 2D NumPy array + extent | Requires `HeightAboveGround`; supports optional interpolation. |
| DTM | `generate_dtm(ground_points, resolution)` | 2D NumPy array + extent | Builds from ground points with `X`, `Y`, `Z`; not a first plugin target. |
| PAD | `calculate_pad(voxel_returns, voxel_height, ...)` | 3D NumPy array | Voxel product, not directly a standard 2D raster unless sliced/summarized. |
| PAI | `calculate_pai(pad, voxel_height, ...)` | 2D NumPy array | Derived from PAD. |
| FHD | `calculate_fhd(voxel_returns, voxel_height, ...)` | 2D NumPy array | Derived from voxel returns. |
| Canopy cover | `calculate_canopy_cover(pad, voxel_height, ...)` | 2D NumPy array | Derived from PAD using Beer-Lambert relation. |
| Point density | `calculate_point_density(voxel_returns, ...)` | 2D NumPy array | Count or density per XY voxel column. |
| Voxel statistic | `calculate_voxel_stat(arr, voxel_resolution, dimension, stat, ...)` | 2D NumPy array + extent | Supports arbitrary numeric point dimension statistics. |

`handlers.create_geotiff` writes single-band GeoTIFFs from 2D metric arrays.

## Scalar Products

| Product | Function | Output Type |
| --- | --- | --- |
| Rumple index | `calculate_rumple(chm, cell_resolution, min_height=None)` | `float` |

The current rumple API returns one scalar for a CHM array. A future QGIS raster
rumple product would require windowed or polygon-based adapter logic, not only a
direct call.

## Vector Products

PyForestScan `0.4.0` does not appear to write vector products or polygon summary
outputs. It can read polygon inputs for clipping, but tabular/vector summaries
will need plugin-side implementation or future PyForestScan support.

## Point Cloud Outputs

`handlers.write_las` writes point arrays to:

- `.laz` when `compress=True`.
- `.las` when `compress=False`.

`utils.tile_las_in_memory` writes uncompressed `.las` tiles.

## Visualization Products

`visualize.plot_2d`, `plot_metric`, and `plot_pad` create Matplotlib plots. These
are not QGIS products. Future QGIS visualization should use QGIS layers and style
files instead.
