# Polygon LiDAR Processing Architecture

Phase 27D introduces QGIS-free planning models for polygon-driven LiDAR folder processing.

## Modules

- `core/lidar_inventory.py`: folder request, source records, inventory cache signatures, supported source discovery.
- `core/spatial_selection.py`: polygon WKT validation and bounds derivation.
- `core/polygon_processing.py`: source intersection records, processing plan, preflight summary, workload warnings.

## Responsibilities

QGIS UI should handle polygon selection, lightweight geometry extraction, user choices, and output loading. PBM should handle point-cloud reading, exact polygon cropping, array combination, scientific processing, and output writing.

## Safe Strategy

1. Inventory source footprints before reading point data.
2. Skip non-intersecting sources.
3. Use broad bounds for EPT reads and exact polygon crop via `crop_poly=True` / `poly`.
4. Block or warn on CRS mismatches instead of silently merging incompatible sources.
5. Warn on large source/point selections and route heavy work through PBM/chunking.
6. Do not concatenate arbitrary arrays without memory checks.

## Current Limitations

Local LAS/LAZ/COPC footprint extraction requires PDAL/PBM metadata inspection and remains execution-gated. Current QGIS-free discovery records unknown bounds for local files and therefore does not select them for clipped reads until metadata inventory is available.
