# Phase 31J CHM/Rumple Preparation Matrix

| Input condition | Preparation decision | Worker behavior |
| --- | --- | --- |
| Explicit valid HAG | Reuse source | Proceed after durable COMPLETE status |
| Valid normalized Z | Materialize Z as explicit HAG | Read local prepared artifact |
| Distributed class-2 ground | Delaunay HAG | Read one prepared artifact |
| Classification without usable class 2 | SMRF then Delaunay | Proceed only after validation |
| Compatible DTM | DTM HAG | Proceed only after validation |
| Poor/invalid height evidence | Scientific blocker | No work-unit scheduler |
| Compatible checkpoint | Reuse | Canary then unfinished units |
| Source/support signature changed | Rebuild | No stale checkpoint reuse |
| Concurrent preparation | One lock owner | No duplicate writers |
| Missing/corrupt artifact | Structured source-preparation failure | No worker fan-out |

CHM and Rumple share one prepared source and one CHM support path. Rumple continues to use its established halo and final-mask contracts.
