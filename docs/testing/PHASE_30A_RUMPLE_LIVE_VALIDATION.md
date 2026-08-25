# Phase 30A Rumple Live Validation

| Scenario | Status |
|---|---|
| PBM runtime raster/scalar/georeferencing | Passed live (managed backend) |
| QGIS 3.44.9 offscreen imports/core | Not tested: launcher absent from local 3.44.9 install |
| QGIS 3.44.13 offscreen imports/core | Failed before plugin import: local QtCore DLL load failure |
| Small LAS CHM + Rumple visual alignment | Not tested live |
| Small EPT polygon Rumple-only | Not tested live |
| CHM + Rumple one-computation evidence | Not tested live |
| Irregular polygon and holes | Not tested live |
| Sparse LiDAR gap | Not tested live |
| Medium/large adaptive seam check | Not tested live |
| Consecutive current-job isolation | Not tested live |

Automated mathematical evidence is recorded separately. Unperformed interactive tests remain explicit release blockers.
