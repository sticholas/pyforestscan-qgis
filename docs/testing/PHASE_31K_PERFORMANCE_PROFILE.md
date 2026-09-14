# Phase 31K Performance Profile

## Real Baseline

The 104,819,538-point, 24.4 ha Olaa run prepared a 2,005,259,664-byte `prepared_hag.laz` in about 247 seconds. Eight required areas each took 1,024–1,234 seconds; effective concurrency was two.

Source inspection found the decisive defect: installed PyForestScan `handlers.read_lidar()` forwards `bounds` only for EPT. The local prepared LAZ bounds were ignored, so every area loaded the complete 104.8M-point cloud before CHM.

## Controlled Read Benchmark

The same first support window returned 11,403,435 points:

- LAZ plus explicit PDAL crop: 20.55 seconds
- COPC reader bounds: 3.48 seconds
- observed old end-to-end area: 1,066.63 seconds

The first COPC conversion produced a 1,312,699,829-byte file but omitted `HeightAboveGround`; a dimension-preserving conversion did not yield a valid artifact. COPC is therefore not the new default yet.

## Managed CHM Smoke

With the production PBM DLL and GDAL/PROJ paths, the corrected adapter processed the original 11,403,435-point support window and wrote a valid CHM in 61.22 seconds. The matching old area took 1,066.63 seconds, a measured 94.3% reduction for that area. A smaller 6,505,854-point calibration completed in 53.58 seconds.

## Production Change

The adapter now uses an explicit `readers.las` plus `filters.crop` pipeline for bounded LAS/LAZ and reader-native bounds for COPC. Rumple consumes the already-created CHM and records zero LiDAR rereads. New `work_unit_timing.json` files separate bounded-read/CHM, core extraction, checksums/checkpoints, Rumple, and total time.

A full optimized eight-area rerun was not performed because the completed science was recovered without recalculation. The existing roughly 297 m cores and effective concurrency two remain selected pending a complete run; pilot timing is now persisted for future source-signature planning without mutating an active frozen plan. Exact total-job improvement remains a live RC measurement.
