# Real EPT Polygon Validation

This checklist is for manual Windows/QGIS validation and must not be treated as passed unless run against the real dataset.

1. Install the current ZIP in a clean QGIS profile.
2. Verify PBM Backend is READY.
3. Select the EPT root, `ept.json`, or `ept-data`.
4. Confirm Mission Control normalizes to one logical `ept.json` source.
5. Select one EPSG:6635 polygon feature.
6. Run polygon preflight.
7. Confirm one logical input, PBM Ready, spatial alignment status, and no high-confidence 110-billion-point estimate.
8. Run CHM.
9. Confirm named stages progress through polygon input preparation and product generation.
10. Confirm the previous `No such polygon file: Polygon (...)` error does not occur.
11. Open the job folder and verify `inputs/clipping_polygon.gpkg` or `inputs/clipping_polygon.geojson` exists.
12. Confirm the output is limited to the requested area and loads into QGIS.

Record QGIS version, Windows version, package SHA256, backend status, screenshots, output path, and any blockers.
