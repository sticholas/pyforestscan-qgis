# PyForestScan Limitations for QGIS Integration

This document records limitations observed in installed PyForestScan `0.4.0`.
It is not criticism of the library; it identifies integration boundaries for a
production QGIS Processing plugin.

## No Project or Configuration Object

No project/session/configuration class was found. The package is function-based.
The QGIS plugin should own configuration dataclasses and convert them to
PyForestScan function arguments.

## Private PDAL Pipeline Helpers

`pyforestscan.pipeline` functions are private by naming convention (`_filter_*`,
`_hag_*`, `_crop_polygon`, `_reproject`). They return PDAL JSON fragments and are
not stable public API. QGIS algorithms should not call them directly.

## Progress and Cancellation

PyForestScan does not accept a progress callback or cancellation token.
`process_with_tiles` uses `tqdm`; some utilities use `print`. QGIS integration
must wrap workflows so progress is emitted through `QgsProcessingFeedback` and
long-running operations can be cancelled where possible.

## CRS Handling

Observed CRS support is useful but limited:

- `read_lidar` accepts an `srs` string and can add a PDAL reprojection stage.
- `validate_crs` can compare CRS values after simplifying to EPSG codes.
- `load_polygon_from_file` returns vector CRS but `read_lidar` does not validate
  it before clipping.
- `get_srs_from_ept` returns `AUTHORITY:HORIZONTAL` if those EPT fields exist,
  otherwise `None`.

The plugin should perform QGIS-side CRS validation and transformation before
calling PyForestScan.

## Format-Specific Behavior

- `read_lidar` supports `.las`, `.laz`, `.copc`, `.copc.laz`, and `ept.json`.
- Bounds are only attached to the PDAL reader for EPT.
- `validate_extensions` only accepts `.las`/`.laz` point clouds and `.tif` DTM;
  it does not reflect the broader `read_lidar` format support.
- `tile_las_in_memory` fully loads input into memory and is not suitable for
  large production workflows.

## Output Ownership

PyForestScan can write GeoTIFF and LAS/LAZ outputs, but it does not write QGIS
layers, styles, metadata sidecars, Processing result dictionaries, or provenance
records. The plugin should own output metadata and layer loading.

## High-Level Tiled Workflow Risks

`process_with_tiles` is powerful but not yet ideal as a direct QGIS Processing
engine:

- EPT only.
- Writes files directly inside the loop.
- Owns output filenames.
- Uses `tqdm` and `print` instead of QGIS feedback.
- Skips invalid/empty tiles in some cases rather than returning structured
  warnings.
- Supports `chm`, `fhd`, `pai`, and `cover`, but not `pad` or `rumple` as direct
  output metrics.

## Scientific and Product Gaps

- PAD is a 3D array; QGIS output strategy for PAD slices, stacks, or summaries
  must be designed.
- Rumple returns a scalar over an entire CHM, not a raster by default.
- Polygon summaries are not implemented in PyForestScan `0.4.0`.
- Publication-quality output layouts are outside PyForestScan.

## API Stability Risk

Several useful functions live outside `pyforestscan.__all__` even though they are
not underscore-prefixed. The plugin should use a narrow adapter and keep direct
imports centralized so future PyForestScan API changes can be absorbed in one
place.
