# Work-unit scheduler

The scheduler now transactionally records `Pending`, `Starting`, `Running`, and terminal states before launching subsequent work. Progress reports complete, failed, attempted, and pending work units rather than source datasets.

`PolygonProductWorkScheduler` enforces one-to-four internal workers and a plan-derived lower limit. It persists checksum and plan signature after every completed core, retries transient failures, and does not retry deterministic geometry/HAG failures identically.

Pause stops new submissions while active units reach checkpoints. Cancel prevents new work and cancels queued futures. Resume verifies signatures/checksums and skips completed cores. Invalid checkpoints rerun. The outer Batch record remains one logical polygon job; External Worker mode stays disabled.

## Durable terminal ordering

Terminal unit state is persisted before circuit-breaker progress or another launch. Breaker history can be reconstructed.


## Phase 28G Exact Polygon Completion

Successful terminal states now include `CompleteNoData` and `SkippedOutsidePolygon`; neither reaches the circuit breaker. Durable status files remain authoritative for resume and progress.


## Phase 28H Adaptive Scale and Compact Workspace

Adaptive planning may provide one fast-path unit or hundreds of bounded units. Scheduler concurrency remains memory/CPU bounded and EPT remains serial by default; unit count is never a target.
