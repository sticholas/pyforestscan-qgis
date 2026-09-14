# Phase 30B Real Rumple Output Analysis

The retained 130 ha run proved that backend completion and Mission Control finalization were distinct. The backend wrote a usable Rumple raster and scalar summary; presentation then raised `AttributeError` because `_set_batch_summary()` called the removed `BatchPage._batch_settings()` helper. That call entered in Phase 29B and had no implementation in the current architecture. Immutable execution options and durable plans replaced it.

## Redacted raster evidence

- GeoTIFF: 1324 x 1032, one Float32 band, EPSG:6635, 1 m cells.
- Bounds: 197779.46, 2235468.97, 199103.46, 2236500.97.
- NoData: -9999; valid cells: 1,299,973; NoData cells: 66,395.
- Minimum/maximum/mean/median: 1.0 / 10.684097 / 1.328385 / 1.029559.
- Percentiles 1/5/25/75/95/99: 1.0 / 1.0 / 1.010118 / 1.155688 / 3.135662 / 4.720161.
- Values below 1: zero.
- The earlier pre-mask scalar was 1.330454, about 0.156% above the exact-mask raster aggregate. Phase 30B now derives the published scalar blockwise from the final exact-mask raster.

The real data path is intentionally omitted. This evidence does not replace a fresh live QGIS acceptance run of the corrected package.
