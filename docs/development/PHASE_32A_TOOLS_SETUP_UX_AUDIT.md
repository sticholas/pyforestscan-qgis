# Phase 32A Tools & Setup UX Audit

## Scope

This audit covers the retained **Tools & Setup** page only. Processing, PBM installation, scientific algorithms, backend routing, Advanced Toolbox behavior, and External Worker policy are unchanged.

## Outcome

The page now presents three calm layers:

1. **Processing Engine**: current status, one short explanation, and a contextual **Set Up** or **Repair** action only when work is required.
2. **Advanced Settings**: always visible, limited to the default output folder and the QGIS-startup preference.
3. **Troubleshooting**: collapsed by default, with only **Recheck Processing Engine** and **Open Diagnostics**.

**LiDAR Spatial Reference - Automatic** remains a separate collapsed specialist section because trusted-unit assignments affect interpretation of source data. It is not mixed into engine setup.

## Control Decisions

| Previous control or section | Decision | Phase 32A location or behavior |
|---|---|---|
| Processing Engine status | Keep | Prominent compact status card |
| Set Up Processing Engine | Keep and make contextual | Shown only when setup is required |
| Repair Processing Engine | Combine | Same primary action becomes **Repair** when repair is required |
| Recheck Processing Engine | Keep | Troubleshooting |
| Open Diagnostics | Keep | Troubleshooting; opens consolidated architecture, path, version, compatibility, dependency, and technical-log details |
| Preview Install Plan | Remove from normal UI | Setup transaction remains authoritative |
| Verify QGIS Compatibility | Combine | Included in setup verification and Recheck diagnostics |
| Manual Setup Instructions | Remove from normal UI | Managed setup remains the supported path |
| Open Backend Folder | Remove from normal UI | Paths remain visible in diagnostics |
| View Logs | Combine | Technical log is available through Open Diagnostics |
| Advanced backend button | Remove | Diagnostics is the one advanced support surface |
| Additional Tools | Remove | Toolbox and guidance already have better homes elsewhere |
| Open Processing Toolbox duplicate | Remove | Advanced Toolbox navigation remains available outside Tools & Setup |
| Guidance Details duplicate | Remove | Scientific Advisor remains the guidance surface |
| Advanced Settings disclosure | Simplify | Always visible; no disclosure click required |
| Recent Item Limit | Remove from normal UI | Internal recent-workspace display bound remains 10; it never limits jobs, datasets, polygons, or outputs |
| Session persistence toggles | Remove from normal UI | Existing conservative defaults remain internal |
| LiDAR spatial assignment controls | Keep and move | Separate collapsed automatic-spatial-reference section |

## Action Count

The expanded page previously exposed 14 user actions. Phase 32A exposes six purposeful actions across the entire page: Save Trusted Units, Clear Assignment, Browse, contextual Set Up or Repair, Recheck Processing Engine, and Open Diagnostics. The engine action is hidden when Ready. Troubleshooting fell from seven or more standalone backend actions to two.

## State Matrix

| Engine state | Status text | Primary action |
|---|---|---|
| Ready | Everything required for LiDAR processing is installed. | Hidden |
| Setup required | Set up the Processing Engine to install everything required for LiDAR processing. | Set Up |
| Repair required | Setup requires attention; diagnostics explain the failure. | Repair |
| Failed or incompatible | Setup cannot be used until repaired. | Repair |
| Checking or unknown | State is being resolved. | Set Up when action is allowed |

## QGIS Runtime QA

The packaged plugin was instantiated with QGIS 3.44.13 LTR at 420, 500, 620, and 800 px widths. No horizontal scrollbar appeared. Advanced Settings remained visible and non-collapsible. Ready, Setup Required, and Repair Required produced the expected action visibility and labels. Troubleshooting was expanded and collapsed repeatedly while diagnostics refreshed without ownership or lifecycle errors.

The offscreen QGIS renderer did not paint stylesheet text into screenshots on this machine. Widget geometry and state assertions were therefore used as the authoritative runtime evidence; live in-application visual inspection remains part of release QA.

## Guardrails

- Setup and Repair still call the same background managed-engine transaction.
- Recheck does not install or mutate the engine.
- Diagnostics does not create processing work.
- No normal control modifies QGIS Python, system Python, global environment variables, or the QGIS installation.
- External Worker mode remains disabled.
- No job-size or workload limit was added.
