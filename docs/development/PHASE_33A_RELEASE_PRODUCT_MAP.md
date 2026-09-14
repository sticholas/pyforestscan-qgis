# Phase 33A Release Product Map

This map describes the `0.2.0-beta.1` product boundary. PyForestScan remains the scientific authority; the plugin owns QGIS interaction, request construction, orchestration, durability, output registration, and presentation.

## User Surface And State

| Concern | Authority | Main implementation |
| --- | --- | --- |
| Mission Control composition | dock owns pages and session projection | `ui/mission_control.py`, `ui/pages.py` |
| Interaction wording/help | semantic registry and page help banner | `ui/help_topics.py`, `ui/help.py` |
| Current session/job | session state and current-job token | `ui/session_state.py`, `core/active_job.py` |
| Workspace history | user-selected workspace metadata | `core/workspace/` |
| Advanced Toolbox | QGIS provider and typed algorithms | `processing_provider.py`, `algorithms/advanced/` |

Mission Control's routine surface is Process and Tools & Setup. Process owns Folder/Polygon input, product selection, output, Prerun, execution progress, and the current Result. Engineering controls remain under collapsed troubleshooting sections.

## Processing Chain

1. Source selection enters `BatchPage` and publishes an immutable session signature.
2. Discovery normalizes LAS, LAZ, COPC, or logical EPT roots through repository discovery and catalog services.
3. Polygon geometry is normalized once. CRS resolution follows valid source authority, repository evidence, safe established policy, then explicit fallback.
4. Prerun builds a source-aware plan outside the GUI thread and records timing, bounds, workload, and blockers.
5. `ProcessingEngineService` supplies a verified runtime token. Supported work uses managed Python without changing QGIS Python.
6. Attempt-specific coordinators own child processes, heartbeats, checkpoints, pause/cancel files, retries, and finalization.
7. `PyForestScanAdapter` maps requests to the supported upstream API. Spatial Rumple is the documented plugin extension.
8. Finalization masks, mosaics, validates, registers, and optionally loads only current successful outputs.

## Product Ownership

| Product | Scientific call | Primary output | Shared work |
| --- | --- | --- | --- |
| CHM | `calculate_chm` | `chm.tif` | prepared heights; reusable by Rumple |
| DTM | `generate_dtm` | `dtm.tif` | ground-classified preparation |
| PAD | `calculate_pad` | `pad.tif` | voxel assignment |
| PAI | `calculate_pai` | `pai.tif` | PAD/voxel inputs |
| FHD | `calculate_fhd` | `fhd.tif` | voxelized height distribution |
| Canopy Cover | `calculate_canopy_cover` | `canopy_cover.tif` | PAD-style vertical structure |
| Rumple | `calculate_rumple` plus spatial extension | `rumple.tif` and summary | CHM |
| Point Density | `calculate_point_density` | `point_density.tif` | point reads/grid definition |

The static contract is `core/product_registry.py`. Generic Voxel Statistic remains an Advanced operation, not a routine release product.

## Durability And Storage

- REQUIRED: final products, provenance, output registry, terminal result.
- RECOVERABLE: region checkpoints, manifests, prepared source evidence, active attempt state.
- DIAGNOSTIC: bounded logs, runtime identity, timings, error records.
- TEMPORARY: partial downloads, staging environments, partial rasters before promotion.
- CACHE: reusable repository catalogs and safely reusable preparation artifacts.

Attempt identity prevents an old coordinator, cancellation file, polygon, output, or runtime token from owning a new run. Final output folders should contain deliverables and provenance; scheduler internals belong in managed job workspaces.

## Compatibility And Gates

QGIS APIs are isolated in `core/qgis_compat.py`, `compat/qt.py`, and `ui/`. QGIS 3.44.13 is the supported Windows keystone with limitations. QGIS 4.0.0 passes installed-package UI lifecycle and control audits but remains UI-COMPATIBLE until provider, engine, Prerun, loading, and science gates pass. Linux and macOS remain unqualified. External Worker mode remains disabled.

Automated unit, compile, package, source/ZIP parity, replacement, docs-link, and release checks are mandatory. RC promotion also requires clean-profile engine setup, complete product/source/mode QA, a substantial real job, pause/resume/cancel/recovery, failure injection, current-output loading, science canaries, and supported-platform bootstrap hashes/locks.
