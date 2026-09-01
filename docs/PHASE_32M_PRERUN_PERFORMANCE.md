# Phase 32M Prerun Performance

## Root cause

The crash stack exposed a real algorithmic defect, but the Python dictionary line was not itself a native crash source. `validate_coordinate_pair`, WKT parsing, and the polygon clipping implementation are pure Python: they do not call QGIS, PyQt, GDAL, PROJ, pyproj, NumPy, `ctypes`, or another native library. The Windows access violation is therefore classified as process-level/native corruption observed while Python happened to be allocating another validation dictionary after a long UI-thread prerun.

Before Phase 32M, every core and buffered-read intersection called `wkt_to_geojson_geometry`. A 221-parent plan performed 442 parses and validated every vertex 442 times. Prerun manifest generation also built that plan twice for two legacy manifest aliases, producing 884 intersection-loop parses plus two whole-grid area parses: **886 parses** in this path. A 102-vertex polygon therefore triggered about 90,372 coordinate validations instead of 102.

The EPT discovery service pruned `ept-data` and `ept-hierarchy` only after entering `os.walk`. Selecting an already-recognizable EPT root now takes a direct `ept.json` path and never starts recursive traversal.

## Polygon planning

`NormalizedPolygonGeometry` is a frozen, QGIS-free contract containing immutable polygon parts and rings, overall/part/ring bounds, source and processing CRS, coordinate-domain classification, signature, and vertex count. WKT conversion and Phase 32L coordinate validation happen once when this representation is created. Candidate core and read extents reuse it.

Intersection uses three levels of cheap rejection before ring clipping: polygon envelope, part envelope, then hole-ring envelope. Exact clipping, hole subtraction, boundary-touch behavior, global grid construction, parent sizing, buffers, and final-mask science are unchanged.

Synthetic production-shaped benchmark, 102 vertices, 221 candidate parents, and 442 core/read checks:

| Metric | Before | After |
|---|---:|---:|
| Polygon parses | 442 | 1 |
| Intersection-loop time | 0.347 s | 0.015 s |
| Traced peak temporary memory | 495,576 B | 57,514 B |
| Measured speedup | 1x | 23.3x |

The old manifest path multiplied the before parse count to 886. Phase 32M builds one source-aware plan and serializes one in-memory representation for both compatibility keys.

## QGIS threading

Previously `QAbstractButton.clicked -> BatchPage.run_preflight -> run_polygon_batch_preflight -> write_polygon_batch_manifest -> SourceAwareWorkPlanner.plan` ran synchronously on the GUI thread.

Polygon prerun now captures a detached `PolygonBatchRequest` on the main thread and submits `_PolygonPreflightWorker` to a `QThread`. The worker reports repository, grid, coverage, and finalization stages. `Cancel Prerun` sets a cooperative flag checked between candidate units. Failures return `PRERUN_FAILED` and write `prerun_failure.txt`; timing, peak traced memory, process/thread identity, stage, and manifest size are written to `prerun_profile.json`.

The worker does not access `QgsProject`, `QgsVectorLayer`, `QgsFeature`, `QgsGeometry`, widgets, or other QGIS GUI objects. UI changes happen only through queued Qt signals on the page.

## EPT discovery

An EPT root, `ept.json`, or EPT internal-folder selection is normalized by `resolve_ept_selection`. Recognized EPT discovery returns one logical source after path checks and never calls `os.walk`. Automated evidence records one directory, one metadata file, and zero recursive entries. Network latency still controls the filesystem existence checks and later metadata read.

## Manifest and profiling

The source-aware plan is no longer reconstructed independently for `source_aware_raster_plan` and `source_aware_chm_plan`. Large manifest construction and disk writes occur in the prerun worker. Every interactive polygon prerun persists `prerun_profile.json` beside its plan.

The compatibility aliases still serialize equivalent plan data, so a future schema migration can replace the second copy with a reference after all installed-engine consumers accept a new manifest version.

## Stress and regression evidence

- Polygon, MultiPolygon, holes, boundary touches, projected coordinates, and geographic-domain rejection remain covered.
- A 10,001-coordinate ring was normalized once and tested against 500 candidate extents with one parser call. The complete Phase 32M test module, including this stress case, ran in under one second on the development host.
- Cooperative cancellation stops candidate evaluation at a pure-Python safe point.
- Recognized EPT discovery is guarded by a test that makes any `os.walk` call fail.
- Phase 32L `EPSG:6635` projected/meter semantics remain unchanged.

## Live QA status

The known-good Phase 32L small EPT CHM remains the latest completed live canary. Phase 32M automated tests and packaged validation cover the changed planner and UI ownership. The following interactive gates require the real QGIS selection session and are **not claimed by this document** until rerun:

- five packaged-QGIS large-polygon preruns;
- measured UNC repository-selection latency;
- full small-EPT dispatch/final-mask/load rerun;
- large-job first-parent execution and clean cancellation.

For those runs, retain each `prerun_profile.json`, confirm the plan reports approximately 221 candidates / 109 required parents, and attach QGIS responsiveness observations.
