# Phase 30E CRS Resolution Matrix

| Case | Expected | Automated |
|---|---|---|
| LAS/LAZ embedded EPSG | Authoritative | Resolver fixture |
| COPC WKT | Authoritative normalized horizontal CRS | Normalization fixture |
| EPT authority/WKT/compound | Authoritative | EPT resolver fixture and existing Phase 27S tests |
| EPSG vs WKT | Equivalent | Resolver fixture and `crs_alignment` tests |
| Exact `.prj`/`.wkt` | Authoritative sidecar | Resolver fixture |
| Exact QGIS datasource assignment | High confidence | Resolver fixture |
| 90 known + 10 unknown | Repository inheritance | Resolver fixture |
| Mixed known systems | Conflict | Resolver fixture |
| Persisted assignment | Remembered until fingerprint changes | Resolver fixture |
| Unknown standalone | Source-local | Resolver and adapter fixtures |
| Unknown plus polygon | Ambiguous/block | Adapter fixture |
| Different known polygon/source CRS | Exact geometry transformed | Existing `crs_alignment` suite |
| Source-local output | No CRS; provenance tags | Raster writer fixture |

Live QGIS/PBM validation was not available in this development environment and is not claimed.
