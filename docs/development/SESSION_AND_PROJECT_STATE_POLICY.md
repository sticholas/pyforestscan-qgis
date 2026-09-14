# Session and project state policy

Global state contains PBM location/status, default output folder, and general preferences. Project-scoped state contains repository, mode, polygon, products, output override, prerun result, and current/previous job references. Active progress, transient errors, dialogs, and preview layers are session-only.

Repository or polygon changes invalidate prerun/advisor state, clear current job outputs, and retain completed runs only as previous history. New QGIS projects receive a distinct state keyed by saved project path or an unsaved-project UUID. Legacy global current-dataset, planning, and current-job values are removed at schema migration; safe preferences remain.
