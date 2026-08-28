# Phase 32I Progress and Cancellation

Phase 32I corrects the polygon processing projection exposed by the first real PAI/FHD run. The prior UI counted every synthetic `running` item emitted while polling the coordinator, producing impossible values such as `106/1` and duplicate dataset rows.

The corrected path keeps one row per source, derives completion from terminal entity states, and treats coordinator heartbeats as liveness only. Opaque LiDAR preparation uses an indeterminate progress bar and reports elapsed time, source size, child PID, and prepared-output growth when available.

Generic local LAS/LAZ preparation runs in a hidden Processing Engine child. Cancellation writes durable request state, terminates that owned child tree, removes a partial output, and prevents product execution. Pause means finish the current preparation step and do not begin products until resumed.

The observed Olaa run read a 3.77 GB, 104,819,538-point LAS once through `PyForestScanAdapter.normalize_heights`, then wrote a 2,005,259,826-byte clipped/HAG LAZ in about 654 seconds. Cancellation arrived during that operation but the old in-process path could only observe it afterward. No scientific product began.

## Live verification status

The pre-fix QGIS 3.44.13 run conclusively established the preparation path and failure semantics. Post-fix automated coverage validates idempotent progress, bounded heartbeat history, owned-process termination, and checkpoint reuse. A post-fix default-profile UI run was not performed while three existing QGIS sessions remained active, because replacing loaded plugin files would risk a mixed installation. That manual run remains required after those sessions are closed and the packaged ZIP is installed cleanly.
