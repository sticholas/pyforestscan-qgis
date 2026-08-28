# Source-aware processing architecture

## Unified managed runtime

Source-aware CHM/Rumple and logical polygon products such as PAI, PAD, FHD, and Canopy Cover now share the same frozen-token launch contract. The route is recorded as `polygon_managed_engine`; there is no product-specific QGIS-Python or legacy backend fallback after Prerun.

## Bounded local prepared sources

For local LAS/LAZ, each frozen area is read with `readers.las` plus `filters.crop`; for COPC the reader receives native bounds. This adapter boundary is required because PyForestScan 0.1.x applies its `bounds` argument only to EPT. Rumple consumes the buffered CHM and performs no second point-cloud read.

Large local CHM/Rumple execution now has a source-preparation dependency before canary and tiled work. Work units read a single validated local `prepared_hag.laz`, while retaining original/prepared paths in diagnostics. EPT remains on its logical bounded-work-unit path and is not fully materialized.

Local LAS CHM/Rumple plans now enter the durable PBM coordinator directly instead of first clipping through QGIS Python. Work-unit identity is described in [Global Work Unit Identity](GLOBAL_WORK_UNIT_IDENTITY.md), and alternative source representations in [Source Alternative Detection](SOURCE_ALTERNATIVE_DETECTION.md).

## Phase 29D performance contract

The adaptive planner and executor share one point-memory model. Direct one-unit requests bypass durable unit/mosaic overhead. Larger EPT CHM jobs launch one PBM coordinator, not one Python process per unit; the coordinator owns bounded scheduling and recovery. Native files remain first partitions and are subdivided only when file size or estimated point/raster memory exceeds the adaptive budget. Plan diagnostics report execution path, output cells, units, concurrency, estimated peak memory, and buffered-read amplification.

Phase 28E-Stabilization adds one-worker EPT CHM safe mode, inspect-first HAG suitability, deterministic failure circuit breaking, and crash-safe work-unit transitions. See [Crash-Safe Work Scheduler](CRASH_SAFE_WORK_SCHEDULER.md).

```mermaid
flowchart LR
  A[Repository identity] --> B[Native source selection]
  B --> C[Global aligned raster grid]
  C --> D[Bounded work units]
  D --> E[HAG suitability and strategy]
  E --> F[PBM CHM core tiles]
  F --> G[Verified checkpoints]
  G --> H[Transactional mosaic]
  H --> I[Exact polygon mask]
  I --> J[Current-attempt registry]
```

Partitions are execution constructs. Existing LAS/LAZ files remain native sources and adjacent small files may be grouped. Large files may receive bounded subrequests. EPT remains one logical `ept.json`; work units are independent bounds requests and never hierarchy-node jobs. COPC uses footprints across files and bounded reads within unusually large files.

CHM is the only partition-enabled product in beta. It uses one grid, buffered reads, retained cores, deterministic first-valid core mosaicing, and final exact masking. Other products retain existing execution until their merge mathematics are reviewed.

## Phase 28F contracts

EPT remains one logical source. CHM uses bounded buffered rectangles, aligned cores, mosaic, then one exact mask. Memory estimates include point and native overhead.


## Phase 28G Exact Polygon Completion

Exact-polygon planning now separates envelope candidates, required cores, and geometry-excluded cores. See [Exact Polygon Work-Unit Filtering](EXACT_POLYGON_WORK_UNIT_FILTERING.md).


## Phase 28H Adaptive Scale and Compact Workspace

Phase 28H replaces fixed EPT scale with the workload-derived [Adaptive Processing Planner](ADAPTIVE_PROCESSING_PLANNER.md). Native partitions remain authoritative, exact polygon filtering remains downstream, and small-safe requests bypass tiled finalization.
# Rumple

The source-aware coordinator accepts CHM-only, Rumple-only, and CHM-plus-Rumple plans. LiDAR and CHM work are shared. Rumple cores use a one-cell CHM dependency halo and one authoritative global output grid.
