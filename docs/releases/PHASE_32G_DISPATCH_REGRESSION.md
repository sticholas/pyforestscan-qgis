# Phase 32G Dispatch Regression

## NameError

Phase 32F called `validate_runtime_token_for_launch()` but discarded its return
value. The following call referenced `runtime_comparison`, which had never been
assigned in `_run_polygon_batch()`. The live attempt therefore stopped after
`TOKEN_VALIDATED`, before dispatch or scientific work.

The fixed controller stores the one returned comparison as
`runtime_validation` and passes that exact object to manifest persistence.
The attempt records `DISPATCH_VALIDATION_STARTED` and
`DISPATCH_VALIDATION_RECORDED` before `DISPATCH_STARTED`.

The prior tests inspected source ordering and helper names but never executed
the production controller method. Phase 32G adds a QGIS-free Qt harness that
invokes the real `BatchPage._run_polygon_batch()` method and requires it to
reach `DISPATCH_STARTED` with the returned validation object.

## Identity Domains

The package build ID identifies one ZIP/plugin artifact and is intentionally
short for diagnostics. The Processing Engine `plugin_build_id` field is the
full plugin-contract fingerprint produced from managed execution and launch
surfaces. These values have different domains and are not compared.

Compatibility is decided only by `ProcessingEngineService` using the contract
fingerprint frozen in `ProcessingRuntimeToken`. Mission Control pages consume
the resulting semantic READY/REPAIR state. Diagnostics label the values as
`Package build ID` and `Plugin contract fingerprint`.

## Split Readiness

Tools & Setup previously emitted the setup transaction result while Process
relied on the canonical engine report and its freshness timestamp. Mission
Control could reject the noncanonical projection and retain an older Process
message. Setup completion now re-reads and emits
`processing_engine_state(quick=True)`, so both pages consume the same report.

## Failure Semantics

Unexpected synchronous controller exceptions now record `DISPATCH_FAILED` and
`FAILED` with category `PLUGIN`, code `DISPATCH_INTERNAL_ERROR`, exception type,
message, and traceback. The UI returns to a terminal error state while
preserving Prerun selections. Engine repair is not suggested.

The real Phase 32F attempt `20260828T185000409369Z-e7c93c7f` was repaired from
stale `LAUNCHING` to this terminal failure state. It never reached dispatch,
coordinator creation, clipping, or science.
