# Workspace Timeline

Workspace timeline events provide a local audit-style narrative of a PyForestScan analysis. They are not QGIS project history and are not a scientific provenance replacement, but they give Mission Control enough memory to resume and explain what happened.

## Event Shape

Each event stores:

- `event_type`
- `message`
- `timestamp`
- `details`

Example:

```json
{
  "event_type": "dataset_explored",
  "message": "Dataset explored: plot.laz",
  "timestamp": "2026-06-30T10:15:00+00:00",
  "details": {
    "report": "/analysis/pyforestscan_runs/.../reports/dataset_report.html"
  }
}
```

## Current Event Types

- `workspace_created`
- `environment_refreshed`
- `dataset_selected`
- `dataset_explored`
- `planning_updated`
- `products_generated`
- `processing_failed`
- `batch_complete`

Future phases can add events such as `batch_resumed`, `results_reviewed`, `qa_reviewed`, and `publication_ready` without changing the file format.

## Rules

- Events are timestamped in UTC.
- Events are local-only.
- Events should use plain strings for details to keep JSON stable and readable.
- UI timeline viewers should treat the file as append-oriented and not require a database.
