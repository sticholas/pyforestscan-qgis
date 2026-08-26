# Effective Source Spatial Profile

The effective source spatial profile is resolved before overlap selection. Raw metadata remains immutable and is reported separately from the effective processing CRS.

Resolution precedence is embedded source metadata, source sidecar, explicit file assignment, explicit repository assignment inherited by members, high-confidence repository consensus, then exact QGIS datasource assignment.

Legacy catalog overrides remain readable for compatibility but are not the user-assignment source of truth. New assignments are written to the shared user-local spatial assignment store.

An unknown member inherits a valid repository assignment. An authoritative member CRS that differs from the assignment produces `CONFLICT`; the assignment never overwrites header truth. Polygon selection blocks when no real CRS is available. Folder source-local processing may use its separate unit-aware fallback policy.

`polygon_source_resolution.json` records raw CRS, effective CRS, assignment provenance, polygon/comparison CRS, bounds, overlap, and selection or rejection reason.
