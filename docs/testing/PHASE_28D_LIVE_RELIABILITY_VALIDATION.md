# Phase 28D live reliability validation

Status: prepared, not executed in a live interactive QGIS session.

| Test | Procedure | Evidence required | Status |
|---|---|---|---|
| Backend cold start | Restart QGIS and run fast check | timings and READY/check-timeout status | Pending |
| Project isolation | Select EPT A in Project A, open Project B | footer screenshots | Pending |
| Polygon isolation | Run A then select B | current Results clears; no old CHM load | Pending |
| Failed job | force failure | zero current outputs | Pending |
| Large EPT | repeat 7,061.6 ha CHM | heartbeat/stage beyond one hour; cleanup evidence | Pending |
