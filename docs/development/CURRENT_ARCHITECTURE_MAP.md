# Current Architecture Map

## Phase 31G scientific runtime

Mission Control builds requests in QGIS, `ProcessingEngineService` verifies and freezes runtime identity, `BackendExecutionService` launches managed Python, and backend runner modules execute science. `ScientificRuntimeBoundary` prevents QGIS Python from becoming an accidental second scientific runtime.

## Phase 31F runtime boundary

`ProcessingEngineVerifier` is the authoritative readiness boundary shared by preflight and execution. It probes `pyforestscan_qgis.backend_runner inspect_runtime_contract` through the exact managed executable used by `BackendExecutionService`. `processing_engine.json` provides fingerprinted quick discovery; it never overrides a changed environment.

Phase 31D adds `core/effective_source_spatial_profile.py` between source metadata and polygon selection. Folder and polygon paths then converge on shared preparation, execution, recovery, and output systems.

Phase 31A adds a PBM-owned LiDAR preparation layer between request validation and product adapters. Assessments, plans, bounded classification samples, prepared checkpoints, provenance, and recommendations are plugin-owned contracts; PyForestScan/PDAL perform ground and HAG operations.

Phase 30F adds protocol-level spatial-reference and height-normalization contracts plus PBM runtime self-identity. Job diagnostics record actual backend module locations and source-local execution stages.

## Phase 30C Batch launch boundary

Standard Batch treats UI preflight as a replaceable readiness projection. Process performs missing validation and freezes an immutable `BatchExecutionRequest` before status widgets change. The worker receives only the approved typed request. Advanced-control visibility is derived by `batch_control_visibility`; expandable groups hide one content container without mutating child applicability.

This is the current architecture index. Phase reports are historical evidence, not competing specifications.

| Responsibility | Authoritative implementation | Status of adjacent paths |
|---|---|---|
| Repository detection/preparation | `lidar_repository_discovery.py`, `repository_actions.py` | Catalog modules are indexed-folder support, not an alternate executor. |
| EPT and LAS/LAZ metadata | `ept_repository.py`, `ept_spatial_reference.py`, `lidar_source_metadata.py` | Header verification is compatibility/diagnostics. |
| Polygon and CRS | `polygon_normalization.py`, `crs_alignment.py`, `polygon_source_selection.py` | QGIS adapters only acquire geometry. |
| Adaptive/work-unit planning | `adaptive_processing.py`, `source_aware_processing.py` | `pilot_planning.py` is advisory; no live identity-changing replan. |
| Resources and HAG | `resource_estimation.py`, `hag_strategy.py` | Shared by direct and durable paths. |
| Scientific products | `adapter.py`, `chm_work_unit_execution.py`, `localized_rumple.py`, `product_capabilities.py` | Coordinator orchestrates and does not implement CHM or Rumple math. Spatial Rumple is CHM-derived. |
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
# Phase 30B Additions

`processing_ui_state.py` owns processing control projection, `product_finalization.py` owns output-role semantics, `durable_errors.py` retains closed-dialog diagnostics, and `rumple_adaptive.py` plus `rumple_raster_io.py` own adaptive Rumple grid/scalar behavior.
# Phase 30D additions

- `core.pipeline_results`: product validation severity and stage observability.
- `core.automatic_execution`: source-level automatic scheduling policy.
- `core.batch_preflight`: fresh-job manifest isolation.
- `core.batch_runner`: requested-product persistence and scientific-output filtering.
# Phase 30E additions

- `core.spatial_reference_resolver`: authoritative evidence, normalization, consensus, assignments, and source-local decisions.
- `core.product_crs_capabilities`: product-specific named/source-local CRS policy.
- `core.adapter`: PDAL source-local read and unassigned GeoTIFF provenance for CHM/Rumple.
- `core.crs_alignment`: retained exact polygon transformation once source and target CRS resolve.
- `core.spatial_assignment`: typed units, scope, provenance, fingerprints, and compact spatial profiles.
- `core.output_spatial_assignment`: non-destructive CRS registration for a copied source-local raster.
- `backend_runner.pbm_lidar_preparation`: cached classification evidence, unit-aware parameters, bounded ground coverage, and durable HAG.
