# Phase 29C Product Reliability Audit

## Scope and Evidence

This phase audited the retained Process workflow, legacy guided pages, Results, Mission Control state propagation, active-job ownership, output registration, adaptive planning, PBM execution boundaries, and recovery controls. Evidence comes from source tracing, 600+ QGIS-free tests, package checks, and an offscreen QGIS 3.44 interaction test. No fresh real-LiDAR scientific run was performed in this phase; earlier Phase 27-28 field evidence remains historical evidence, not a new pass.

## Workflow Audit

The supported compact path is: open Mission Control, choose Folder Batch or Polygon Area Processing, select data, choose products/output, run Prerun Check, process, review the current result, load it into QGIS, then start a new run. Repository preparation remains explicit for polygon repositories. Advisor, Environment, Settings, workspace history, and Advanced Toolbox remain supporting surfaces.

The audit confirmed one Process click creates one logical-job token and one Qt worker thread. A second coordinator is rejected while the active token is non-terminal. Run-defining sections are now disabled until that worker finishes. Pause and cancel continue to operate between safe boundaries.

## Control Audit

Visible controls were traced by page and signal. Primary buttons have concrete slots or emitted actions. Selection, text, numeric, profile, execution, retry, overwrite, masking, repository-strategy, and product controls invalidate readiness. Phase 29C closed gaps for file check-state, recursive discovery, direct-header fallback, and mask-failure policy. Warning acknowledgement changes run eligibility without changing the scientific request.

Spatial preview controls perform fresh preflight when required. Repository maintenance remains under Repository Tools. Settings and Environment signals retain their existing service boundaries. Advanced Toolbox behavior was not changed.

## Session-State Audit

Every run-defining Process value now contributes to a deterministic `input_signature`. A changed signature invalidates the current plan, Prerun Check, Advisor summary, current output references, loaded-output references, Results display, and active terminal-job reference. Durable previous-run history is retained separately. Inputs are frozen while a job is active, preventing a callback from completing against mutated settings.

## Output Integrity Audit

Results now loads only explicitly registered paths. It no longer recursively scans an output folder, so stale, cached, intermediate, or partial rasters cannot appear merely because they exist on disk. Duplicate canonical paths remain filtered against both this session and QGIS project layer sources.

Only `COMPLETED` single jobs publish loadable result records or auto-load rasters. A batch with any failed item keeps summary diagnostics but does not register partial item outputs as the current successful result. A successful batch registers only existing outputs from completed items. Current-job tokens reject stale completion callbacks.

## Background Job Audit

The active-job controller enforces one non-terminal job. Qt workers are connected to exactly one completion/failure path, quit their owning thread, and clear worker/thread references after Qt cleanup. PBM execution monitors heartbeat age and captures native crash diagnostics. External Worker mode remains disabled.

Durable worker progress files remain forensic/recovery artifacts; they are not QGIS layer-registration inputs. Interrupted jobs require their existing recovery path and do not silently become successful Results.

## Adaptive and Large-Job Audit

Automated tests cover tiny, small, medium, large, very large, network EPT, native LAS/LAZ partitions, irregular/concave geometry filtering, pilot growth/shrinkage, memory pressure, and CPU bounds. Planning derives scale from envelope and polygon area, resolution, point density, source type/location, available memory, CPUs, and optional performance history.

Safety caps and bounded defaults still exist in the planner. They are engineering guardrails, not preferred tile counts, but live calibration across more hardware and repositories remains an RC requirement. Multipolygon and missing-LiDAR behavior are covered by spatial/preflight tests; fresh live fixtures were not executed here.

## Performance and Memory Audit

Existing instrumentation records catalog lookup, row loading, workload estimation, total preflight query time, backend elapsed/liveness, work-unit resource estimates, and durable progress. Performance history is keyed by repository/product/resolution/HAG context and is advisory.

The bounded executor avoids loading the whole large-area source into QGIS memory. Adaptive units cap expected point/raster memory, exact polygon filtering drops irrelevant units, and mosaics use files rather than an in-memory full-raster assembly. Remaining measurement gaps are end-to-end phase timings for HAG, calculation, masking, mosaic, registration, and QGIS loading on real machines.

## Failure Matrix

| Failure | User result | Recovery |
| --- | --- | --- |
| PBM unavailable | Readiness blocker | Open Backend Settings; install/repair and verify |
| Network/EPT unavailable | Source-read failure with diagnostics | Restore access; retry current failed attempt |
| No LiDAR/no points | Preflight blocker or valid NoData unit where scientifically allowed | Confirm coverage/CRS; adjust polygon |
| CRS unresolved | Spatial-alignment blocker | Assign/repair repository CRS or choose correct source CRS |
| Permission denied/disk full | Transaction or output failure | Change output location/free space; retry |
| Cancelled/interrupted | Non-success terminal state | Resume/retry through documented recovery |
| Worker/HAG/PDAL failure | Failed attempt; no loadable outputs | Review technical log/crash bundle; retry after correction |
| Mask/mosaic failure | Product failure under selected policy | Review mask settings and diagnostics; do not load partial output |
| Timeout/stale heartbeat | Stalled/timed-out diagnostic | Inspect heartbeat/crash bundle and retry safely |

Raw exception details remain in technical diagnostics. The user-facing surface provides status and recovery context; further exception-by-exception wording review remains appropriate during RC manual QA.

## Scientific Equivalence

Adaptive execution does not alter the requested resolution, CRS, global grid, HAG signature, exact polygon geometry, product parameters, core-cell ownership, NoData contract, or final mask. Worker count changes scheduling only. Buffered unit edges are discarded and aligned core cells are merged deterministically. Resume accepts verified current-plan units only.

These are structural equivalence guarantees. Numeric equivalence across worker counts, interruption/resume, EPT versus ordinary LAS, and representative products still needs fixture-based raster statistics and pixel comparisons on real data before v1.0.

## Cleanup Summary

No broad legacy deletion was attempted. Folder scanning as an implicit Results registry was removed. Duplicate output paths are collapsed. Existing legacy guided pages and compatibility services remain because they are still wired, documented, or needed for backward compatibility. Removing them without telemetry and RC evidence would be unsafe.

## Release-Candidate Blockers

- Run the RC manual script on a clean Windows QGIS installation with PBM installation.
- Capture fresh small, medium, large, missing-coverage, EPT, and ordinary LAS results.
- Prove numeric equivalence across sequential/adaptive schedules and interrupted/resumed runs.
- Capture process-tree evidence showing no orphan PBM process after success, failure, and QGIS shutdown.
- Measure complete phase timings and peak memory on representative hardware.
- Review every documented failure using induced clean-machine cases.

Phase 29C improves enforceable reliability contracts, but it does not claim those outstanding live tests passed.
