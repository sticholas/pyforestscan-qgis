# Processing Engine User State Contract

## Launch authority

READY is a discovery/display state. Once Prerun freezes and validates a `ProcessingRuntimeToken`, that token is authoritative for the attempt. Dispatch does not consult another READY enum. Every successful setup or Repair / Reload publishes a new `runtime_generation_id`; active Prerun state must refresh before a token from the new generation can launch.

`processing_engine.json` is the lightweight startup authority, but its persisted `READY` word is never trusted alone.

## Ready requirements

Ready requires the contract version, protocol, managed executable, environment fingerprint, plugin and setup build IDs, runner SHA256, dependency-manifest hash, product-capability hash, verification timestamp, setup-completion timestamp, and persisted status to match current expectations.

A backend directory, environment directory, `python.exe`, dependency import, old manifest, or singleton state cannot independently establish Ready. Missing managed Python is **Setup required**. A missing/corrupt manifest beside an existing environment, stale build, changed dependency contract, or changed runner is **Repair required**.

Only an explicit Set Up or Repair / Reload action can write a current-build setup marker. Each successful Repair / Reload writes a fresh `setup_completed_at`; that setup generation participates in the runtime contract hash and invalidates tokens created before reload.
