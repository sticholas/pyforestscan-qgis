# PyForestScan Source / Docs Difference Audit

Installed source inspected at `/mnt/c/Users/Lama/AppData/Roaming/Python/Python312/site-packages/pyforestscan` and compared with official docs pages.

| Area | Docs status | Installed source status | Difference / action |
| --- | --- | --- | --- |
| `calculate` | Documented API page exists | Public functions match documented calculate surface | Plugin metrics tools cover safe functions. |
| `filters` | Documented API page exists | Public signatures include full SMRF parameters and `remove` flag | Phase 20E exposes full SMRF, PointSourceId, and outlier `remove` in Preprocess Point Cloud. |
| `handlers` | Documented API page exists | Public functions match docs plus helper behavior | Standalone CRS/polygon helpers remain deferred because QGIS-native providers are preferred. |
| `pipeline` | Docs page linked, but API page returned an internal server error during audit | Source contains only underscored helper functions | Treat as internal. Do not call directly from plugin. |
| `process` | `process_with_tiles` documented | Public function exists with broad EPT tiling parameters | Deferred until a QGIS-safe tiling workflow is designed. |
| `utils` | Public functions are present in installed source; not part of the main required API list | `get_srs_from_ept`, `get_bounds_from_ept`, `tile_las_in_memory` | Accounted for in full API surface and deferred features. |
| `visualize` | Documented API page exists | Public matplotlib helpers match docs | Deferred / QGIS-native visualization preferred. |

## Current Remaining Gaps

- `process_with_tiles` is not exposed as an executable toolbox algorithm.
- Matplotlib visualization helpers are not exposed because QGIS-native visualization is preferred.
- Product-level crop/bounds controls remain deferred pending a consistent vector/bounds UX.
- Standalone CRS/polygon/raster helper algorithms remain deferred to avoid low-value toolbox clutter.
