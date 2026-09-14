# Polygon LiDAR Selection Regression Audit

Phase 27Q audited the history of polygon-to-LiDAR folder selection because real repositories could show files in the UI while Polygon Area Processing selected no files for execution.

## History Findings

- `20d1e15` (`Phase 27D`) introduced direct polygon-folder planning. It discovered LAS/LAZ/COPC sources and applied direct bounds overlap against the polygon bounds.
- `99d569b` (`Phase 27F`) moved polygon-folder processing into Batch while still using discovered real source paths for preflight and execution.
- `59f6611` (`Phase 27G`) added the SQLite/RTree LiDAR spatial catalog and changed polygon preflight toward catalog-backed selection.
- Phases 27I through 27P improved indexing, EPT handling, catalog integrity, CRS assignment, and QGIS map actions, but ordinary folder selection still needed a direct correctness fallback when catalog rows were absent, stale, or CRS-inconclusive.

## Root Cause

The regression was not a scientific algorithm failure. It was a source-selection routing problem:

- the UI could identify a folder containing valid point-cloud files;
- the catalog path could return zero usable intersecting rows;
- preflight then treated zero catalog results as no coverage instead of cross-checking real headers;
- no direct file list reached polygon clipping or Batch execution.

## Phase 27Q Fix

Phase 27Q adds `DirectLidarFolderSelector` as a QGIS-free correctness reference and integrates it into polygon preflight:

- ordinary local repositories can run Direct Header Scan explicitly;
- automatic mode compares catalog results to direct header results;
- if catalog selection finds no files but direct header scan finds overlapping files, preflight uses the direct real paths;
- manifests record the selection method and direct-selection summary;
- `scripts/audit_polygon_lidar_selection.py` compares direct and catalog selection without modifying state by default.

## Remaining Manual Validation

Live QGIS validation is still required for a real Windows tester repository:

1. Select the LiDAR repository folder.
2. Select a polygon layer or vector file in the same effective CRS.
3. Run preflight in Automatic mode.
4. Confirm selected source paths are real LAS/LAZ/COPC files.
5. Run one small polygon batch and verify clipped-source and final-product outputs.

Do not record this as live-QGIS passed until those steps are executed in QGIS.

## Phase 27R Notes

Phase 27R adds the stabilized ordinary-folder contract: direct header metadata is the beta correctness reference, catalogs are optional optimization, selected real paths are serialized and invariant-checked before PBM clipping, and EPT remains a separate logical-source path. See [Polygon LiDAR Stabilization](POLYGON_LIDAR_STABILIZATION.md).
