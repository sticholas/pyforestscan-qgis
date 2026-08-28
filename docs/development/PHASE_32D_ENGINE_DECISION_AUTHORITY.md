# Phase 32D Engine Decision Authority

## Root cause

Polygon Prerun froze and successfully compared a `ProcessingRuntimeToken`, but PAI/FHD followed the generic logical-product route. `PyForestScanAdapter._run_pbm_product_if_selected()` then called `BackendExecutionService.can_execute_processing()` and `run_processing_job()` could discover another token. This second readiness decision could disagree with the already validated launch identity and was translated into the generic repair message. CHM/Rumple's durable coordinator already carried the frozen token explicitly, which made the defect product-route specific.

## Resolution

`execute_polygon_batch()` now validates the frozen request token once, binds that exact token to its adapter, and writes `engine_decision_trace.json`. Every routed product passes the token into its backend job specification. Launch validates objective manifest/runtime invariants without consulting the display/discovery READY enum. The managed runner independently checks its observable executable, protocol, runner, plugin build, dependency, and product-capability values.

The trace records UI projection, Prerun state, immutable token, dispatch comparison, service identity, requested products, runner executable, execution mode, and the `polygon_managed_engine` route. The polygon manifest embeds a concise `runtime_validation_at_dispatch` record.

