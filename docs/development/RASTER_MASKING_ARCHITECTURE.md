# Raster Masking Architecture

Polygon Area Processing often generates a rectangular raster for the polygon envelope. Phase 27M finalizes polygon raster products by applying the exact selected Polygon or MultiPolygon before the result is registered.

## Pipeline

1. Validate the polygon request and CRS.
2. Query or subset the LiDAR repository by the polygon envelope.
3. Generate the product raster.
4. Close and validate the raster writer.
5. Apply the exact polygon mask.
6. Validate the masked raster.
7. Write mask metadata.
8. Register the final output in `generated_outputs.json`.
9. Optionally load the final output into QGIS from the UI thread.

The GeoTIFF remains rectangular because rasters are grids. Cells outside the polygon, including holes, become NoData.

## Engines

`pyforestscan_qgis/core/raster_mask.py` exposes two service boundaries:

- `BackendRasterMaskService`: uses rasterio/shapely where available, writes through an atomic temporary file, preserves bands/descriptions/tags, supports crop-to-envelope, `all_touched`, NoData, and retained intermediates.
- `QgisRasterMaskService`: normalizes the QGIS/GDAL `gdal:cliprasterbymasklayer` parameter contract. It verifies algorithm availability when QGIS Processing is present and builds explicit parameters for INPUT, MASK, NODATA, CROP_TO_CUTLINE, KEEP_RESOLUTION, OUTPUT, and extra GDAL flags.

Automatic policy favors backend finalization for PBM-produced rasters so Results only sees completed scientific outputs. QGIS/GDAL remains a supported selectable/recovery path inside QGIS.

## Metadata

Masked rasters record tags such as:

- `pyforestscan_polygon_clip`
- `pyforestscan_polygon_crs`
- `pyforestscan_processing_crs`
- `pyforestscan_mask_engine`
- `pyforestscan_mask_nodata`
- `pyforestscan_mask_all_touched`
- `pyforestscan_mask_crop_to_polygon_extent`

## Failure Semantics

The default mask failure policy is `fail_product`. This prevents a rectangular unmasked envelope raster from appearing as a successful polygon result. If retained for diagnostics, unmasked intermediates are not registered as primary Results outputs.
