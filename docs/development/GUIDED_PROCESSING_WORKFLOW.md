# Guided Processing Workflow

Phase 27N introduces a reusable guided workflow model for Polygon Area Processing.

## Steps

1. Data: choose LiDAR data and resolve repository identity.
2. Area: choose or normalize a polygon area.
3. Outputs: choose products.
4. Settings: choose output folder and common quality settings.
5. Review: validate the execution plan.
6. Results: run, monitor progress, and load outputs.

The Batch page now shows a compact step indicator and a structured Polygon Processing Review before the raw technical report.

## Processing Profiles

Guided mode uses profiles instead of making users reason about worker topology:

- Conservative: lower concurrency for network storage and memory-sensitive work.
- Recommended: balanced default.
- Performance: higher concurrency for tested fast local storage.
- Custom: exposes detailed worker settings.

Specialist controls remain under Advanced Batch Options and Polygon Finalization.

## Phase 27O Notes

Repository discovery, catalog identity, catalog integrity, repair, source-view, coverage-model, diagnostic-export, and repository action-state services now back Polygon Area Processing setup. Broken catalogs are reported as catalog repair/readiness issues instead of generic no-coverage results. The RTree contract is `id, xmin, xmax, ymin, ymax`; EPSG:6635 overlap fixtures cover the observed polygon envelope regression.

## Phase 27P Notes

Catalog health now separates embedded CRS from effective CRS. A bounded LAS/LAZ catalog with all source CRS values missing is `CRS Assignment Required`, not healthy, and polygon preflight does not report true no coverage until comparable CRS metadata exists. Repository CRS override metadata is explicit and reversible. Live QGIS coverage/zoom services now require actual layer insertion or canvas extent changes before reporting success.

## Phase 27Q Notes

Polygon Area Processing can now compare the catalog path with Direct Header Scan for ordinary local LAS/LAZ/COPC repositories. Catalogs remain the performance path, but Direct Header Scan is the correctness fallback when catalog selection is missing or inconclusive. EPT keeps native logical-source handling. See [Polygon LiDAR Selection Contract](POLYGON_LIDAR_SELECTION_CONTRACT.md) for the developer contract and [Process LiDAR Folder by Polygon](../user-guide/polygon-folder-processing.md) for user-facing guidance.
