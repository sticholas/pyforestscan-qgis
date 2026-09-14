# Large-area processing audit

## Current path before Phase 28E

```mermaid
flowchart LR
  A[Polygon selection] --> B[Prerun and execution plan]
  B --> C[One PBM job]
  C --> D[read_lidar bounded by full polygon envelope]
  D --> E[Materialized PDAL arrays]
  E --> F[HAG normalization]
  F --> G[CHM calculation]
  G --> H[Raster write]
  H --> I[Exact mask]
  I --> J[Registry and Results]
```

The complete polygon point subset entered backend memory through `PyForestScanAdapter` and `pyforestscan.handlers.read_lidar`. The request enabled HAG before CHM rasterization. PyForestScan/PDAL materialized arrays for the full bounds; no durable product existed until raster writing. The parent could measure only process liveness. Partial work could not be saved, and Delaunay geometry failure could occur after a long network read.

Errors crossed the backend result boundary correctly, but Phase 28D monitor exceptions were all formatted as custom wall-time failures from `self.timeout_seconds`, including `None`. That could obscure a monitor cause. Scientific child errors were preserved only when the child completed and wrote its result.

## Phase 28E path

The planner reuses selected native sources, builds one grid, emits bounded units, and limits concurrency by source location and memory. Each PBM call materializes only one buffered work unit. A verified core raster and checksum are persisted immediately, then backend process memory is released. Finalization requires every core, transactional mosaic creation, exact masking, and current-job registration.

Progress is measurable at unit boundaries. Optional point/RSS/network metrics remain best-effort. HAG suitability models can reject rank-deficient samples before Delaunay when statistics are available; otherwise deterministic failures are isolated to one bounded unit and never retried identically.

## Phase 28F implementation evidence

# Large-area processing audit

## Current path before Phase 28E

```mermaid
flowchart LR
  A[Polygon selection] --> B[Prerun and execution plan]
  B --> C[One PBM job]
  C --> D[read_lidar bounded by full polygon envelope]
  D --> E[Materialized PDAL arrays]
  E --> F[HAG normalization]
  F --> G[CHM calculation]
  G --> H[Raster write]
  H --> I[Exact mask]
  I --> J[Registry and Results]
```

The complete polygon point subset entered backend memory through `PyForestScanAdapter` and `pyforestscan.handlers.read_lidar`. The request enabled HAG before CHM rasterization. PyForestScan/PDAL materialized arrays for the full bounds; no durable product existed until raster writing. The parent could measure only process liveness. Partial work could not be saved, and Delaunay geometry failure could occur after a long network read.

Errors crossed the backend result boundary correctly, but Phase 28D monitor exceptions were all formatted as custom wall-time failures from `self.timeout_seconds`, including `None`. That could obscure a monitor cause. Scientific child errors were preserved only when the child completed and wrote its result.

## Phase 28E path

The planner reuses selected native sources, builds one grid, emits bounded units, and limits concurrency by source location and memory. Each PBM call materializes only one buffered work unit. A verified core raster and checksum are persisted immediately, then backend process memory is released. Finalization requires every core, transactional mosaic creation, exact masking, and current-job registration.

Progress is measurable at unit boundaries. Optional point/RSS/network metrics remain best-effort. HAG suitability models can reject rank-deficient samples before Delaunay when statistics are available; otherwise deterministic failures are isolated to one bounded unit and never retried identically.

## Phase 28F implementation evidence

Confirmed defects were redundant Delaunay despite existing normalized heights, exact polygon cropping before HAG, unrealistic memory estimates, predictable temporary status files, and late PBM results left behind Running state.

Phase 28F enforces validated existing HAG with hag=False, rectangular buffered reads, realistic point/native/raster memory estimates, unique fsynced atomic files, late-result adoption, durable commands and progress, and representative pilot selection.

The real EPT windows, medium mosaic, QGIS restart, and full 120-unit run have not been rerun here and remain prerelease blockers.
