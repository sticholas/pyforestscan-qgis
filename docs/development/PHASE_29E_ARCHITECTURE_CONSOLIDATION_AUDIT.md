# Phase 29E Architecture Consolidation Audit

Status labels: **Authoritative**, **Compatibility only**, **Historical**, **Remove candidate**.

| Subsystem | Classification and implementation |
|---|---|
| Repository detection/preparation | **Authoritative:** `lidar_repository_discovery`, `repository_actions`; catalog stack is authoritative only for indexed folders. |
| EPT | **Authoritative:** `ept_repository`, `ept_spatial_reference`, bounded PDAL reads. Older subset helpers are **compatibility only** for Advanced Toolbox extraction. |
| LAS/LAZ metadata/source selection | **Authoritative:** `lidar_source_metadata`, `direct_lidar_selection`, `source_aware_processing`; header verification is diagnostic. |
| Polygon/CRS | **Authoritative:** normalization, transport, source selection, and CRS alignment modules; UI geometry adapters are compatibility boundaries. |
| Adaptive/work-unit/resources | **Authoritative:** `adaptive_processing`, `source_aware_processing`, `resource_estimation`, scheduler. Pilot planning is advisory, not a second planner. |
| HAG/science | **Authoritative:** `hag_strategy`, adapter/PyForestScan and work-unit execution. Coordinator contains no CHM formula. |
| PBM/coordinator/monitor/recovery | **Authoritative:** backend execution, durable coordinator, processing monitor, checkpoint/recovery. External worker is disabled **compatibility only**. |
| Mosaic/mask/output | **Authoritative:** raster mosaic plan, raster mask, product capabilities, output registry. Folder scanning is not authoritative for current Results. |
| Session/current/history | **Authoritative:** project session, active job controller, processing identity. Workspace models remain project/session support rather than duplicate job ownership. |
| Advisor/environment/provider/help | **Authoritative:** knowledge engine, dependency check/backend service, processing provider, contextual help registry. |
| Release tooling | **Authoritative:** package, package validation, release validation, docs/help checks. Phase audits are **historical** evidence. |

No module was deleted merely for having an older phase origin. The stale Phase 1 docstring in `output_loader.py` is a **remove candidate** for a later documentation-only cleanup because live QGIS loading now occurs through compatibility/UI integration. Hidden Mission Control page classes remain compatibility state for saved navigation and are not active workflow authorities.

## Execution invariants

Fast and durable paths share request/product/HAG/CRS/resolution/grid/mask/output contracts and the scientific adapter. They differ only in orchestration, checkpointing, partitioning, and mosaicking. Recovery validates signatures/checksums and cannot bypass output validation. Current results require complete current-attempt registry records.
