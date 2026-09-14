# Phase 32Q Production Performance Baseline

## Authoritative fixture

The completed Phase 32P run at `ept-1d62cdc8acd2/ept-full` is the control. It processed one 8,968.6 ha polygon from a network EPT source in EPSG:6635 at 1 m resolution, with a 50 m CHM support buffer. All 109 required regions completed, no region failed, finalization completed, and the final CHM was produced.

- Wall time: 9,847.953 s (2h 44m 8s)
- Parent processing regions: 109
- Bounded EPT subreads: 981 (nine per parent region)
- Points decoded: 2,518,468,129
- Final parent output bytes: 320,387,809
- Runtime generation: `ed368eefe86d42abb86f2dde6dd9639c`
- Backend contract: `7935114...` (full value retained in the durable runtime trace)

The reproducible parser is `scripts/analyze_phase32q_baseline.py`.

## Region distributions

| Measure | Mean | P50 | P75 | P90 | P95 | Maximum |
|---|---:|---:|---:|---:|---:|---:|
| Parent total (s) | 89.873 | 86.453 | 96.234 | 112.172 | 122.003 | 153.593 |
| Parent bounded read + CHM (s) | 89.609 | 86.172 | 96.000 | 111.725 | 121.694 | 153.172 |
| Core extraction (s) | 0.205 | 0.188 | 0.250 | 0.300 | 0.322 | 0.469 |
| Checkpoint/checksum (s) | 0.032 | 0.031 | 0.032 | 0.063 | 0.078 | 0.172 |
| Subread science (s) | 9.365 | 7.672 | - | - | 18.081 | 31.785 |
| EPT read/decode (s) | 1.324 | 1.124 | - | - | 2.652 | - |
| HAG contract (s) | 1.296 | 1.035 | - | - | 2.754 | - |
| PyForestScan CHM (s) | 5.880 | 4.647 | - | - | 12.070 | - |
| Raster write (s) | 0.046 | 0.033 | - | - | - | - |

The largest parent took 153.593 s, 1.71 times the median. This is legitimate long-region behavior, not evidence of a stall by itself.

## Wall-time accounting

| Category | Seconds | Share of wall |
|---|---:|---:|
| PyForestScan CHM | 5,768.712 | 58.58% |
| EPT access and point decode | 1,298.993 | 13.19% |
| HAG contract/preparation | 1,271.749 | 12.91% |
| Other bounded-child science/orchestration | 847.303 | 8.60% |
| Parent process/assembly overhead | 580.582 | 5.90% |
| Core extraction | 22.368 | 0.23% |
| Raster creation/write | 44.738 | 0.45% |
| Checkpoint/checksum | 3.512 | 0.04% |
| Startup/finalization/idle and other unaccounted wall | 51.842 | 0.53% |

`KNOWN_TIME` is 9,796.111 s at the parent level. `UNACCOUNTED_TIME` is 51.842 s. Fine-grained CPU utilization, network bytes, peak RSS, mosaic, mask, registration, and QGIS loading were not recorded by this historical run, so those categories cannot be separated honestly. Phase 32Q adds child RSS and stage evidence for future runs.

## Bottleneck conclusion

PyForestScan science is the largest measured component. EPT and HAG access are material but smaller. Core extraction, raster write, and checkpointing are not meaningful optimization targets. The eligible optimization is orchestration: overlap independent bounded regions in isolated PBM child processes without changing the scientific request.

## Historical comparison

Older jobs are not equivalent controls unless source, bounds, point density, HAG path, resolution, and network conditions match. The completed fixture decoded 2.52 billion points from network EPT and spent 58.6% of wall time in PyForestScan. The apparent regression is therefore primarily explained by workload and serial region execution; current evidence does not identify checkpoint or finalization overhead as a material regression.
