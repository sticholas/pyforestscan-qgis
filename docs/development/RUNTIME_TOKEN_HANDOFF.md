# Runtime Token Handoff

Phase 31I freezes one `ProcessingRuntimeToken` during Prerun and carries it unchanged through the polygon request, manifest, QGIS launcher, environment, and PBM coordinator.

The immutable identity contains the engine ID, executable, environment fingerprint, contract hash, protocol, runner hash, plugin build ID, dependency-manifest hash, product-capability hash, and verification timestamp. `processing_runtime` in `polygon_batch_manifest.json` records this provenance without secrets.

Launch uses `ProcessingEngineService.validate_runtime_token_for_launch()`. This is a lightweight integrity comparison against the published manifest and current environment fingerprint; it does not select another engine or run another verifier. Field results are written to `runtime_token_comparison.json`, and launch evidence is written to `processing_engine_launch_snapshot.json`.

Missing or changed identity fails as `ENGINE_RUNTIME_TOKEN_MISSING` or `ENGINE_RUNTIME_TOKEN_MISMATCH` with expected and observed fields. The failure stage is `runtime_prelaunch`; no scientific attempt is claimed.

Setup and Repair publish a new token and `processing_engine_snapshot.json`. Mission Control invalidates the old Prerun and rebuilds it without clearing repository, polygon, or product selections.
