# Phase 32K Bounded EPT Execution

## Live root cause

Attempt `20260828T212732242157Z-ac7630f9` launched PBM coordinator PID 32152 and stopped before its pilot or scheduler. The durable snapshot remained at `Assessing Source: Inspecting Ground Returns`, with 221 candidate areas, 109 required areas, 112 skipped areas, and zero attempted areas.

`_execute_source_aware_chm` called `_prepare_source_dependency` before constructing `PolygonProductWorkScheduler`. That function passed the union of every work-unit read extent to `prepare_durable_source`. `prepare_request_source` then called `ClassificationInspectionService.inspect` without bounds. Its EPT pipeline was:

```json
{"pipeline":[{"type":"readers.ept","filename":".../ept.json"},{"type":"filters.head","count":10000}]}
```

`filters.head` did not constrain EPT hierarchy traversal. The next planned operation would also have created one polygon-wide prepared LAZ, with `filters.crop` after `readers.ept`. The bounded 20-hectare canary succeeded because it used the separate work-unit read path; its evidence was not authoritative for the production preparation path.

## Repaired contract

Large EPT CHM preparation is now logical, not physical. The first required work unit supplies a representative bounded assessment. `ClassificationInspectionService` places the bounds directly on `readers.ept`:

```json
{"pipeline":[{"type":"readers.ept","filename":".../ept.json","bounds":"([xmin,xmax],[ymin,ymax])"},{"type":"filters.head","count":50000}]}
```

The resulting `source_preparation/<source-id>/pilot_result.json` and `status.json` record the work-unit ID, bounds, dimensions, classification counts, class-2 count and proportion, elapsed time, reader method, selected HAG method, and required work-unit count. They explicitly record `source_wide_materialization: false`.

The bounded evidence preserves strategy precedence: a sampled, varying `HeightAboveGround` dimension selects `existing_normalized_height`; otherwise usable class-2 ground selects `classified_ground_delaunay`. The selected method is computed independently in every bounded work unit, and the backend validates the actual bounded values or point geometry before execution.

Oversized frozen parent units retain their original scheduler identity but execute as 100 m core child reads with a 50 m halo on every side, capping each EPT request at 200 m. Every child runs in a fresh managed PBM Python process with the canonical conda DLL/GDAL/PROJ environment, writes its TIFF and checksum checkpoint immediately, and releases all native state on exit. Child cores mosaic into the original parent buffered tile; the parent then follows the unchanged core extraction and checkpoint path. The 50 m science buffer, 1 m global raster grid, final mosaicing, exact polygon mask, sequential concurrency, and 109-parent scheduler contract are unchanged.

The first real large-plan read extent (`196138.631177,2167029.3494` to `197308.631177,2168199.3494`) was sampled through PBM in 14.704 seconds. The bounded request returned 50,000 points, 4,122 class-2 returns (8.244%), and a `HeightAboveGround` dimension. This verifies network access, reader-level bounds, and the evidence needed to choose the existing-HAG path. It is not a substitute for the required three-tile QGIS gate.

EPT and CoPC bounds are also applied at reader level in the general preparation pipeline. LAS/LAZ keeps its existing bounded crop behavior.

## Progress and recovery

Coordinator snapshots now expose `PILOT_STARTED`, `HAG_STRATEGY_RESOLVED`, `PILOT_COMPLETED`, and `WORK_UNIT_SCHEDULER_STARTED`. Existing scheduler statuses and per-unit product checkpoints remain the recovery authority. A valid pilot tile is reused when the scheduler begins and on a matching restart.

The QGIS-side observer tracks stage, attempted, completed, failed, and current-work-unit transitions separately from heartbeat updates. After 120 seconds without measurable forward progress it writes `stall_snapshot.json` and reports `No forward processing progress`; it does not automatically terminate scientific work.

The stale live coordinator was positively identified as managed backend PID 32152, terminated with its process tree, and marked `FAILED_STALLED`. Its heartbeat is closed.

## Live large-plan evidence

The managed-runtime large-plan gate used the preserved 109-parent plan in `D:\tmp\pyforestscan_phase32k_live\large\batch\ept-full_09`. The pilot selected validated existing HAG, parent 1 completed, and `WORK_UNIT_SCHEDULER_STARTED` immediately advanced the full plan. Four parent units completed with 144 child checkpoints each:

| Parent | Seconds | Parent TIFF bytes | SHA256 |
| --- | ---: | ---: | --- |
| `wu-40cb5f0be7-0001` | 422.30 | 4,126,949 | `1f8b7c68a29b04583c57921e1fb5de81da7d52710cc7c61f85660609a2f5b420` |
| `wu-40cb5f0be7-0002` | 413.20 | 4,152,229 | `bf181fbaf85fd3d24c2d04e4456b8c9abe99ff19187143f1fa957a90d95a2d71` |
| `wu-40cb5f0be7-0003` | 392.38 | 3,745,406 | `296767f751c69e83a954e359ece3d78db974038c651c41e5236834a3db68fbcd` |
| `wu-40cb5f0be7-0004` | 377.64 | 3,420,961 | `931ea82f7f21561b97943c29a63e8d7227383a22bf420e9fd2f7256752329e18` |

The process was stopped after unit 3, then restarted against the same workspace. Reconciliation reported three recovered parents, reused the pilot and prior child checkpoints, and completed unit 4 without recomputing units 1-3. The process was stopped again after the scheduler advanced to unit 5; no PBM Python process remained.

## Remaining live gate

Automated tests prove reader-level EPT bounds, no source-wide EPT materialization, 109-unit contract persistence, bounded child sizing and reuse, lifecycle markers, watchdog diagnostics, and adjacent durable-preparation behavior. The large-plan first-three and resume gates pass in the managed runtime. A complete small-polygon run, final mask/output registration, layer load, and full default-profile QGIS UI run remain pending because this uncommitted package does not match the existing Processing Engine setup marker and Phase 32K forbids mutating engine state. No claim is made for those pending gates.
