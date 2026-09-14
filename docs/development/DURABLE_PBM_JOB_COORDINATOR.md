# Durable PBM Job Coordinator

The QGIS-free coordinator records identity, heartbeat, authoritative progress, command acknowledgements, and terminal results using atomic files. It has no Qt or widget dependency.

Automated tests validate durable state and observer absence. Production polygon submission and live QGIS close/restart validation remain release blockers; this prerelease does not claim they are proven.


## Phase 28G Exact Polygon Completion

Coordinator progress is rebuilt from durable per-unit status files, including candidate, required, skipped, CompleteNoData, failed, pending, running, and attempted counts.


## Phase 28H Adaptive Scale and Compact Workspace

Foreground observation now carries a current-job token. Historical coordinator callbacks remain durable but cannot mutate the active Mission Control result or trigger automatic loading.
# Phase 30B

The polygon coordinator now carries shared CHM/Rumple product state and retains verified work-unit artifacts for resume. Terminal backend state is authoritative over the Mission Control UI projection.
