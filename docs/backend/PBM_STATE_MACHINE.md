# PBM State Machine

PBM uses an explicit backend state machine so users and developers can understand what is safe to do next.

```mermaid
stateDiagram-v2
    [*] --> NotInstalled
    NotInstalled --> Installing: future Install Backend
    Installing --> Verifying: install files created
    Verifying --> Ready: required checks pass
    Verifying --> RepairRequired: partial or invalid backend
    Verifying --> Failed: unrecoverable verification error
    Ready --> Updating: future Update Backend
    Updating --> Verifying: update complete
    Ready --> Removing: future Remove Backend
    Removing --> NotInstalled: backend removed
    RepairRequired --> Installing: future Repair Backend
    Failed --> RepairRequired: user retries / repair possible
```

## States

| State | Meaning in Phase 22D |
| --- | --- |
| Not Installed | Backend root or required files are absent. This is expected before PBM installation exists. |
| Installing | Reserved for future installer orchestration. |
| Verifying | Reserved for active verification workflows. |
| Ready | Config reports ready and required backend files/dependencies verify. |
| Repair Required | Partial backend files, unreadable config, or missing required dependencies were detected. |
| Updating | Reserved for future update orchestration. |
| Removing | Reserved for future removal orchestration. |
| Failed | Reserved for failed backend operations. |

Phase 23C can report states, verify existing files, preview manifest-driven installation, report QGIS compatibility, plan repairs, write structured logs, and run guarded transactional installer mechanics for Windows internal beta builds after confirmation. Linux/macOS installer execution, repair execution beyond retry guidance, update, remove, and broad backend processing execution remain planned.
