# PyForestScan Advanced API Audit

Phase 20A reviewed the PyForestScan public API needed for expert Processing Toolbox algorithms. The plugin still treats PyForestScan as the computational engine and keeps direct calls behind the adapter boundary.

## Sources Reviewed

- Official calculate API: `https://pyforestscan.sefa.ai/api/calculate/`
- Official filters API: `https://pyforestscan.sefa.ai/api/filters/`
- Official handlers API: `https://pyforestscan.sefa.ai/api/handlers/`
- Official process API: `https://pyforestscan.sefa.ai/api/process/`
- Official pipeline API pages linked from the PyForestScan documentation.
- Usage pages for importing/preprocessing/writing data, Digital Terrain Models, and large point clouds.
- Existing Phase 3A local API audit for installed PyForestScan `0.4.0`.

The local QGIS Python executable was not available from this shell during Phase 20A, so the implementation is aligned with the official docs and the previously recorded installed `0.4.0` audit.

## Advanced Product API Mapping

| Product | Public PyForestScan calls | Output representation | Notes |
| --- | --- | --- | --- |
| CHM | `handlers.read_lidar(..., hag=True)`, `calculate_chm(arr, (x, y), interpolation, interp_valid_region, interp_clean_edges)`, `handlers.create_geotiff(...)` | Single-band GeoTIFF | Interpolation accepts `None`, `nearest`, `linear`, or `cubic`. |
| PAD | `read_lidar(..., hag=True)`, `assign_voxels(arr, (x, y, z))`, `calculate_pad(voxel_returns, voxel_height, beer_lambert_constant, drop_ground)` | Multi-band GeoTIFF written by plugin adapter | One band per vertical bin. |
| PAI | `assign_voxels`, `calculate_pad`, `calculate_pai(pad, voxel_height, min_height, max_height)`, `create_geotiff` | Single-band GeoTIFF | PAD remains an internal prerequisite unless the user runs PAD separately. |
| Canopy Cover | `assign_voxels`, `calculate_pad`, `calculate_canopy_cover(pad, voxel_height, min_height, max_height, k)`, `create_geotiff` | Single-band GeoTIFF | `min_height` is the canopy-height threshold. |
| FHD | `assign_voxels`, `calculate_fhd(voxel_returns, voxel_height, min_height, max_height)`, `create_geotiff` | Single-band GeoTIFF | Uses return-count voxels directly. |
| Rumple | `calculate_chm`, `calculate_rumple(chm, (x, y), min_height)` | CSV summary | PyForestScan returns a scalar rumple value, not a raster. |

## Height Above Ground / Normalization

PyForestScan exposes HAG primarily through `handlers.read_lidar`:

```python
read_lidar(input_file, srs, hag=True)
read_lidar(input_file, srs, hag_dtm=True, dtm="dtm.tif")
```

The handlers module also exposes `write_las(arrays, output_file, srs=None, compress=True)`. Phase 20A therefore implements an honest advanced HAG workflow:

1. Read the input lidar with HAG requested.
2. Optionally use DTM-backed HAG when the user supplies a DTM.
3. If the user provides a LAS/LAZ output path, write the returned point arrays through `write_las`.
4. If no output is provided, report that HAG was available in memory and explain the limitation.

The plugin does not fabricate unsupported normalized point-cloud formats. Future work should manually validate whether `write_las` preserves all required dimensions, scale/offset metadata, CRS metadata, compression behavior, and point attributes for the project’s target datasets.

## APIs Not Used Directly

- Private handler/pipeline helpers are not called from QGIS.
- `process.process_with_tiles` remains out of the Advanced Toolbox for now because it owns tiling, progress, output naming, and warnings internally.
- Visualization helpers remain outside Processing algorithms; QGIS styling is handled by plugin UI/integration helpers.
- Large point-cloud tiling utilities are not exposed until cancellation, progress, and memory behavior are designed for QGIS.

## Risk Notes

- Advanced settings are powerful and may create invalid or scientifically questionable combinations. Validation catches mechanical issues only; parameter interpretation remains the user’s responsibility.
- HAG quality depends on ground classification, DTM quality, and PDAL behavior. The plugin reports this clearly rather than claiming a universal normalization guarantee.
- PAD band semantics are vertical-bin order from PyForestScan output. The plugin does not yet write per-band height labels.
- Rumple remains scalar CSV because raster output would be scientifically misleading.
