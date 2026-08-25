# State Ownership Model

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
