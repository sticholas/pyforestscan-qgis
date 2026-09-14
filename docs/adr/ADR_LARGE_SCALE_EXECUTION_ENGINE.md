# ADR: Large-Scale Execution Engine

Status: Accepted for research roadmap, 2026-09-01.

## Decision

Keep the custom durable coordinator and PyForestScan scientific boundary. Do not add Dask, Ray, CUDA, COPC conversion, or AI dependencies to the production Processing Engine in Phase 32N.

## Evidence

- Current “stall” was CPU_ACTIVE: three child checkpoints in 10.2 seconds while parent state did not transition.
- Direct bounded EPT read was 0.709 seconds; full child science/checkpoint was 3.719 seconds.
- Warm immutable cache open was 0.008 seconds.
- Fresh scientific process startup median was 1.082 seconds.
- Coarse hierarchy pruned 39.4% of envelope candidates.
- Morton ordering reduced center travel 49.6%.
- Installed live plugin is Phase 32L, so Phase 32M comparative claims are blocked until restart.

## Roadmap

### Phase 32O: truthful telemetry and locality-aware execution

Add child PID/stage/CPU/I/O/output-growth telemetry, adaptive stall/ETA ranges, Morton ordering, and an opt-in immutable ReadBlock cache behind a rollback flag. Expected benefit: eliminate false alarms and improve warm/overlap/restart locality. Risk: cache-key or telemetry errors. Dependency footprint: standard library plus existing NumPy/PDAL. Scientific impact: none; PyForestScan calls unchanged.

### Phase 32P: hierarchy-informed planning and compact manifests

Read only relevant EPT hierarchy pages, reject unoccupied regions before parent materialization, separate ReadBlock/ScienceBlock/CheckpointTile, and compact skipped grid ranges. Expected benefit: less planning state and fewer useless reads. Risk: EPT octree-bound interpretation. Rollback: envelope planner remains selectable. Scientific impact: none after equivalence gate.

### Phase 32Q: isolated persistent-worker experiment

Benchmark a small worker pool with fixed task-count recycling against fresh processes. Consider a Dask/Ray hybrid only if the custom scheduler, rather than I/O/science, remains limiting. Expected benefit: recover about one second of startup per short child. Risk: native-state accumulation and weaker crash isolation. No production promotion without repeated crash/memory/equivalence tests.

### Later: optional AI-derived products

Separate imagery and point-classification environments, provenance, product IDs, and QA. These are additions, never replacements for PyForestScan structural science.

## Consequences

The next work is measurable and reversible. Single-machine Windows/QGIS remains the supported center of gravity, while ReadBlock and durable task contracts leave room for later distributed execution.
