# Failure Circuit Breaker

`WorkFailureCircuitBreaker` groups failures by code, normalized signature, spatial work-unit adjacency, source job, and product context supplied by the scheduler.

- Three adjacent identical deterministic failures pause launching.
- Five identical deterministic failures are the hard-stop threshold if execution is resumed under controlled review.
- One `NATIVE_BACKEND_CRASH` stops launching immediately.
- Completed units remain verified checkpoints.
- Unstarted units remain `Pending`.

Normal progress uses work units: `2 complete, 3 failed, 5 of 120 attempted, 115 not started.` A stopped run never creates a successful mosaic with missing populated areas.


## Phase 28G Exact Polygon Completion

Expected outside-polygon and valid-NoData states do not increment failures. `FAILED_EMPTY_READ` has empty-read-specific pause/stop language, separate from HAG contract failures.
