# Process LiDAR Folder by Polygon

Phase 27D adds a compact Dataset page entry point for polygon-driven folder processing preflight.

## Guided Inputs

- LiDAR folder.
- Polygon WKT and CRS.
- Output folder.
- Products.

Selected QGIS polygon feature extraction is planned for the next UI pass. The current QGIS-free core accepts WKT, supports polygon and multipolygon text, derives bounds, and validates that geometry is non-empty.

## What Preflight Does

- Recursively discovers `.las`, `.laz`, `.copc`, `.copc.laz`, and local `ept.json` sources.
- Refuses arbitrary JSON as EPT.
- Reads local `ept.json` metadata for bounds, CRS, and point count when present.
- Intersects known source bounds with the polygon envelope.
- Derives broad EPT bounds from the polygon envelope.
- Produces warnings for unknown source bounds, CRS mismatches, large source selections, and large point estimates.

## Execution Status

The current workflow is a guarded preflight/planning path. Full clipped product execution must be routed through PBM/chunked processing before it is enabled for normal users. The plugin does not read an entire folder indiscriminately.
