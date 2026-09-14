# Phase 29B Workflow Simplification Audit

## Scope

Phase 29B reduces normal decisions without changing scientific algorithms, PBM, adaptive planning, output registration, raster masking, Advanced Toolbox, or External Worker policy.

## Repository controls

| Control | Decision |
|---|---|
| Repository path | Accepted and normalized automatically after browsing or editing |
| Prepare Repository | One normal preparation action, replacing the Build Index wording |
| Update Index | Moved into Repository Tools |
| Use Path | Removed as duplicate confirmation |
| Refresh Catalog Status | Removed as duplicate automatic status refresh |
| Inspect Data Folder | Removed; Inspect Repository owns inspection |
| Preview Setup Method | Retained advanced |
| Inspect, scan headers, resume/pause, repair, CRS, coverage, sources, diagnostics | Retained under Repository Tools |

## Spatial controls

Show Selected Files, Preview Spatial Alignment, Zoom to Polygon, and Zoom to Repository remain. They now request a fresh spatial readiness plan when the current one is absent. Re-run Prerun Check and Zoom to Combined Extent were removed as duplicate/nonessential actions. Reset Polygon remains an explicit destructive recovery action.

## Profiles and execution

Recommended is presented as **Automatic (Recommended)**. Automatic, Conservative, and Performance are explanatory presets that apply existing guarded topology. Only Custom exposes Execution Mode. Max Workers appears only for Custom + Parallel and is described as an upper limit because adaptive/source safeguards may use fewer workers. External Worker remains disabled.

## Session integrity

Repository, polygon, product, resolution, output, profile, execution, worker, retry, conflict, and mask-option changes invalidate the old prerun plan. Current-job token isolation continues to prevent stale jobs from populating current results.

## Startup

Plugin initialization registers its provider and Mission Control action but does not open Mission Control by default. A persisted Advanced Settings preference can explicitly restore startup opening. Preference read failures fail closed.

## Remaining Phase 29C opportunities

- Replace remaining long help dialogs with concise hover help.
- Add product/parameter mini-diagrams where they materially improve understanding.
- Give every retained repository maintenance action unique contextual help.
- Perform live Windows visual, map-action, and processing QA.
