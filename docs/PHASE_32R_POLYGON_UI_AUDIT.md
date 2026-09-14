# Phase 32R Polygon UI Audit

## Release Workflow

The normal path is now:

`LiDAR Data -> Processing Area -> Products -> Output Folder -> Prerun Check -> Process LiDAR -> Results`

The wizard-style step strip was removed because the complete workflow already
occupies one workspace.

## Control Classification

| Surface | Classification | Release treatment |
| --- | --- | --- |
| Processing mode | `ESSENTIAL_NORMAL` | Retained for Folder versus Polygon. |
| LiDAR source | `ESSENTIAL_NORMAL` | Retained; recognition/preparation is automatic. |
| Polygon source/layer/file | `ESSENTIAL_NORMAL` | Retained with compact selection summary. |
| Area/geometry/CRS summary | `ESSENTIAL_NORMAL` | Retained; `Zoom to Area` placed beside the area workflow. |
| Products | `ESSENTIAL_NORMAL` | Retained as a compact checkbox grid. |
| Output folder | `ESSENTIAL_NORMAL` | Retained as one path row. |
| Prerun Check | `ESSENTIAL_NORMAL` | Retained as the single explicit review action. |
| Process LiDAR | `ESSENTIAL_NORMAL` | Retained as the primary action. |
| Repository strategy/index selection | `AUTOMATIC` | Hidden from normal workflow; selected during recognition/Prerun. |
| Prepare Repository | `AUTOMATIC` | Removed from the routine path. Prerun invokes required preparation. |
| Exact mask, crop, mask engine/failure policy | `AUTOMATIC` | Scientifically safe defaults remain active and recorded. |
| Scheduling, concurrency, checkpointing | `AUTOMATIC` | Hidden; Processing Engine owns these decisions. |
| Inspect/update/repair repository | `ADVANCED_DIAGNOSTIC` | Kept under one compact Advanced section. |
| Resolution override | `ADVANCED_DIAGNOSTIC` | Kept under Advanced. |
| Retain unmasked intermediate | `ADVANCED_DIAGNOSTIC` | Kept under Advanced and off by default. |
| Map selection/alignment/repository extent tools | `REMOVE` | Removed from normal display; `Zoom to Area` is the useful retained action. |
| Legacy profile/worker/masking choices | `REMOVE_LEGACY` | Existing internal defaults remain for request compatibility; controls are hidden. |
| Info badges in normal Polygon rows | `REMOVE` | Replaced by hover/focus help and tooltips. |

## Help and Accessibility

Every Mission Control page has one bounded help strip below its scroll area.
Hover and keyboard focus both update it from explicit context help, tooltips, or
accessible names. The default text remains available when no control is active.
The strip wraps at narrow widths and is capped so it does not cause layout jumps.

## Progress and Results

Normal progress reports product/stage, percent, completed/total regions, active
regions, elapsed time, ETA, and health. Worker targets remain technical evidence,
not a user decision. Long jobs state that completed regions are saved and valid
completed regions can be resumed. Results continue to prioritize generated
outputs, loading, and opening the output location.

## Width and Height Expectations

- Narrow dock: path rows wrap through Qt layout behavior; the help strip wraps
  and primary buttons remain full-size.
- Normal dock: Data, Area, Products, Output, Prerun, and Process remain a single
  readable vertical flow.
- Floating wide: sections expand to available width without exposing hidden
  repository or scheduler panels.
- Laptop height: hidden engineering panels eliminate the previous multi-screen
  expansion; scrolling remains available for product/result content.

