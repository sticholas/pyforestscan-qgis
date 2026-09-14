# Phase 29D Performance and Scalability Audit

## 1. Current Processing Architecture

Polygon normalization, CRS resolution, source selection, and EPT bounds are computed once during preflight. CHM planning creates one globally aligned grid, exact polygon/core intersections, scientifically buffered read extents, and required/skipped units. A small logical EPT/COPC request uses one bounded PBM product call. A larger EPT CHM launches one durable PBM coordinator; its in-process bounded scheduler retains scientific imports and executes all units, extracts aligned cores, builds a file-backed GDAL VRT/GeoTIFF mosaic, applies the exact mask, registers successful outputs, and returns them to QGIS.

Ordinary LAS/LAZ uses catalog/direct-header source selection, preserves intersecting files as native first partitions, clips required sources, and hands them to the existing batch path. COPC uses logical bounded access where selected as a logical source. QGIS submits, observes, and loads; routed scientific computation remains in PBM.

## 2. Baseline Bottlenecks

The synthetic baseline exposed inconsistent memory models. Adaptive sizing assumed 96 bytes/point for existing HAG while execution estimated about 245 bytes/point plus raster buffers and fixed overhead. An 8 GiB EPT plan could therefore create units estimated near 5.7 GiB. A single native source with missing file-size metadata could remain monolithic regardless of spatial workload. Planning itself was fast and was not a bottleneck.

## 3. Measurements

Measurements are synthetic planning measurements on this machine except PBM startup, which used the installed Windows managed backend. No real LiDAR was read.

PBM Python plus `pyforestscan`, PDAL, GDAL, rasterio, and numpy imports measured 4.46 seconds cold and 0.85-0.86 seconds warm. Architecture tracing confirmed this startup occurs once for a durable polygon job: work units run inside the coordinator process. A persistent worker service is therefore not justified by startup measurements.

A historical real network-EPT job folder was analyzed without restarting it. Of 120 durable records, 89 cores were complete, four failed, and 27 remained pending at the scientific blocker. Completed-unit runtime totaled 2,151.9 seconds over a 2,156.5-second coordinator span; median was 28.6 seconds, mean 24.2 seconds, and read amplification was 1.317. The roughly 4.6-second difference between summed serial unit runtime and coordinator span is below 0.3%, confirming that orchestration was not the dominant bottleneck in that run. This is measured historical evidence, not a new Phase 29D scientific pass.

## 4. Small-Job Overhead

The 200 m x 200 m synthetic case plans one unit and uses `direct_single_request`. It does not create per-unit scheduler execution, core rasters, or a mosaic. Diagnostic buffered-read amplification is reported as 1.0 because the direct path uses the request bounds rather than the dormant work-unit buffer.

## 5. Adaptive Planning Behavior

The planner now shares the executor's point-memory model. Scale derives from area, exact intersection, resolution, density, source type/location, memory, CPU, HAG method, raster cells, and native partitions. Pilot calibration remains advisory and is skipped for small safe requests. Live re-planning is not enabled because changing unit identities after durable checkpoints would weaken recovery compatibility without a validated migration contract.

## 6. Work-Unit Strategy

There is no fixed 88, 89, or 120 unit target. On the 8 GiB/8 CPU synthetic EPT matrix, required units were 1, 20, 315, and 2,542 for small through very large scenarios. Those counts reflect the corrected conservative memory model, not preferred counts. Planning took roughly 0.1-15 ms after interpreter warm-up.

## 7. Native Partition Strategy

Small adjacent native tiles remain reusable first partitions and may be grouped when their combined workload is safe. A large source is subdivided when file size or estimated point/raster memory exceeds the adaptive unit limit, including when file size is unknown. The synthetic native matrix produced 1, 6, 130, and 1,014 units.

## 8. Concurrency Policy

Effective concurrency is capped by runnable units, CPU, memory, storage class, and four-worker safety bounds. EPT remains serial until live native-worker evidence permits more. Synthetic local native plans selected up to two workers under the corrected 8 GiB model. Custom workers remain an upper bound in Mission Control.

## 9. Memory Policy

