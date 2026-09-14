# Phase 32C Deterministic Setup UX

Phase 32C makes Processing Engine readiness an explicit, current-build contract. Mission Control performs only a lightweight manifest read at startup. It does not launch Micromamba, Conda, pip, PDAL, managed Python, or network activity.

## User states

- **Setup required:** no managed Python is present. The primary action is **Set Up Processing Engine**.
- **Ready:** the persisted setup marker and complete runtime contract match the current plugin build. **Repair / Reload Processing Engine** remains available.
- **Needs attention:** the environment is partial, stale, incompatible, or has a missing/corrupt setup record. The recovery action is **Repair / Reload Processing Engine**.

Both buttons run `ensure_processing_engine_ready()`. The transaction verifies the current runtime, invokes the managed installer only when reconciliation is needed, verifies again, records current-build setup completion, publishes state, and refreshes Mission Control. Repeating it against a valid environment does not reinstall packages.

The former normal **Recheck Processing Engine** action is removed. Technical state remains available through **Open Diagnostics**.

## Spatial intervention

Tools & Setup no longer displays a permanent LiDAR spatial-reference card. The Process page shows compact CRS or units controls only when preflight reports that specific blocker. A successful assignment is persisted, the panel disappears, and preflight runs again without clearing input, area, product, or output selections.

