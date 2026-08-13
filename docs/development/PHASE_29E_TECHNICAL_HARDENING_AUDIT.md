# Phase 29E Technical Hardening Audit

## Result

The authoritative architecture is indexed in `CURRENT_ARCHITECTURE_MAP.md`. No scientific formulas, PBM installer behavior, adaptive checkpoint identities, or UI design were changed. Similar modules were retained where they represent acquisition, planning, execution, or compatibility boundaries rather than duplicates.

## Consolidation

- Product and output behavior now comes from `ProductExecutionCapabilities`; filename inference remains compatibility-only input identification.
- Terminal work-unit codes resolve through one error taxonomy without collapsing no-coverage and unexpected-empty-read semantics.
- Current/historical isolation remains token- and attempt-based and is covered by a 50-cycle soak.
- Job storage has REQUIRED, RECOVERABLE, DIAGNOSTIC, TEMPORARY, and CACHE classes plus a dry-run maintenance API. It never selects final outputs or recoverable checkpoints.
- Phase 29D telemetry is constant-time plan summarization. Benchmark and historical analyzers run only when explicitly invoked.

## Lifecycle and Safety

The durable coordinator owns one attempt and writes atomic identity, heartbeat, progress, and terminal records. The scheduler bounds concurrency, releases its thread pool, reconciles interrupted records, and validates checksums before reuse. Explicit cancellation is authoritative; crash recovery preserves checkpoints. PID-based termination must remain identity-validated; no broad process-name killing is supported. External Worker mode remains disabled.

Subprocess calls use argument arrays and sanitized PBM environments. No supported runtime path requires `shell=True`. UNC and user paths remain arguments/data, not interpolated commands. Diagnostics must not include credentials or full environments.

## Repository and Packaging

Tracked sources contain permanent diagnostics, benchmarks, release scripts, and tests; no Phase 29D scratch names are tracked. `__pycache__` files observed locally are ignored build residue, not tracked/package content. Package validation excludes tests, VCS metadata, caches, compiled files, scripts, and development documentation.

## Upgrade and Compatibility

Existing output registries remain schema-compatible. Unknown error codes map safely to UNKNOWN. Existing backend version checks remain authoritative and avoid rebuilding a compatible PBM environment. Old catalogs/jobs remain historical or recoverable and are not auto-promoted. Live upgrade and clean-machine checks remain explicitly pending in the matrix.

## Deferred

Final UX polish, live Windows clean-machine QA, destructive process-tree crash simulation, and broader scientific equivalence runs with real LiDAR remain release-path work, not claims made by this phase.
