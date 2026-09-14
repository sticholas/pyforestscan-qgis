# Processing Engine Setup Transaction

## Runtime handoff

Successful setup publishes a fresh runtime generation. Mission Control rejects delayed state projections older than the accepted verification timestamp, invalidates existing Prerun readiness, and reruns Prerun when active selections exist. Setup remains separate from launch: dispatch consumes the newly frozen token and never invokes setup or readiness discovery.

## Authoritative ensure operation

Set Up and Repair / Reload both call `ensure_processing_engine_ready()`. It first performs a full managed-runtime reconciliation. A valid runtime is reverified and marked for the current plugin build without reinstalling packages. An invalid runtime enters the existing locked installer transaction, then receives final verification and the current-build setup marker. Successful completion republishes a fresh runtime token; failure remains non-Ready and exposes its concise reason plus diagnostics.

Successful setup writes `processing_engine_snapshot.json`, publishes a new token, and emits the shared state event. Existing Prerun requests are invalidated and rebuilt with that new token while user selections remain intact.

The normal **Set Up** and **Repair** actions call the same `setup_processing_engine()` transaction on a background Qt worker.

1. Inspect the existing engine contract.
2. If already correct, persist final verification and publish Ready.
3. Otherwise acquire the cross-process setup lock.
4. Run the existing transactional installer/repair path for the complete dependency manifest.
5. Verify managed Python, protocol, runner, dependency versions, required modules, required functions/signatures, and all advertised product capability smoke checks.
6. Compute engine identity and hashes.
7. Atomically write `processing_engine.json`.
8. Publish Ready and refresh every UI projection.
9. Release the lock.

Failure never publishes Ready and does not create a LiDAR job. The normal UI requires no second Verify action. **Recheck Processing Engine** remains collapsed under Troubleshooting.

Setup remains user-local, hidden-window, non-admin, and isolated from QGIS/system Python and global environment variables.

## Phase 32A UI contract

The normal Tools & Setup page exposes one contextual engine-changing action. **Set Up** and **Repair** are two labels for the same authoritative transaction, selected from verified engine state. Ready hides the action. **Recheck Processing Engine** is read-only and **Open Diagnostics** consolidates compatibility, dependency, path, version, and log evidence. Standalone preview, compatibility verification, manual setup, backend-folder, and log buttons are intentionally absent.