Planning and execution now use one point-memory formula covering Python arrays, native PDAL overhead, existing-HAG or triangulation cost, raster working arrays, and fixed process overhead. The post-change 8 GiB EPT peak estimate is about 1.72 GiB at one worker; local native planning is about 3.07 GiB at two workers. Large unknown-size native sources no longer bypass memory subdivision.

## 10. EPT Read Amplification

The benchmark records total buffered area divided by required core area. Direct small requests are 1.0. Durable synthetic EPT cases measured about 1.45-1.58. The 50-unit CHM edge buffer remains the documented scientific policy. It was not reduced merely for speed.

## 11. HAG Performance

Existing normalized `HeightAboveGround` remains the validated default and avoids Delaunay recomputation. The runner records HAG decisions, but real read/HAG/CHM phase timings are not yet separable inside PyForestScan's combined call. This is a measurement limitation, not an inferred result.

## 12. Raster and Mosaic Performance

Durable units write buffered rasters, extract only aligned cores, and mosaic through GDAL VRT plus one transactional compressed GeoTIFF. The final exact mask is preserved. No full mosaic array is loaded into QGIS memory. A windowed final writer remains a candidate only after real I/O profiles show VRT/Translate is dominant.

## 13. PBM Startup Findings

One coordinator startup owns all durable work units and preserves process isolation from QGIS. A native crash may terminate that coordinator, after which compatible verified cores are recovered. No additional daemon/process-pool architecture was added.

## 14. Pilot Calibration

Pilot selection and calibration are tested for representative large work and memory/duration-driven resizing. Small jobs do not request a pilot. Automatic live pilot/replan remains disabled until work-unit identity migration and representative metrics are validated with real repositories.

## 15. Recovery Behavior

Checkpoint reuse still requires matching plan, grid, polygon, source, and HAG signatures plus output checksum. Memory-model changes naturally change plan signatures/work units and do not import incompatible old cores.

## 16. Current-Job Isolation

Phase 29C current-token and output-registration rules remain unchanged. One coordinator belongs to one attempt. Stale callbacks are rejected, failed/partial outputs are not registered, and Results never scans folders.

## 17. Scientific Equivalence

Structural tests preserve CRS/grid signatures, exact polygon filtering, aligned core ownership, NoData, and deterministic assembly. Synthetic numeric tests report zero maximum difference and zero RMSE for equivalent partition assembly and reject pixel or NoData changes. Real CHM equivalence across unit sizes, recovery, EPT, and LAS remains required.

## 18. Before/After Benchmark

| Scenario | Baseline EPT units | Phase 29D EPT units | Baseline peak estimate | Phase 29D peak estimate | Read amplification |
| --- | ---: | ---: | ---: | ---: | ---: |
| Small | 1 | 1 | 549 MiB | 549 MiB | 1.00 direct |
| Medium | 6 | 20 | 5,710 MiB | 1,763 MiB | 1.58 |
| Large | 88 | 315 | 5,710 MiB | 1,763 MiB | 1.47 |
| Very large | 651 | 2,542 | 5,710 MiB | 1,763 MiB | 1.45 |

This is a measured safety correction, not a speed claim: planning remains millisecond-scale, while execution uses smaller bounded units to prevent likely memory exhaustion. Real total-time before/after data is unavailable.

`scripts/analyze_polygon_job_performance.py <job-folder>` reproduces runtime/status/read-amplification summaries from durable status files without QGIS or unsafe pickle loading.

## 19. Remaining Performance Limitations

- Real EPT/LAS read, HAG, CHM, write, mosaic, mask, and peak-RSS timings are still needed.
- Ordinary LAS source-aware subdivision planning exists, but the current polygon folder path still primarily executes native selected/clipped files through Batch.
- Live pilot re-planning is not enabled.
- EPT concurrency remains one pending native-runtime evidence.
- Real numeric raster equivalence and coverage-gap tests remain RC blockers.

## 20. Phase 29E Recommendation

Run the permanent benchmark and real validation matrix on representative local LAS, network EPT, and COPC. Add backend-native stage timing around PDAL read, HAG, product calculation, and raster write. Only if those measurements identify dominant startup, overlap, or mosaic cost should Phase 29E consider coordinator pooling, buffer-policy calibration, shared multi-product reads, or a windowed mosaic writer.
