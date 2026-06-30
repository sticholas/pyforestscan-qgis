# Workspace Data Model

The Workspace data model is split into small files so future functionality can evolve without turning one JSON file into an unstructured dump.

## `workspace.json`

Stores the top-level identity and current state snapshot:

- `workspace_id`
- `name`
- `output_root`
- `workspace_dir`
- `created_at`
- `updated_at`
- `state`

## `session.json`

Stores resumable user context:

- last opened workspace
- last selected dataset
- last output folder
- last planner settings
- last selected products
- last Mission Control page
- window geometry
- floating/docked state
- remember last workspace/dataset/output folder
- maximum recent items
- auto-save enabled

A separate global session file under the local user config directory stores the pointer needed before any output root is known. Workspace-owned session state remains in `.pyforestscan/session.json`.

## `history.json`

Stores processing run records:

- run id
- products
- parameters
- success/failure
- output paths
- started/finished timestamps
- duration if known
- error message if failed

## `recent.json`

Stores recent items, trimmed by the configured maximum count. Item types include workspaces, datasets, output folders, reports, batch reports, and outputs.

## `timeline.json`

Stores append-only timeline events with timestamp, event type, message, and string details.

## `notes.md`

Stores simple Markdown notes for the workspace. Phase 19A creates and preserves the file but does not build an editor.

## `version.json`

Stores workspace format version metadata. No migrations exist yet, but the model is migration-ready.
