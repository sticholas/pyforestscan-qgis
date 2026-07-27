# Real Repository Action Validation

Use this checklist inside live Windows/QGIS. Do not mark an action passed until it is performed in QGIS with a real repository.

## Repository A And B

Test both the original LiDAR folder and a smaller independent LiDAR folder.

1. Select the folder.
2. Run Inspect Repository and record supported file counts.
3. View source table and confirm valid/problem rows.
4. Run Scan File Headers.
5. Confirm valid header count, metadata error count, and RTree count.
6. Add Coverage to Map.
7. Zoom to Repository Extent.
8. Select a polygon inside coverage and Re-run Preflight.
9. Confirm candidate sources are selected.
10. Select a polygon outside coverage and confirm true No Coverage.
11. Run Update Catalog after adding, changing, and removing a file.
12. Pause a rebuild after the current chunk.
13. Resume the paused catalog build.
14. Move Catalog Local and confirm the active mapping.
15. Open Catalog Folder and confirm the catalog directory opens.
16. Preview Spatial Selection.
17. Zoom to Polygon.
18. Zoom to Repository Extent.
19. Zoom to Combined Extent.
20. Reset Polygon Batch and confirm no stale plan remains.

Record pass/fail, screenshots needed, and exact reproduction steps for every failure.
