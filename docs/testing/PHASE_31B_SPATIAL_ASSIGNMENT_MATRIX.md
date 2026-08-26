# Phase 31B Spatial Assignment Matrix

| Case | Expected | Automated status |
|---|---|---|
| Existing HAG, no CRS | source-local fast path | Covered by Phase 30E/31A regressions |
| Missing HAG, class 2, metres | Delaunay then products | Pass |
| Missing HAG, class 2, international/US survey feet | canonical parameter conversion | Pass |
| Missing HAG, no ground, known units | SMRF then Delaunay | Covered by Phase 31A matrix |
| Missing HAG, assigned CRS | derive units, georeferenced output | Pass for assignment/profile propagation |
| Missing HAG, unknown units | one resolvable input request | Pass |
| Polygon plus units only | CRS required | Pass |
| Polygon plus assigned CRS | spatial alignment permitted | Pass at resolver boundary |

## Managed Windows PBM evidence

The installed managed backend Python 3.12.13 passed 41/41 focused Phase 30E, 31A, and 31B tests. GDAL emitted `Cannot find gdalvrt.xsd (GDAL_DATA is not defined)` during existing raster tests, but all operations passed. This matrix verifies managed package imports and execution boundaries; live QGIS selector/output loading still requires QGIS runtime evidence and is not claimed by QGIS-free tests.
