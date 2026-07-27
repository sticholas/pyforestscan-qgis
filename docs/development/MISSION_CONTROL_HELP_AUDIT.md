# Mission Control Help Audit

Phase 27K introduced a central HelpTopic registry and InfoBadge component. The audit follows the rule: simplify first, then add help only where a concept remains non-obvious.

| Page | Control | Revised label | Classification | Help topic key | Guided/Advanced | Action taken | Rationale |
|---|---|---|---|---|---|---|---|
| Home | Backend status | Backend status | Add InfoBadge | home.backend_status | Guided | Topic registered | PBM readiness can be confused with QGIS Python readiness. |
| Workspace | Workspace folder | Workspace folder | Add InfoBadge | workspace.folder | Guided | Topic registered | Users need to distinguish workspace state from outputs. |
| Workspace | Output root | Output root | Add InfoBadge | workspace.output_root | Guided | Topic registered | Output storage impacts disk and recovery. |
| Dataset | Dataset source | Dataset source | Add InfoBadge | dataset.source | Guided | Topic registered | EPT/COPC/LAS/LAZ source types differ. |
| Dataset | CRS | CRS | Add InfoBadge | dataset.crs | Guided | Topic registered | CRS controls spatial alignment and estimates. |
| Dataset | Point dimensions | Point dimensions | Add InfoBadge | dataset.dimensions | Guided | Topic registered | Product prerequisites depend on dimensions. |
| Planning | Processing CRS | Processing CRS | Add InfoBadge | planning.processing_crs | Guided | Topic registered | Projected units are important. |
| Planning | Resolution | Resolution | Add InfoBadge | planning.resolution | Guided | Topic registered | Resolution affects runtime and output quality. |
| Planning | Height normalization | Height normalization | Add InfoBadge | planning.height_normalization | Guided | Topic registered | Scientific prerequisite. |
| Processing | CHM | CHM | Add InfoBadge | processing.chm | Guided | Topic registered | Scientific product term. |
| Processing | PAD / PAI / FHD / Rumple | Product names | Add InfoBadge | processing.pad, processing.pai, processing.fhd, processing.rumple | Guided | Topic registered | Scientific acronyms require restrained explanation. |
| Batch | LiDAR Repository | LiDAR Repository | Add InfoBadge | batch.lidar_repository | Guided | Badge applied | EPT root/ept-data normalization needs explanation. |
| Batch | Polygon source | Polygon source | Add InfoBadge | batch.polygon | Guided | Badge applied | Selected features/layers/WKT differ. |
| Batch | Repository setup method | Repository setup method | Add InfoBadge | batch.repository_setup_method | Advanced | Badge applied | Strategy affects performance and should remain understandable. |
| Batch | Workload estimate | Workload estimate | Add InfoBadge | batch.workload_estimate | Guided | Topic registered | Estimate confidence is intentionally conservative. |
| Results | Load Outputs | Load Outputs | Add InfoBadge | results.load_outputs | Guided | Topic registered | Duplicate prevention and batch scope need explanation. |
| Environment | Managed Backend | Managed Backend | Add InfoBadge | environment.managed_backend | Guided | Topic registered | PBM is separate from QGIS Python. |
| Environment | QGIS Python fallback | QGIS Python fallback | Add InfoBadge | environment.qgis_python | Advanced | Topic registered | Optional fallback should not scare PBM-ready users. |
| Settings | Performance | Performance and Memory | Move to Advanced | settings.performance | Advanced | Topic registered | Risky runtime controls belong under Advanced. |
| Settings | Diagnostics | Diagnostics | Move to Troubleshooting | settings.diagnostics | Troubleshooting | Topic registered | Logs are secondary unless debugging. |

Current automated coverage is reported by `python3 scripts/check_help_coverage.py`. The script reports registered, used, missing, and orphan topics. Missing used topics fail validation; orphan topics are allowed because the registry documents the full audit before every topic is placed in UI.

## Phase 27L additions

Added help coverage for request validation and diagnostic actions so Guided Mode can explain failures without exposing raw backend internals by default.

## Phase 27M Help Coverage

Batch Advanced Options now use InfoBadge topics for processing concurrency, concurrent logical jobs, effective concurrency, continue-on-error behavior, retry behavior, output conflict policy, load-after-completion, exact raster masking, mask implementation, crop-to-extent, touched cells, retained intermediates, and mask failure policy.

## Phase 27N Guided Help

The Batch page now exposes spatial-selection preview actions and processing profiles. Future help expansion should add badges to guided step headings only where the term changes user decisions.

## Phase 27O Notes

Repository discovery, catalog identity, catalog integrity, repair, source-view, coverage-model, diagnostic-export, and repository action-state services now back Polygon Area Processing setup. Broken catalogs are reported as catalog repair/readiness issues instead of generic no-coverage results. The RTree contract is `id, xmin, xmax, ymin, ymax`; EPSG:6635 overlap fixtures cover the observed polygon envelope regression.
