# Parameter and Language Audit

Phase 20F reviewed the Processing Toolbox, Mission Control-facing documentation, README, user guide, limitations, release checklist, and API coverage docs for parameter parity and professional wording.

## Summary

| Area | Status | Issues found | Fixes made | Remaining risks |
| --- | --- | --- | --- | --- |
| Diagnostics / Environment Check | Fixed | Help text was accurate but brief. | Reworded help to state runtime checks, QGIS/Python/package scope, optional report, and no environment mutation. | None beyond manual QGIS confirmation. |
| Input / I/O / Normalize Heights | Fixed | Labels mixed plain-language and PyForestScan wording; help did not list all important inputs. | Clarified DTM, bounds, thin_radius, crop polygon, output, and compress labels; help now states `read_lidar`, HAG, optional LAS/LAZ output, and key parameters. | Product-level crop UX remains deferred. |
| Preprocessing / Filters | Fixed | Tool performs many operations; splitting was considered. Labels for duplicate `cell` parameters were ambiguous. | Kept one ordered preprocessing tool because it writes one LAS/LAZ output through a clear filter chain. Help now lists execution order. Labels distinguish SMRF cell from voxel-downsample cell. | Separate filter-only tools may be useful later if users request smaller single-operation dialogs. |
| Terrain / Generate DTM | Fixed | Help was too terse; labels did not show units or exact `nodata` wording. | Reworded help to explain ground-class requirement, output, and QA; labels now use `resolution (map units)` and `nodata`. | DTM quality still depends on ground classification quality. |
| Metrics tools | Fixed | Help strings named functions but did not consistently state use case, key parameters, output, and caution. | Rewrote CHM, PAD, PAI, Canopy Cover, FHD, Rumple, Point Density, and Voxel Statistic help strings. Common parameter labels now include units and PyForestScan parameter names where useful. | Manual QGIS review is still required for visual layout and wording in dialogs. |
| Tool names and groups | Pass | Phase 20E already removed the visible `Advanced` prefix and hid legacy guided toolbox entries. | Added regression tests for clean groups and removed deprecated names. | Underlying Python class names remain stable for code compatibility. |
| Mission Control language | Pass | Current documentation describes progressive disclosure, run folders, Advisor, Batch, and Workspace clearly. | User Guide wording now distinguishes Mission Control guided workflows from toolbox expert tools. | Full visual copy review still requires QGIS manual QA. |
| README | Fixed | Metadata and README needed current guided/toolbox separation language. | Updated plugin metadata and README algorithm-directory description. | Version and screenshots remain release-management work. |
| User Guide | Fixed | Some passages still described Dataset Explorer and Product Planner as Processing algorithms and used stale future-facing language. | Reworded them as Mission Control workflows and clarified generated outputs. | Long guide should receive another editorial pass before public release. |
| API / Toolbox docs | Fixed | Some docs still used old `Advanced` naming or older toolbox grouping. | Updated toolbox map, toolbox docs, and deferred-feature language. | Public docs should be regenerated if PyForestScan changes its API. |
| Known limitations | Fixed | External Worker and release-scope wording was unnecessarily future-facing. | Reworded to concrete disabled/release-scope statements. | External worker research remains intentionally blocked. |
| Release checklist | Pass | Checklist remained accurate for internal build validation. | No change required. | Manual QGIS smoke tests remain required. |

## Split-Tool Decision

`Preprocess Point Cloud` was not split in Phase 20F. Although it exposes several filter operations, those operations share the same input, CRS, output LAS/LAZ writer, adapter boundary, and scientific purpose: producing a cleaned or normalized point cloud. Splitting would create several tools that each need a point-cloud output and would increase toolbox clutter without adding a new capability. The help text now documents the exact operation order.

## Deferred Work

- `process_with_tiles` remains deferred until a QGIS-safe tiling workflow handles progress, cancellation, summaries, and output naming.
- Matplotlib visualization helpers remain deferred because QGIS-native rendering, histograms, symbology, and Layout Manager are the preferred user-facing tools.
- Product-level crop/bounds controls remain deferred until a consistent QGIS vector/bounds UX is designed.
- External Worker mode remains disabled until a true headless Python launcher is proven.

## Verification

Phase 20F adds/updates tests for visible toolbox names, group strings, deprecated registration removal, critical parameter labels/defaults, metadata language, and external-worker disabled text.
