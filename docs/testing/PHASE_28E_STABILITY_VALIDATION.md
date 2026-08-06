# Phase 28E Stability Validation

## Automated

- HAG reason-code and suitability contract: implemented.
- Deterministic scientific classification: implemented.
- One-worker EPT CHM safe mode: implemented.
- Three-adjacent-failure pause: implemented.
- Native-crash immediate stop: implemented.
- 120-transition scheduler soak: implemented.
- Sanitized 120-unit failure fixture: 5 attempted, 2 complete, 3 failed, 115 pending.
- PBM path isolation tests: implemented.
- Crash-safe status transitions and dead-PID reconciliation: implemented.

## Live Status

| Check | Status |
| --- | --- |
| Controlled successful bounded EPT unit | Pending |
| Known collinear unit diagnostic | Pending |
| Known empty unit diagnostic | Pending |
| QGIS close/reopen monitoring | Pending |
| PBM native runtime DLL probe on Windows | Pending |
| QGIS 3.44.9 offscreen init/unload/recreate | Pending |
| Full 120-unit live run | Blocked until pilot passes |

No live result is inferred from unit tests. Production readiness remains blocked.
