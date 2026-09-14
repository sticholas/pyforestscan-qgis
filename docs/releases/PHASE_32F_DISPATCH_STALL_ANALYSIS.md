# Phase 32F Dispatch Stall Analysis

## Incident

Attempt `20260828T174311319620Z-2dbc2d7e` stopped after `DISPATCH_STARTED`. The
11 ms handoff interval produced no job directory, coordinator identity, worker
artifact, heartbeat, clipped source, or scientific output.

## Root Cause

The QGIS main thread called `QThread.start()` and then appended
`DISPATCH_STARTED`. The new worker simultaneously appended `WORKER_STARTED`.
Both writers used the same `launch_attempt.json.tmp` path. One atomic replace
could remove the other writer's temporary file. The worker append was outside
its exception boundary, so that diagnostics exception escaped the Qt slot
before `execute_polygon_batch()` and before a failure signal. The QThread event
loop remained active and Mission Control continued to project RUNNING.

The 40-minute interval was therefore not LiDAR clipping or PAI/FHD processing.
Scientific work never started.

## Corrected Handoff

The main thread now records `DISPATCH_STARTED` before starting the QThread.
Attempt updates are serialized by a process-local reentrant lock and each
atomic write uses a unique temporary name. Diagnostics failures return safely
and cannot abort processing. Every stage records process ID, thread ID, main
thread status, timestamp, and elapsed milliseconds.

The state sequence is now:

1. `STARTING` after the click.
2. `LAUNCHING` during validation, serialization, and process creation.
3. `RUNNING` only after owned worker/process evidence.
4. `FINALIZING` while terminal outputs are registered.
5. `COMPLETED`, `FAILED`, or `CANCELLED` at a terminal boundary.

## Generic Polygon Execution

Local LAS/LAZ PAI and FHD previously prepared a polygon-clipped, normalized
source from the QGIS process's Qt worker before product execution. The main Qt
GUI thread was not doing that work, but ownership and progress were weak and a
large source could consume substantial memory in the QGIS process.

Generic polygon work now launches a detached, runtime-token-validated PBM
coordinator first. The managed process owns bounded polygon preparation,
height normalization, and the existing product execution path. QGIS only
serializes the frozen report, launches the coordinator, and observes durable
progress. The coordinator writes identity, PID, request path, five-second
heartbeats, stage transitions, terminal result, and traceback on failure.

One prepared polygon source is reused by the existing batch request for PAI
and FHD, avoiding separate full-source preparation for each product. Scientific
equations, bins, normalization request, CRS contract, and polygon mask behavior
are unchanged.

## Runtime Consistency

Click-time token validation is persisted before background launch. The current
polygon manifest is rewritten from that validation so
`processing_runtime.runtime_generation_id`, dispatch generation, and the
attempt's `TOKEN_RECEIVED` generation describe the same launch.

## QA Status

QGIS-free concurrency, ordering, managed-route, heartbeat, manifest handoff,
and state tests pass. Full automated validation is required for every package.
The real 104.8-million-point UNC source and bounded pilot require the default
Windows QGIS profile and test data; they are not represented as completed by
repository-only validation.
