# Workspace Architecture

Phase 19A adds a local Workspace foundation for PyForestScan QGIS. A Workspace represents one analysis and records enough context for Mission Control to feel resumable without coupling state to a QGIS project.

This is local-only infrastructure. It is not cloud sync, accounts, a database, or QGIS project manipulation.

## Storage Location

Each output root can contain a hidden workspace folder:

```text
<output_folder>/
  .pyforestscan/
    workspace.json
    session.json
    timeline.json
    notes.md
    history.json
    recent.json
    version.json
```

The existing per-run folders remain unchanged:

```text
<output_folder>/pyforestscan_runs/<timestamp_dataset>/
```

The workspace folder is the durable analysis memory; run folders are execution artifacts.

## Package Layout

```text
pyforestscan_qgis/core/workspace/
  __init__.py
  run_context.py
  workspace.py
  workspace_manager.py
  workspace_state.py
  workspace_history.py
  workspace_session.py
  workspace_timeline.py
  workspace_notes.py
  workspace_version.py
```

`run_context.py` preserves the existing run-folder API. The package `__init__` re-exports `RunContext` and `create_run_context` so existing imports continue to work.

## Responsibilities

- Models are immutable dataclasses.
- `WorkspaceManager` owns local file persistence and auto-save operations.
- Mission Control owns QGIS widget state and calls the manager after major operations.
- Core workspace modules remain QGIS-free.
- No PyForestScan scientific calculation is called by the workspace layer.

## Mission Control Integration

Mission Control now loads a lightweight global session on startup, restores the last selected dataset/output folder/page when available, and saves session state on close or major workflow changes. When a dataset run creates a `RunContext`, Mission Control creates or loads the workspace under the selected output root.

Major events currently auto-save:

- Environment refreshed
- Dataset selected
- Dataset explored
- Planning updated
- Products generated or processing failed
- Batch complete
- Default output folder changed

## Design Boundaries

The Workspace is deliberately not a project file yet. There is no Welcome page, Resume UI, Notes editor, Timeline viewer, cloud sync, accounts, or database. Those can be built later against this local persistence contract.
