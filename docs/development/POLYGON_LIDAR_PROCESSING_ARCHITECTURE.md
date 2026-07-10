# Polygon LiDAR Processing Architecture

Phase 27E keeps polygon-folder processing split between QGIS-facing selection/normalization and QGIS-free folder planning.

## Modules

- `core/lidar_inventory.py`: folder request, source records, inventory cache signatures, supported source discovery.
- `core/spatial_selection.py`: QGIS-free polygon WKT validation and bounds derivation.
- `core/polygon_source.py`: QGIS-free polygon source and normalized-selection models.
- `core/polygon_normalization.py`: QGIS-free WKT fallback normalization helpers.
- `ui/polygon_source_selector.py`: QGIS layer, selected-feature, vector-file, GeoPackage/container, CRS, dissolve, repair, and WKT extraction helpers.
- `core/polygon_processing.py`: source intersection records, processing plan, preflight summary, workload warnings.

## Responsibilities

QGIS UI handles polygon source discovery, geometry extraction, repair, dissolve, CRS transformation, and user-facing state recovery. The QGIS-free core receives a normalized WKT/CRS/bounds representation and remains testable without QGIS.

PBM should handle point-cloud reading, exact polygon cropping, array combination, scientific processing, and output writing once clipped folder execution is enabled.

## Source Modes

- `qgis_selected_features`: selected polygon features from a loaded QGIS layer. Empty selections are rejected with guidance.
- `qgis_full_layer`: all polygon features from a loaded QGIS layer, dissolved for preflight.
- `vector_file`: a QGIS/OGR-readable polygon vector file. GeoPackage and other containers expose polygon sublayers when available.
- `wkt`: Advanced fallback for direct POLYGON/MULTIPOLYGON text.

All modes normalize to `NormalizedPolygonSelection` before `build_polygon_processing_plan` runs.

## Safe Strategy

1. Inventory source footprints before reading point data.
2. Normalize and validate one Polygon/MultiPolygon processing geometry.
3. Skip non-intersecting sources.
4. Use broad bounds for EPT reads and exact polygon crop via `crop_poly=True` / `poly` when execution is later enabled.
5. Block or warn on CRS mismatches instead of silently merging incompatible sources.
6. Warn on large source/point selections and route heavy work through PBM/chunking.
7. Do not concatenate arbitrary arrays without memory checks.

## State Recovery

Mission Control exposes **Refresh Layers** to rescan current QGIS polygon layers, preserve the selected layer when it still exists, update selected-feature counts, and recover from stale layer references without crashing.

## Current Limitations

Local LAS/LAZ/COPC footprint extraction requires PDAL/PBM metadata inspection and remains execution-gated. Current QGIS-free discovery records unknown bounds for local files and therefore does not select them for clipped reads until metadata inventory is available.

Polygon-folder processing remains preflight/planning only. Product generation from a folder clipped by polygon is still deferred until PBM/chunked execution is implemented and validated.
