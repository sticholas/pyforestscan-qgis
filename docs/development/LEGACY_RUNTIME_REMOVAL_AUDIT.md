# Legacy Runtime Removal Audit

| Mechanism | Phase 31H disposition | Reason |
|---|---|---|
| QGIS `PyForestScanAdapter()` default in Mission Control | Removed | Normal science is managed-engine-only |
| Default adapters in Advanced Toolbox science | Removed | Prevents local QGIS fallback |
| Batch worker default adapter factory | Removed | Folder and Polygon now explicit PBM mode |
| Per-launch `ProcessingEngineVerifier.assert_ready_for()` | Removed | Launch consumes shared authoritative token |
| Separate normal Verify Backend ritual | Removed | Setup performs final verification |
| Separate repair-plan action on normal path | Migrated | Repair invokes the setup transaction |
| `backend.json` | Keep compatibility | Installation/config metadata, not readiness |
| Legacy `verify_backend()` | Keep troubleshooting/API compatibility | Cannot publish engine READY |
| QGIS Python adapter mode | Keep managed-worker/test compatibility | Runtime boundary blocks production QGIS science |
| External worker system | Disabled/unchanged | Not a supported execution route |

A static regression scans Mission Control, Process, and Advanced Toolbox production entry points for default/auto adapters.
