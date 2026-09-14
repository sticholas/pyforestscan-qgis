# Processing Attempt Diagnostics

Every polygon `Process LiDAR` launch creates an attempt ID before plugin-integrity, policy, Prerun, or runtime-token guards can return. Evidence is stored at:

```text
<batch-folder>/attempts/<attempt-id>/launch_attempt.json
<batch-folder>/attempts/<attempt-id>/engine_decision_trace.json
<batch-folder>/latest_attempt.json
```

The user-local diagnostics directory also contains `latest_processing_attempt.json`, which lets Open Diagnostics identify the newest click without mixing it with setup history.

The attempt trace begins with `PROCESS_CLICKED` and records token receipt, validation, dispatch, worker entry, failure, or completion. It includes the plugin session build ID, commit, root, critical hashes, requested products, and plan signature. Previous attempt folders are immutable evidence and are not overwritten by later clicks.

Engine decision traces additionally retain the Phase 32D Prerun token, objective dispatch comparison, managed executable, engine build identity, and current plugin session identity.
