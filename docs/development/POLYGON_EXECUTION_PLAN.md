# Polygon Execution Plan

`PolygonExecutionPlan` is the Phase 27N preflight authority for Polygon Area Processing. Preflight builds it, manifests serialize it, and execution consumes the selected sources from the same report.

## Contents

- repository identity
- polygon spatial context and normalization report
- source selection result
- selected products
- shared Batch options
- polygon finalization options
- requested and effective concurrency
- spatial read, masking, output, and loading plans
- workload estimate
- structured warnings and blockers
- validation results
- deterministic plan signature

## Plan Signature

The signature includes repository identity, polygon geometry hash, CRS, products, Batch options, mask options, output folder, and backend readiness. When polygon, repository, products, settings, or output folder change, a new preflight produces a new signature.

Run buttons should only execute a current plan. The current implementation records and displays the signature; fuller stale-plan blocking across saved workspaces remains a follow-up.

## Phase 27O Notes

Repository discovery, catalog identity, catalog integrity, repair, source-view, coverage-model, diagnostic-export, and repository action-state services now back Polygon Area Processing setup. Broken catalogs are reported as catalog repair/readiness issues instead of generic no-coverage results. The RTree contract is `id, xmin, xmax, ymin, ymax`; EPSG:6635 overlap fixtures cover the observed polygon envelope regression.

## Phase 27Q Notes

Polygon Area Processing can now compare the catalog path with Direct Header Scan for ordinary local LAS/LAZ/COPC repositories. Catalogs remain the performance path, but Direct Header Scan is the correctness fallback when catalog selection is missing or inconclusive. EPT keeps native logical-source handling. See [Polygon LiDAR Selection Contract](POLYGON_LIDAR_SELECTION_CONTRACT.md) for the developer contract and [Process LiDAR Folder by Polygon](../user-guide/polygon-folder-processing.md) for user-facing guidance.

## Phase 27R Notes

Phase 27R adds the stabilized ordinary-folder contract: direct header metadata is the beta correctness reference, catalogs are optional optimization, selected real paths are serialized and invariant-checked before PBM clipping, and EPT remains a separate logical-source path. See [Polygon LiDAR Stabilization](POLYGON_LIDAR_STABILIZATION.md).

## Phase 27S CRS Manifest Fields

Polygon execution plans and manifests record original polygon CRS, transformed polygon CRS, repository CRS, EPT query CRS, clipping polygon CRS, processing CRS, output CRS, CRS resolution source, and transformation status separately. Incomplete CRS strings are rejected before plan signatures are produced.

## Phase 28D reliability
Large polygon requests are classified from raster dimensions. Automatic execution has no fixed one-hour wall limit; scientifically equivalent tiling remains subject to a product-specific review.
