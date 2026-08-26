# Phase 31F Clean Install Matrix

| State | Expected UI | Expected action | Job created |
|---|---|---|---|
| No backend directory | Setup required | Set Up | No |
| Valid managed engine | Ready | None | Yes |
| Network failure during setup | Setup failed | Retry | No |
| Permission failure | Setup failed with writable-path guidance | Retry after correction | No |
| Concurrent setup | Being prepared by another QGIS session | Refresh later | No |

Clean Windows/QGIS live installation remains a manual release gate. Automated tests verify state classification, locking, hidden subprocess policy, runtime identity, and package integrity.
