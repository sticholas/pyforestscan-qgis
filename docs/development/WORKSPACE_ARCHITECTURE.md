# Workspace Architecture

Phase 19A added the local Workspace foundation for PyForestScan QGIS. Phase 19B makes that foundation visible in Mission Control through Welcome, Resume, Timeline, and Notes UI. A Workspace represents one analysis and records enough context for Mission Control to feel resumable without coupling state to a QGIS project.

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
  workspace_display.py
```

`run_context.py` preserves the existing run-folder API. The package `__init__` re-exports `RunContext` and `create_run_context` so existing imports continue to work.

## Responsibilities

- Models are immutable dataclasses.
- `WorkspaceManager` owns local file persistence, notes saving, reset behavior, and global recent-workspace tracking.
- `workspace_display.py` owns QGIS-free presentation helpers for status labels, recent workspace summaries, primary next actions, and timeline formatting.
- Mission Control owns QGIS widget state and calls the manager after major operations.
- Core workspace modules remain QGIS-free.
- No PyForestScan scientific calculation is called by the workspace layer.

## Mission Control Integration

Mission Control loads a lightweight global session on startup, restores the last selected dataset/output folder/page when available, and saves session state on close or major workflow changes. When a dataset run creates a `RunContext`, Mission Control creates or loads the workspace under the selected output root. The Home dashboard now reflects workspace state, and the Workspace page exposes Continue Last Workspace, Start New Workspace, Recent Workspaces, status, recent runs, key output links, timeline, notes, and reset controls.

Major events currently auto-save:

- Environment refreshed
- Dataset selected
- Dataset explored
- Planning updated
- Products generated or processing failed
- Batch complete
- Default output folder changed
- Workspace opened
- Workspace notes saved
- Workspace reset

## User-Facing Workspace UI

The Workspace page is intentionally simple by default. It shows a current status card, recent workspace choices, recent runs, key output links, readable timeline entries, and a plain Markdown notes editor backed by `notes.md`. Missing recent workspace folders are flagged so users can remove stale entries without touching valid workspace data.

Continue Last Workspace opens the most recent recorded workspace. Start New Workspace asks for an output folder and creates a `.pyforestscan/` folder there. Reset clears progress, processing history, recent workspace items, and timeline entries while preserving the workspace identity and local folder. It does not delete generated outputs or manipulate the QGIS project.

## Design Boundaries

The Workspace is deliberately not a formal project file yet. There is no cloud sync, account, database, QGIS project manipulation, or external worker integration. The UI reads and writes local workspace files only, and scientific processing continues to flow through JobManager, Pipeline, Adapter, and PyForestScan.
