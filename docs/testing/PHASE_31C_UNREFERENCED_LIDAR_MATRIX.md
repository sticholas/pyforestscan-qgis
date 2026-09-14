# Phase 31C Unreferenced LiDAR Matrix

| Case | Expected | Automated |
|---|---|---|
| Unknown CRS/units, existing HAG, CHM | source-local assumed units, ready | Pass |
| Unknown CRS/units, class 2, CHM | assumed metres, Delaunay | Pass |
| Unknown CRS/units, class 2, Rumple | assumed metres, Delaunay | Pass |
| CHM + Rumple | one compatible preparation identity | Pass |
| No observed class 2 | assumed units, SMRF then Delaunay | Pass |
| Explicit metres/feet | trusted assignment overrides policy | Pass |
| Known CRS | embedded/CRS-derived authoritative units | Pass |
| Unknown CRS plus polygon | block for CRS | Pass |
| Contradictory evidence | block | Pass |
| Independent unknown-source batch | per-source fallback | Pass at resolver/preflight boundary |
| Cross-source alignment | compatibility required | Pass |
| Assumed metres changed to trusted feet | checkpoint invalidated | Pass |
| Prerun context versus execution context | immutable fields agree | Pass |

No global warning acknowledgement is used. `SOURCE_UNITS_ASSUMED` is a warning/provenance state; `SOURCE_CRS_REQUIRED` and scientific quality failures remain blockers.

## Managed Windows PBM evidence

The installed PBM Python 3.12.13 passed 56/56 focused Phase 30E, 31A, 31B, and 31C tests. Existing raster tests emitted the known non-failing `GDAL_DATA`/`gdalvrt.xsd` warning. The matrix includes managed-package Delaunay, SMRF, checkpoint, CHM, Rumple, and immutable prerun-context regressions.
