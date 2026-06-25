# PyForestScan Errors and Diagnostics

PyForestScan `0.4.0` primarily reports problems by raising Python exceptions.
It does not expose a structured error type hierarchy or logging callback.

## Common Exceptions Observed

| Area | Exception | Trigger |
| --- | --- | --- |
| File paths | `FileNotFoundError` | Missing point cloud, DTM, polygon file, raster, or EPT JSON. |
| Input format | `ValueError` | Unsupported point cloud extension; invalid DTM extension; invalid output LAS/LAZ extension. |
| Parameters | `ValueError` | Non-positive voxel height, cell size, thinning radius, invalid integration range, invalid statistic, invalid buffer/voxel settings. |
| CRS | `pyproj.exceptions.CRSError` | CRS cannot be converted to EPSG. |
| CRS mismatch | `ValueError` | `validate_crs` detects mismatched EPSG values. |
| Array fields | `KeyError` | Required structured array fields are missing. |
| PDAL execution | `pdal.PipelineException` or other PDAL errors | Invalid pipeline, missing dimensions, bad input data, unsupported reader/writer behavior. |
| Raster writing | `rasterio.errors.RasterioError` or `ValueError` | Invalid raster dimensions, invalid extent, raster creation failure. |
| EPT metadata | `KeyError` / `ValueError` | Missing or malformed EPT bounds. |

## Error Handling Strategy for QGIS

The plugin should catch PyForestScan and dependency exceptions at the adapter
boundary and convert them into QGIS Processing errors with actionable messages.

Recommended mapping:

- `FileNotFoundError`: invalid Processing input path.
- `ValueError`: invalid Processing parameter or unsupported input combination.
- `KeyError`: missing point dimension or metadata.
- `CRSError`: invalid or unsupported CRS.
- `pdal.PipelineException`: PDAL processing failure; include the failing stage if
  known.
- `rasterio.errors.RasterioError`: output writer failure.

## Logging and Progress

Observed behavior:

- Calculation functions are silent.
- `process_with_tiles` uses `tqdm` for progress and `print` for warnings.
- `tile_las_in_memory` prints tile creation messages.
- No logging object, logger name, progress callback, or cancellation API was
  found.

The QGIS plugin should not let `print`/`tqdm` be the user-facing reporting path.
Future adapters should emit messages through `QgsProcessingFeedback` and return
structured warnings where possible.

## Warnings to Preserve

Potential warnings the plugin should make explicit:

- Empty point cloud returned from reader.
- Empty tile skipped.
- Outlier removal or downsampling emptied a tile.
- Buffer exceeds output dimensions and was adjusted.
- Invalid tile/core extent skipped.
- Requested height integration range is empty.
- CRS is missing from EPT or cannot be simplified to EPSG.
- Polygon CRS differs from point cloud CRS.

## Recommended Adapter Error Envelope

Do not implement yet, but future adapter results should use a structured envelope
similar to:

```python
@dataclass(frozen=True)
class AdapterResult:
    outputs: dict[str, Path | float | np.ndarray]
    warnings: tuple[str, ...]
    metadata: dict[str, str | int | float]
```

For failures, raise plugin-owned exceptions such as:

```python
class PyForestScanAdapterError(Exception): ...
class PyForestScanInputError(PyForestScanAdapterError): ...
class PyForestScanProcessingError(PyForestScanAdapterError): ...
class PyForestScanOutputError(PyForestScanAdapterError): ...
```

Those plugin exceptions can then be translated consistently to
`QgsProcessingException` in Processing algorithms.
