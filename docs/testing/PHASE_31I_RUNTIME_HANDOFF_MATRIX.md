# Phase 31I Runtime Handoff Matrix

| Scenario | Expected result |
|---|---|
| READY token and Polygon request | Token accepted; coordinator launch proceeds |
| Token absent | Prerun/development validation reports `ENGINE_RUNTIME_TOKEN_MISSING` |
| Repair publishes new token | Mission Control invalidates and rebuilds Prerun |
| Old token after Repair | `ENGINE_RUNTIME_TOKEN_MISMATCH` names changed fields |
| Folder processing | PBM execution remains explicit; no legacy QGIS auto routing |
| Two independent sources | Every work-unit ID is globally unique |
| Raw plus normalized alternative | One canonical representation is selected from combined evidence |
| Successful CRS fallback | Superseded "cannot compare" warning is removed |
| Runtime failure before coordinator | Stage is `runtime_prelaunch`; no scientific attempt is claimed |
| Large source-aware plan | Canary executes first, then full work continues automatically |

Automated coverage uses QGIS-free runtime, manifest, source-identity, checkpoint-ID, and static caller guards. Managed Windows and offscreen QGIS checks remain part of package validation evidence.
