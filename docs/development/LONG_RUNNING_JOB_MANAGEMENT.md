# Long-running job management

Source-aware safe mode bounds active workers and in-memory process output. Deterministic circuit breakers preserve completed checkpoints and leave unstarted work pending for review or restart reconciliation.

Automatic processing uses a startup limit and heartbeat/no-progress monitoring, with no universal wall-time limit. A custom maximum remains an advanced policy. Heartbeats are written atomically to `progress/heartbeat.json` and identify the job, attempt, PID, product, stage, activity, and timestamp. Quiet scientific computation is not considered stalled while heartbeats remain current.

The retained 7,061.6 ha EPT CHM run produced request-validation and PDAL-pipeline diagnostics at 2026-08-05 19:24:57 UTC, then no progress events, result, raster, stdout, or stderr. Its last confirmed stage was Reading LiDAR. Because the old runner emitted no heartbeat, whether it was computing, blocked on network I/O, or stalled is indeterminate.

At 1 m resolution its 10,989.9 m by 6,667.7 m envelope is approximately 10,990 columns by 6,668 rows (73,281,320 cells), classified Large. A float32 band is about 280 MiB before working arrays. Current products can still materialize large point subsets in memory; product tiling remains disabled until scientific equivalence and seam behavior are validated.
## Phase 28E
Unlimited wall time is normalized through `has_wall_time_limit`; monitor stalls, explicit limits, and child scientific failures retain distinct terminal causes. Heartbeats include real elapsed time and work counts.

## Coordinator boundary

The PBM coordinator contract is QGIS-free. Full live submission and reconnect integration remains a prerelease blocker.
