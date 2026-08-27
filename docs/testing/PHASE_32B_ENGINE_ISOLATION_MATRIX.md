# Phase 32B Engine Isolation Matrix

| Action | Engine lookup | Scientific import/subprocess | Setup mutation |
|---|---:|---:|---:|
| `initGui()` | No | No | No |
| Construct Mission Control | No | No | No |
| Initial deferred status resolution | Lightweight quick state only | No scientific QGIS-Python import | No |
| Navigate pages or resize | No | No | No |
| View history/results/settings | No | No | No |
| Recheck Processing Engine | Yes | Existing verifier as requested | No install |
| Open Diagnostics | Yes | Existing diagnostic reads | No install |
| Set Up / Repair | Yes | Managed background transaction | Yes, user-local engine only |
| Process LiDAR | Yes | Managed runtime required | Job creation only after readiness |

The packaged QGIS smoke snapshots loaded modules before plugin import and reported no newly imported `pyforestscan`, `pdal`, or `rasterio` modules after construction and lifecycle testing.
