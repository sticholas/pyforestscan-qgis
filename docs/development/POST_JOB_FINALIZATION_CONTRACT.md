# Post-Job Finalization Contract

Scientific terminalization and Mission Control presentation are separate phases.

## Required order

1. Complete backend work and persist its terminal result.
2. Verify primary outputs and exact polygon masking.
3. Persist the output registry and logical terminal state.
4. Build `CompletedJobSummary` from the terminal result, execution plan, checkpoints, and registry.
5. Refresh Results and optionally load primary outputs.
6. Apply the terminal UI state in a `finally` block.

A failure in steps 4 or 5 does not change successful science to failed. Mission Control records `POST_JOB_FINALIZATION_FAILED`, retains the outputs, reports `COMPLETE_WITH_WARNING`, and unlocks controls. The summary must never query deprecated run-definition widgets after execution.

## Output roles

- **Primary:** the Rumple GeoTIFF.
- **Secondary:** the scalar Rumple CSV.
- **Supporting:** CHM produced for a Rumple-only request.
- **Intermediate:** buffered and core work-unit rasters.
- **Diagnostic:** requests, checkpoints, logs, and state snapshots.

Automatic QGIS loading includes primary outputs only. Manual Results loading may include supported secondary tables.

## Recovery

Terminal results replace transient progress events in the review model. Refresh reconstructs the completed summary from durable state. Per-product checkpoints permit a verified CHM to be reused when Rumple derivation fails later; plan signatures and checksums prevent adoption of stale artifacts.
