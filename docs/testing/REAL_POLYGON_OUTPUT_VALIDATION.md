# Real Polygon Output Validation

This checklist validates the full Phase 27M polygon output path in a live QGIS/PBM environment. The headless unit suite validates request contracts, output registry behavior, and synthetic raster masking where rasterio is available, but live QGIS loading and real EPT processing must be recorded separately.

## Manual QGIS Checklist

1. Install the current ZIP in a controlled QGIS profile.
2. Confirm PBM backend is Ready.
3. Open Mission Control > Batch.
4. Choose Polygon Area Processing.
5. Choose an EPT repository and prepare or register the repository.
6. Choose `permit_polygon2` or another known polygon feature.
7. Select CHM.
8. Enable Exact raster mask, Crop raster to polygon extent, and Load generated outputs into QGIS.
9. Run preflight and confirm requested/effective concurrency is shown.
10. Run Polygon Batch.
11. Confirm CHM generation, mask finalization, output registration, and automatic loading.
12. Confirm cells outside the polygon and polygon holes are NoData.
13. Click Load Generated Outputs again and confirm no duplicate layer is created.

## Scripted Diagnostics

Use `scripts/validate_real_polygon_output_workflow.py` to inspect an existing output registry or mask an existing raster. The script does not run network EPT products unless explicit product paths are supplied by the tester.

Example:

```bash
python3 scripts/validate_real_polygon_output_workflow.py --print-output-registry --output-folder /path/to/job
python3 scripts/validate_real_polygon_output_workflow.py --mask-existing-raster --raster /path/chm.tif --polygon-wkt "POLYGON (...)" --polygon-crs EPSG:32610
```

## Evidence To Record

- ZIP path and SHA256.
- Commit hash.
- QGIS and Windows versions.
- PBM status.
- Product path, registry path, mask engine, NoData value, and load result.
- Whether live QGIS loading and live EPT polygon masking passed.
