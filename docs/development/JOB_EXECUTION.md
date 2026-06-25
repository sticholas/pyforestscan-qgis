# Job Execution Framework

Phase 8A introduces the execution framework that future scientific processing
will use. The implementation is dry-run only: it validates a Product Planner JSON
report, simulates lifecycle progress, writes a job summary JSON file, and records
job history in Mission Control.

It does not call PyForestScan calculations and does not create rasters, point
clouds, vectors, or metric products.

## Architecture

```mermaid
flowchart TD
    A["Mission Control Processing page"] --> B["JobManager"]
    B --> C["Product Planner JSON validation"]
    B --> D["Dry-run status lifecycle"]
    B --> E["Job summary JSON"]
    B -."future".-> F["PyForestScanAdapter"]
    F -."future".-> G["PyForestScan public API"]
```

The manager is plain Python and has no QGIS imports. Mission Control bridges its
job updates into Qt widgets through an event sink.

## Core Modules

- `pyforestscan_qgis/core/jobs.py`: immutable job records, status enum, progress,
  log, result, and request objects.
- `pyforestscan_qgis/core/job_manager.py`: dry-run job lifecycle, validation,
  cancellation request handling, and event emission.
- `pyforestscan_qgis/core/job_results.py`: JSON serialization and summary file
  writing.

## Status Lifecycle

Supported statuses are:

- `pending`
- `validating`
- `running`
- `cancelling`
- `cancelled`
- `failed`
- `completed`

A normal dry-run moves through `pending`, `validating`, `running`, and
`completed`. Invalid plans move to `failed` and still write a summary JSON file.
Cancellation can be requested while a job is active; because Phase 8A dry-runs
are synchronous and intentionally fast, cancellation is best-effort but the core
manager already supports the status transition.

## Dry-Run Inputs

Dry-run execution accepts a Product Planner JSON report. The manager requires:

- A JSON object at the top level.
- `processing_executed` set to `false`.
- At least one requested product.
- Requested products must include a product identifier.
- Blocked products are rejected before execution simulation.

## Dry-Run Outputs

The only file written by Phase 8A execution is:

- `<job_id>_job_summary.json`

The summary includes job status, progress, logs, requested products, result
artifacts, and explicit flags:

- `processing_executed: false`
- `scientific_outputs_created: false`

## Error Handling

`JobExecutionError` is raised for invalid requests during explicit job creation.
During `run_dry_run`, validation failures are captured into a failed `JobRecord`
and written to a summary JSON file so users have an auditable result.

## Future Extension

Future phases should add worker-based execution behind `JobManager` while
preserving the public job records and event sink. Scientific processing should
enter through the adapter boundary, not through Mission Control pages or QGIS
widgets directly.
