# Real Ordinary LiDAR Polygon Validation

Use this checklist for Phase 27R live validation on the user's QGIS system.

Do not mark a test passed unless it was actually executed in QGIS.

## Artifact

Record:

- ZIP path;
- ZIP SHA256;
- commit hash;
- QGIS version;
- Windows version;
- PBM backend status;
- repository path;
- polygon source;
- repository CRS assignment source.

## Test A: Small Ordinary Folder

1. Install the plugin ZIP.
2. Open Mission Control > Batch > Polygon Area Processing.
3. Choose a small LAS/LAZ/COPC folder.
4. Click Inspect Folder.
5. Confirm actual filenames appear in diagnostics or source view.
6. Assign repository CRS if headers lack embedded CRS.
7. Select a known-overlapping Polygon or MultiPolygon.
8. Click Find LiDAR for This Area / Run Preflight.
9. Confirm Intersecting LiDAR files is greater than zero.
10. Click Show Selected Files on Map.
11. Confirm a `PyForestScan - Selected LiDAR` group with selected file footprints and selected polygon.
12. Run CHM.
13. Confirm PBM receives selected paths through clipping, not the whole folder.
14. Confirm the final raster is masked to the exact polygon.
15. Load outputs through Results.

## Test B: Original Ordinary Folder

Repeat Test A using the user's original ordinary folder. Capture any discrepancy between direct metadata and catalog results.

## Test C: Irregular Polygon

Use a concave or irregular polygon known to overlap.

Expected:

- broad envelope selects candidate files;
- exact geometry clips and masks output;
- polygon shape does not cause zero-file selection.

## Test D: Outside Polygon

Use a polygon known to be outside the repository.

Expected:

- zero intersecting files;
- true No Coverage message;
- no PBM processing run is enabled.

## Test E: Catalog Comparison

With a catalog present:

- if catalog and direct metadata agree, either path may be used;
- if catalog returns zero but direct metadata finds files, direct metadata is used and catalog repair is recommended;
- if catalog and direct differ, direct metadata is used during beta.

## Evidence Table

| Test | Status | Notes | Screenshots / logs |
|---|---|---|---|
| A Small ordinary folder | Not run | | |
| B Original ordinary folder | Not run | | |
| C Irregular polygon | Not run | | |
| D Outside polygon | Not run | | |
| E Catalog comparison | Not run | | |
