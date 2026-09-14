# Phase 28C Live Visual Validation

## Tested artifact

- QGIS runtime: 3.44.9 LTR
- Method: Windows offscreen QGIS Python runtime
- Profiles: runtime initialization only; no clean interactive profile
- Interactive tester/date: pending

## Automated/offscreen results

| Check | Result |
|---|---|
| BatchPage construction | Passed offscreen |
| MissionControlDock construction | Passed offscreen |
| Plugin initGui/unload | Passed offscreen |
| Folder/Polygon mode switching | Passed offscreen |
| Advisor state update | Passed offscreen |
| Advanced Toolbox routing | Passed offscreen |
| Results empty-state transition | Passed offscreen |
| Narrow/normal/wide geometry at 100% | Passed offscreen |
| Narrow/normal/wide geometry at 150% | Passed offscreen |

## Interactive visual matrix

| Check | Status | Notes/evidence required |
|---|---|---|
| Normal QGIS profile | Not tested live | screenshot each retained page |
| Clean QGIS profile | Not tested live | ZIP install and first run |
| 100% Windows scaling | Not tested live | narrow, normal, wide dock |
| 150% Windows scaling | Not tested live | clipping and wrapping |
| Light QGIS theme | Not tested live | contrast and icons |
| Dark QGIS theme | Not tested live | contrast and icons |
| Keyboard tab order/focus | Not tested live | complete common Batch path |
| Plugin enable/disable/re-enable | Not tested live | no stale dock/provider |
| LiDAR Folder Selection workflow | Not tested live | discovery through Results load |
| Polygon Selection EPT/CHM workflow | Not tested live | exact mask and Results load |

## Live action matrix

The following require actual project/canvas/output data and are **Not tested live**: Show Selected Files on Map, Preview Spatial Alignment, Zoom to Polygon, Zoom to Repository Extent, Zoom to Combined Extent, Add Repository Coverage, Remove Preview Layers, Open/focus Processing Toolbox, refresh provider without duplication, Load generated outputs, and Open Output Folder.

For each action, record the project/panel/canvas side effect, user message, repeated-use behavior, and failure behavior. Do not convert an offscreen pass into a live pass.

## End-to-end workflow

Polygon Selection -> EPT -> polygon -> CHM -> output -> Prerun Check -> Process -> exact mask -> Results -> Load into QGIS: **Not tested live**. Click count, elapsed interaction time, confusing moments, and processing result remain pending.
