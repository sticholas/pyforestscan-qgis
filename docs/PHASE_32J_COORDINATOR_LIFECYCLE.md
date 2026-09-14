# Phase 32J Coordinator Lifecycle

## Root cause

Attempt `20260828T195804437268Z-c4cfa323` reused the plan-scoped directory `polygon_jobs/generic-c918a007d0a0/coordinator`. At launch, that directory still contained the prior attempt's `terminal_result.json`, `coordinator_result.pkl`, and `cancel_requested.json` for PID 27476.

The QGIS observer saw the old terminal file immediately, loaded the old skipped `BatchResult`, and returned it as current success. `_PolygonBatchExecutionWorker.run` consequently appended `FINALIZING` and `COMPLETED` at 174 and 179 milliseconds. Independently, new coordinator PID 38144 started, read the old cancel request, and terminated with `Polygon processing cancelled before source preparation.` PID 38144 did not remain alive.

## Ownership contract

Every launch now has a unique coordinator attempt directory. `CoordinatorLaunchResult` proves only OS process creation. Its `CoordinatorHandle` retains the live process identity and attempt-scoped request, progress, identity, terminal, pause, cancel, stdout, and stderr paths. The existing Qt background worker continues observing the handle without blocking QGIS's main thread.

Startup requires coordinator identity evidence. Exit before startup is `COORDINATOR_START_FAILED`. Exit after startup without `coordinator_result.json` is `COORDINATOR_RESULT_MISSING`. A durable `CoordinatorTerminalResult` must match the current attempt ID and use `SUCCEEDED`, `PARTIAL_SUCCESS`, `FAILED`, or `CANCELLED`.

`FINALIZING` follows `TERMINAL_RESULT_VALIDATED`; spawn alone cannot reach finalization. Claimed success with no completed dataset, fewer product outputs than requested, missing/empty files, or incomplete product states becomes `INTERNAL_EXECUTION_STATE_ERROR`.

## Historical prepared artifact

The previous run's 2,005,259,826-byte clipped/HAG LAZ exists, but no `*.prepared.json` checkpoint or `preparation_timing.json` accompanies it. Its source fingerprint, polygon hash, spatial interpretation, method, and successful preparation terminal state therefore cannot be verified. It is not automatically reused.

## Live QA status

Automated regressions cover stale plan-level terminal/cancel files, slow coordinator observation, attempt alias rejection, exit-zero without terminal result, zero-output success rejection, and explicit `cancel_origin=USER`. Packaged default-profile QGIS verification remains mandatory after active QGIS sessions are closed and the exact Phase 32J ZIP is installed.
