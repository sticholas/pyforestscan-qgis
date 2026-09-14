# Phase 30F PBM Source-Local Regression

The release regression is a standalone LAS with X/Y/Z, `HeightAboveGround`, no CRS, and no polygon. The production target is `ohia_01_5m_norm.las` (about 58,017 points) with CHM and Rumple selected.

Automated coverage in `tests/test_phase30f_source_local_pbm.py` verifies JSON round trips, protocol identity subprocess execution, HAG aliases, mismatch diagnostics, source-local metadata, requested-product retention, and an optional real LAS scientific subprocess. The scientific test runs when `laspy`, PDAL, PyForestScan, Rasterio, and NumPy are available; otherwise it is explicitly skipped rather than reported as live evidence.

Manual PBM verification:

1. Inspect the LAS and confirm `HeightAboveGround` is listed and CRS is unknown.
2. Select CHM and Rumple without a polygon.
3. Run with PBM and verify both rasters plus `rumple_summary.csv`.
4. Open both rasters and confirm CRS is absent and source-local tags are present.
5. Confirm `source_local_trace.json` records `EXISTING_HAG` and the PBM-read dimensions.
6. Confirm `backend_module_locations.json` points to the installed current plugin.
7. Load outputs in QGIS; no project CRS is assigned by PyForestScan.

## Managed-backend evidence

On 2026-08-25 the installed Windows PBM Python executed a generated 64-point LAS through real PDAL, serialized PBM jobs, backend subprocesses, PyForestScan CHM/Rumple calculations, and Rasterio writers. CHM and Rumple both returned exit code 0. CHM was 7 x 7 with valid values 4.0 to 6.9314. Rumple was 6 x 6 with valid values 1.0136 to 1.3295. Both datasets opened with `crs=None`, source-local tags were present, and `rumple_summary.csv` existed. This validates the synthetic managed-backend path; the named 58,017-point production LAS still requires a clean QGIS run because it was not available at the tested filesystem locations.
