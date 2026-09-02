# Phase 32S RC UX Audit

## Blocking defect

Phase 32R removed the polygon guided-step widget but `_on_polygon_preflight_complete()` still updated it. The stale write and unused production import were removed. Prerun state now remains semantic: the report, summary, run-button policy, footprint, and session state are updated without a wizard label.

## Polygon workflow

- Processing mode uses one compact labeled row.
- Refresh and Zoom to Area share the polygon selector row.
- Selection dissolve is automatic and hidden from routine UI; normalized geometry continues to represent the exact selected feature union.
- Repository detection remains automatic. Index inspection, refresh, and repair remain maintenance capabilities outside the normal path.
- Products contain product choices. Temporary unmasked output remains an advanced diagnostic option and defaults off.
- Output folder remains a single line edit and Browse action.

## Context help

`ContextHelpBanner` is the shared Mission Control component. It uses QGIS palette roles, a compact framed treatment, passive default guidance, pointer enter/leave, and keyboard focus in/out. Help remains separate from job state and errors.

## Legacy classification

| Reference | Classification | Action |
| --- | --- | --- |
| `polygon_guided_step_label` production callback | LEGACY_REMOVE | Removed |
| `guided_step_indicator` production import | LEGACY_REMOVE | Removed |
| Core guided-workflow formatter and historical tests/docs | TEST_ONLY / HISTORICAL_DOC | Retained |
| Repository maintenance actions | CURRENT_REQUIRED | Retained outside routine workflow |
| Intermediate-retention capability | CURRENT_REQUIRED | Retained in Advanced |
