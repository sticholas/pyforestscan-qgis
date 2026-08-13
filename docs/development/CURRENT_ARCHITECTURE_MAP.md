# Current Architecture Map

This is the current architecture index. Phase reports are historical evidence, not competing specifications.

| Responsibility | Authoritative implementation | Status of adjacent paths |
|---|---|---|
| Repository detection/preparation | `lidar_repository_discovery.py`, `repository_actions.py` | Catalog modules are indexed-folder support, not an alternate executor. |
| EPT and LAS/LAZ metadata | `ept_repository.py`, `ept_spatial_reference.py`, `lidar_source_metadata.py` | Header verification is compatibility/diagnostics. |
| Polygon and CRS | `polygon_normalization.py`, `crs_alignment.py`, `polygon_source_selection.py` | QGIS adapters only acquire geometry. |
| Adaptive/work-unit planning | `adaptive_processing.py`, `source_aware_processing.py` | `pilot_planning.py` is advisory; no live identity-changing replan. |
| Resources and HAG | `resource_estimation.py`, `hag_strategy.py` | Shared by direct and durable paths. |
| Scientific products | `adapter.py`, `chm_work_unit_execution.py`, `product_capabilities.py` | Coordinator orchestrates and does not implement CHM math. |
| PBM and durable coordination | `backend/execution.py`, `backend_runner/polygon_job_coordinator.py`, `backend_runner/job_coordinator.py` | External workers remain disabled. |
| Recovery/progress | `work_unit_scheduler.py`, `job_recovery.py`, `processing_monitor.py` | Checkpoints are authoritative, UI is observer only. |
| Mosaic/mask | `raster_mosaic_plan.py`, `raster_mask.py` | Product contract defines semantics. |
| Outputs/results | `output_registry.py`, `output_loader.py` and QGIS compatibility loader | Registry, never folder scanning, defines current outputs. |
| Current job/session | `active_job.py`, `job_identity.py`, `project_session.py` | Historical jobs require explicit promotion. |
| Advisor/readiness | `knowledge/`, `dependency_check.py`, `backend/service.py` | QGIS Python is fallback when PBM is ready. |
| Processing provider/help | `processing_provider.py`, `algorithms/advanced/`, `ui/help_system.py` | Advanced Toolbox remains supported. |
| Package/release | `scripts/package_plugin.py`, `validate_plugin_package.py`, `validate_release.py` | Benchmark scripts are developer-only and excluded. |

```mermaid
flowchart LR
 A["User request"] --> B["Current job identity"] --> C["Repository and area resolution"] --> D["Adaptive source-aware plan"] --> E["PBM coordinator"]
 E --> F["Single-request fast path or durable work units"] --> G["Shared scientific adapter"] --> H["Verified core/output"] --> I["Mosaic when required"] --> J["Exact mask"] --> K["Output registry"] --> L["Current Results"] --> M["QGIS loading"]
```
