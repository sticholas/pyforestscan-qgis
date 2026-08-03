# Direct Header Selection

Direct Header Selection is the Phase 27Q reference path for local polygon-to-LiDAR source selection.

It is intentionally boring: it scans source files, reads their headers, and applies one bbox overlap equation. This makes it useful as a fallback when a catalog is stale, empty, interrupted, or otherwise not trustworthy.

## What It Reads

For LAS, LAZ, and COPC sources, the selector attempts to read:

- file path;
- source type;
- file size and modification time;
- XY bounds;
- point count when available;
- embedded CRS when available.

EPT datasets are excluded from direct header selection because EPT roots have their own native logical-source handling.

## What It Returns

The selector returns:

- discovered file count;
- metadata-read count;
- usable source count;
- intersecting source count;
- real intersecting source paths;
- selected `LidarSourceRecord` values for Batch execution;
- rejected sources with reason codes;
- blockers and warnings.

Common rejection reasons include `CRS_MISSING`, `CRS_TRANSFORM_UNAVAILABLE`, `BOUNDS_MISSING`, `HEADER_READ_FAILED`, and `OUTSIDE_QUERY_EXTENT`.

## Diagnostics

Use:

```bash
python3 scripts/audit_polygon_lidar_selection.py \
  --repository /path/to/lidar \
  --polygon "POLYGON ((...))" \
  --polygon-crs EPSG:6635 \
  --repository-crs EPSG:6635 \
  --compare
```

By default the script is read-only. It prints direct selection, catalog selection when a catalog path is supplied, comparison results, and polygon preflight behavior. Use `--export-report` to write the JSON report.

`--rebuild-catalog` is the explicit write path. Do not use it during evidence capture unless the test step intentionally repairs/rebuilds the catalog.

## Phase 27R Notes

Phase 27R adds the stabilized ordinary-folder contract: direct header metadata is the beta correctness reference, catalogs are optional optimization, selected real paths are serialized and invariant-checked before PBM clipping, and EPT remains a separate logical-source path. See [Polygon LiDAR Stabilization](POLYGON_LIDAR_STABILIZATION.md).
