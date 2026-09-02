# Phase 32Q Adaptive EPT Execution

## Decision

Phase 32Q retains the Phase 32P planner and scientific contract. A durable coordinator dispatches independent processing regions through isolated PBM Python child processes. QGIS remains a controller and never executes concurrent PyForestScan calculations in QGIS Python threads.

Each child owns a unique region ID, request pickle, result pickle, status snapshot, diagnostics folder, temporary raster, and checkpoint. The coordinator alone owns mosaicking, exact polygon masking, output registration, and terminal state.

## Automatic policy

- Initial concurrency: 1
- Hard machine-wide maximum: 5
- Network/remote source ceiling: 2, selected from the eight-parent-region safety benchmark
- CPU ceiling: half the detected logical CPUs, capped at 5
- Numerical thread policy: each isolated region child receives one OpenMP, OpenBLAS, MKL, and NumExpr thread to prevent hidden process-by-thread oversubscription
- Memory reserve: 2 GiB for QGIS and the operating system
- Memory estimate: rolling worker RSS p90 multiplied by 1.35, then a 1.25 launch safety factor
- Ramp-up: one worker at a time after stable completions
- Backoff: stop new launches when memory pressure appears or recent EPT latency exceeds 2.25 times the initial median
- Native crash policy: first crash reduces capacity; a repeated native crash opens the circuit breaker
- Global budget: atomic machine-wide worker leases prevent separate jobs from multiplying the five-worker ceiling

Pause stops new dispatch and allows active children to checkpoint. Cancel stops dispatch and terminates only children registered to the current coordinator. Resume validates and reuses completed checkpoints.

## Parallel-safety audit

The PyForestScan adapter receives an immutable per-region request and writes only to that region's output path. PDAL readers and GDAL datasets are process-local. Scientific arrays, temporary outputs, logs, status files, and checkpoints are not shared. Environment construction happens before child launch and each process receives its own environment mapping. Shared manifests are coordinator-owned. No PyForestScan source or scientific parameter changed.

## Progress contract

The coordinator publishes a bounded latest-state snapshot with completed, active, remaining, weighted percent, rolling ETA, ETA confidence, health, target concurrency, active region IDs, child stages, and RSS. Normal UI uses “processing regions,” formats elapsed time, and shows the top-level stages Preparing, Processing, Combining results, Clipping to selected area, Saving output, Loading result, and Complete.

Worker stages are Reading LiDAR, Preparing Data, Calculating CHM, Writing Result, and Saving Checkpoint. A region taking longer than 120 seconds is not classified as stalled. A possible-stall record requires at least ten minutes without forward progress, no active worker evidence, and a missing or stale heartbeat older than thirty minutes.

## Multi-product and cache position

The scheduler model is source preparation, shared evidence, product computation, and finalization. CHM and Rumple already reuse prepared HAG evidence and CHM where their existing contracts allow it. PAI, FHD, PAD, and other products remain behind their documented PyForestScan calls; Phase 32Q does not invent shared scientific arrays.

A read-through EPT cache is deferred. The baseline shows network decode is 13.2% of wall time, while a durable point cache could consume very large storage and duplicate server-side EPT behavior. Persistent workers are also deferred because the measured fresh-process cost is roughly one second and crash isolation is more valuable.

Distributed frameworks, shared memory, GPU staging, COPC conversion caches, and Dask/Ray/joblib are future research candidates, not dependencies of this conservative scheduler.
