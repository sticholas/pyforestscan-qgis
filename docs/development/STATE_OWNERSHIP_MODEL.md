# State Ownership Model

`ProcessingEngineService` owns verification and publication. `PolygonBatchRequest.runtime_token` owns the frozen execution identity after Prerun. The coordinator consumes that identity but cannot replace it.

Phase 31H makes `ProcessingEngineStateModel` execution-authoritative. Mission Control backend/environment strings are derived UI/session compatibility fields. They must never authorize a job or supersede `processing_engine.json`.

`ProcessingEngineStateModel` is the only supported Processing Engine projection. Its status, verification time, contract hash, version, setup/repair flags, availability, and message drive the engine card and footer. Setup and repair refresh this model automatically.

## Processing Engine state

The managed environment owns installed scientific dependencies. `ProcessingEngineVerifier` owns derived readiness. `processing_engine.json` owns only cached evidence with a contract/environment fingerprint. Mission Control displays that state but does not independently infer backend readiness. Scientific batch state begins only after the engine is ready.

Repository CRS assignment has one owner: the shared user-local spatial assignment store. Catalog metadata remains raw/cache state and does not own current user intent.

The effective spatial context is the single owner of runtime interpretation. Legacy catalog CRS is input evidence only; blockers and technical diagnostics consume the same frozen context.

`BatchExecutionReadiness` owns validated source disposition and plan identity. `BatchExecutionRequest` owns the immutable standard-Batch worker launch. Mission Control owns editable inputs and a disposable `preflight_report` projection. Progress events and list-row text do not own execution inputs.

| Scope | Owner | Examples | Invalidation |
|---|---|---|---|
| Application | backend service/settings | PBM paths, compatibility | setting/backend change |
| Project | project session | workspace and project identity | project close/change |
| Session | Mission Control session | selected page, current inputs | plugin/session close |
| Current job | active job controller | one token, status, final paths | explicit new/clear/promote |
| Attempt | processing job identity | attempt ID, plan and geometry signatures | retry creates new attempt |
| Work unit | checkpoint store | status, checksum, metrics | incompatible plan/signature |
| Historical | durable job folders/history | terminal and recoverable jobs | retention policy/user action |

The current-job controller is authoritative. UI fields are projections. A callback is accepted only when its full token matches. Registry records must match job, attempt, project, plan, and polygon before automatic publication. Historical jobs never become current without explicit `make_current_and_continue` action.
# Phase 30D batch identity

The immutable current request owns its new batch folder, requested products, and product outputs. Diagnostic artifacts are separate. Historical manifests cannot become current state through output-root proximity.
# Phase 30E spatial-reference ownership

Embedded source metadata is immutable evidence. Explicit assignments belong to the file/repository fingerprint store, not the LAS header. Current job output owns a serialized provenance snapshot; QGIS project context is evidence, never silent source truth.

The source-local fallback preference belongs to the user-local application policy store. Prerun owns resolution; the immutable product request owns the frozen decision; PBM consumes it without reinterpretation. Output provenance owns the final observation/decision/preparation record.
