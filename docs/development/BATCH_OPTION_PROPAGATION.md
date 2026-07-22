# Batch Option Propagation

Phase 27M defines one shared Batch option model for Standard File Batch and Polygon Area Processing. The UI still keeps Guided mode compact, but execution receives a typed `BatchExecutionOptions` object and records requested versus effective values in polygon manifests.

## Shared Model

`pyforestscan_qgis/core/batch_options.py` owns:

- `BatchExecutionOptions`: shared execution, retry, overwrite, loading, diagnostics, temporary workspace, memory/chunk, raster output, and conflict-policy settings.
- `PolygonBatchOptions`: polygon-only raster finalization settings, including exact masking, mask engine, `all_touched`, crop-to-envelope, intermediate retention, and mask failure policy.
- `BatchOptionApplicability`: human-readable explanations for options that are constrained by source type or product mix.

## Propagation Matrix

| Option | UI Control | Model Field | Manifest Field | Consumer | Standard Batch | Polygon LAS/LAZ | Polygon EPT/COPC |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Execution mode | Advanced Batch Options > Execution mode | `run_sequentially` | `shared_execution_options.run_sequentially` | Batch runner/executor | Yes | Yes | Yes, with logical-source guardrails |
| Max workers | Advanced Batch Options > Max workers | `maximum_parallel_jobs`, `worker_count` | `concurrency` | Scheduler/preflight diagnostics | Yes | Yes | Effective value may be reduced |
| Stop on error | Stop batch when a file fails | `continue_on_error` | `shared_execution_options.continue_on_error` | Batch executor | Yes | Yes | Yes |
| Retry failed | Retry failed files only | `retry_failed_jobs`, `maximum_retry_attempts` | `shared_execution_options.retry_failed_jobs` | Resume/retry paths | Yes | Yes | Yes |
| Skip completed | Skip already-completed files on resume | `skip_existing`, `reuse_existing_outputs` | `shared_execution_options.skip_existing` | Output conflict handling | Yes | Yes | Yes |
| Overwrite existing | Overwrite existing outputs | `overwrite_existing`, `output_conflict_policy` | `shared_execution_options.output_conflict_policy` | Output reservation/finalization | Yes | Yes | Yes |
| Load outputs | Load generated outputs into QGIS | `load_outputs_after_completion` | `shared_execution_options.load_outputs_after_completion` | Results/QGIS loading on UI thread | Yes | Yes | Yes, after final mask |
| Exact raster mask | Polygon Finalization | `PolygonBatchOptions.exact_raster_mask` | `polygon_options.exact_raster_mask` | Raster mask service | Not applicable | Yes | Yes |
| Mask implementation | Polygon Finalization | `PolygonBatchOptions.mask_engine` | `polygon_options.mask_engine` | Mask service selection | Not applicable | Yes | Yes |
| Crop/all touched | Polygon Finalization | `crop_to_polygon_extent`, `all_touched` | `polygon_options` | Raster mask service | Not applicable | Yes | Yes |
| Retain intermediate | Polygon Finalization | `retain_unmasked_intermediate` | `polygon_options` | Mask finalization | Not applicable | Yes | Yes |
| Mask failure policy | Polygon Finalization | `mask_failure_policy` | `polygon_options.mask_failure_policy` | Polygon completion status | Not applicable | Yes | Yes |

## Requested Versus Effective Concurrency

The requested value is the user’s configured maximum concurrent logical jobs. The effective value is the safe value after source/product constraints are applied. A single EPT or COPC product remains one logical job; Mission Control must not split EPT hierarchy nodes into fake workers. Multiple independent polygons or products may increase effective concurrency when output paths and memory limits allow it.

## Output Loading Boundary

Automatic loading is a UI-side action after product generation, exact masking, metadata writing, and output registration. PBM never calls QGIS layer APIs.
