# Durable PBM Job Coordinator

The QGIS-free coordinator records identity, heartbeat, authoritative progress, command acknowledgements, and terminal results using atomic files. It has no Qt or widget dependency.

Automated tests validate durable state and observer absence. Production polygon submission and live QGIS close/restart validation remain release blockers; this prerelease does not claim they are proven.


## Phase 28G Exact Polygon Completion

Coordinator progress is rebuilt from durable per-unit status files, including candidate, required, skipped, CompleteNoData, failed, pending, running, and attempted counts.
