# Repository Action Wiring

Phase 27O introduces `RepositoryActionState` and `RepositoryActionStates` so visible repository controls have a typed enabled/disabled model.

## Guided Actions

- Inspect Data Folder
- Build Catalog
- Refresh Catalog
- Repair Catalog
- Show Coverage
- Continue

## Repository Tools

- Inspect Repository
- Scan File Headers
- Build Complete Catalog
- Update Catalog
- Resume Catalog Build
- Pause After Current Chunk
- Move Catalog Local
- Open Catalog Folder
- Add Coverage to Map
- View Sources
- Export Diagnostic Report

Each action has visible feedback, a disabled reason when it cannot run, and QGIS-free service behavior where possible. Live map operations still require QGIS main-thread execution and must be validated in QGIS.
