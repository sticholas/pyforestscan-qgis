# Localized Rumple Raster

Localized Rumple Raster is a PyForestScan QGIS extension, not the native PyForestScan `calculate_rumple` output.

The extension calculates Rumple separately over moving CHM windows. Each output cell represents the surface-area ratio for the local CHM neighborhood, subject to valid-data thresholds.

## Parameters

- Window width and height in CHM cells.
- Stride.
- Minimum valid CHM fraction.
- Optional minimum canopy height.
- NoData value.

## Scientific Behavior

- Flat CHM windows produce Rumple approximately 1.
- Corrugated CHM windows produce Rumple greater than 1.
- Windows with insufficient valid data produce NoData.

Window size strongly affects the result. Smaller windows are more local but noisier; larger windows smooth local structure. Boundary cells are generated only where a full window is available.

## Status

Phase 27D implements and tests the QGIS-free mathematical core. Full QGIS raster writing and Guided UI execution remain deferred until product QA approves window defaults and output handling.
