# Phase 32H Plan and Dispatch Lifecycle

## Root Cause

`write_polygon_batch_manifest()` always read the batch-level
`engine_decision_trace.json` and copied its dispatch generation into every new
Prerun manifest. A dispatch from runtime generation `83caf...` therefore
remained in a plan frozen against generation `c86fe...`. The Phase 32G manifest
validator detected the objective mismatch, but it had no plan-versus-execution
lifecycle parameter, so Detailed Check treated historical attempt evidence as
a current plan blocker.

This was a plan persistence defect, not Processing Engine damage.

## State Ownership

Processing Engine state is owned by `ProcessingEngineService` and reports
READY, SETUP_REQUIRED, or REPAIR_REQUIRED from objective runtime compatibility.

The reusable Prerun plan owns inputs, polygon, products, options, source and
spatial selection, plan signature, and its frozen Processing Runtime Token. It
does not require dispatch evidence.

Each Process click creates an attempt that owns dispatch validation,
coordinator launch, progress, and terminal state. Attempt metadata cannot
change current engine readiness or poison a later plan.

## Manifests

`polygon_batch_manifest.json` is plan-scoped. It records `lifecycle` as
`PRERUN_PLAN`, a plan ID/signature, and the frozen runtime generation. The
backward-compatible `runtime_validation_at_dispatch` field is always `null`.

At Process click, the attempt folder receives:

- `dispatch_validation.json`
- `polygon_execution_manifest.json`
- `engine_decision_trace.json`
- `launch_attempt.json`

The execution manifest requires exact equality among plan runtime generation,
attempt token generation, and dispatch-validation generation.

## UI Behavior

After Repair/Reload reports READY, Process immediately shows the engine as
Ready. An existing plan is invalidated and projected as Refreshing while
Prerun is automatically regenerated from preserved selections.

Detailed Check reports Engine, Plan, Spatial, Products, and Dispatch
independently. Before Process is clicked, Dispatch is `Not started` and is not
a blocker.

## Diagnostics and Paths

Opening advanced diagnostics rereads `latest_processing_attempt.json` and does
not cache an earlier attempt outcome. The historical Phase 32G attempt remains
FAILED and has no effect on current readiness.

Windows attempt paths are serialized through `json.dumps()` and round-trip as
ordinary strings; JSON escaping does not create bell, backspace, tab, newline,
or carriage-return characters.
