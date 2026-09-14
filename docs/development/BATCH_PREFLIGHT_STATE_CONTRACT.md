# Batch Preflight State Contract

Polygon plan identity includes the effective repository CRS and transformed polygon state. Changing a trusted repository assignment invalidates the old preflight and rebuilds selection.

Plan signatures also include spatial mode, provenance, polygon/comparison bounds, and selected source CRS/bounds so fallback-policy or project/polygon changes cannot reuse unresolved selection.

## Previous lifecycle and failure

Mission Control stored `preflight_report` as both a readiness presentation object and an execution dependency. Any execution-defining input invalidated it. During a standard run, `_mark_selected_files_queued()` changed `QListWidgetItem` text; `itemChanged` was wired to normal input invalidation, so the just-approved report became `None`. Progress then read `self.preflight_report.files_to_skip` and raised `AttributeError`.

## Current contract

`preflight_report` is a replaceable UI projection. It may be absent or stale without making execution unsafe. Process performs authoritative validation when the projection is absent, then freezes `BatchExecutionRequest` before changing status widgets.

The immutable launch contains:

- exact selected and skipped source sets;
- requested products and output root;
- processing mode and profile;
- requested concurrency ceiling;
- warnings, blockers, plan identity, and validation timestamp;
- the exact typed `BatchRequest` approved for the worker.

Programmatic row updates block list signals and cannot invalidate readiness. Scientific execution reads the frozen launch request, never labels, visibility, enabled state, or a later `preflight_report` value.

## Invalidation

Source, selection, polygon, products, output, resolution, profile, execution policy, and mask changes clear only the UI readiness projection. Process transparently recomputes validation. Blocked validation remains visible and does not launch.

## Progress semantics

`logical_inputs` counts sources submitted to execution. Already-completed/skipped sources are recorded separately and do not inflate processing percentage. Polygon progress uses its immutable preflight report and selected logical sources; adaptive work-unit progress remains coordinator-owned.
# Phase 30D amendment

Warnings do not invalidate readiness. New preflight requests create new batch identities; historical manifests require explicit recovery selection. Scheduler details are technical diagnostics rather than normal summary content.

Phase 31C resolves each independent source through the central spatial policy. Eligible assumed units produce `SOURCE_UNITS_ASSUMED` as a warning and keep Process enabled. The resulting context is serialized into Dataset Report/Product Plan and must equal PBM execution context. CRS-required and contradictory-evidence states remain blockers.
