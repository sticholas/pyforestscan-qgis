# Catalog Integrity And Repair

Phase 27O adds explicit catalog identity, integrity, and repair checks for the SQLite/RTree LiDAR catalog.

## Identity

Catalog metadata records the schema version, selected repository root, normalized root, repository fingerprint, creation/update time, plugin version, header-reader version, source count, usable spatial-source count, RTree row count, and failed metadata count.

The selected repository root must match the catalog identity. A catalog from another folder is not silently reused.

## Integrity Status

- `Healthy`: source rows and RTree rows agree, and at least one usable spatial record exists.
- `Repair Recommended`: usable records exist but missing RTree rows, orphan rows, stale files, malformed extents, or missing files were detected.
- `Unusable`: source rows exist but the spatial catalog cannot be used, for example zero valid RTree rows.
- `Empty`: no catalog exists or no source rows exist for the selected repository.

## Skip Reasons

Structured reasons include `HEADER_READ_FAILED`, `CRS_MISSING`, `BOUNDS_MISSING`, `BOUNDS_INVALID`, `BOUNDS_NONFINITE`, `FILE_MISSING`, `FILE_CHANGED`, `STALE_RECORD`, `RTREE_ENTRY_MISSING`, and `RTREE_ENTRY_INVALID`.

Polygon preflight now distinguishes true no coverage from broken catalog data. The message "No LiDAR coverage" is reserved for a healthy catalog whose coverage does not overlap the polygon.

## Repair

`repair_catalog` creates a timestamped backup before structural changes. It removes orphan RTree rows, rebuilds missing RTree entries from valid source bounds, removes invalid RTree entries, marks missing files as deleted, refreshes identity metadata, and reruns integrity validation.
