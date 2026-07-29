# Real Polygon LiDAR Selection Validation

Use this checklist to validate Phase 27Q against a real local LAS/LAZ/COPC repository.

## Artifact

Record:

- plugin ZIP path and SHA256;
- commit hash;
- QGIS version;
- Windows version;
- repository root;
- polygon source;
- catalog path if used;
- repository CRS assignment source.

## Diagnostic Script

Run a read-only comparison first:

```bash
python3 scripts/audit_polygon_lidar_selection.py \
  --repository <repo> \
  --catalog <catalog.sqlite> \
  --polygon "<polygon-wkt>" \
  --polygon-crs <EPSG:code> \
  --repository-crs <EPSG:code> \
  --compare \
  --export-report <report.json>
```

Expected:

- direct scan reports real intersecting LAS/LAZ/COPC paths;
- catalog selection either matches or the discrepancy is explicitly reported;
- preflight selection method is `catalog` when the catalog is healthy and matching, or `direct_header_scan` when automatic fallback is required.

## QGIS Manual Steps

1. Install the current ZIP.
2. Open Mission Control > Batch.
3. Select Polygon Area Processing.
4. Select the LiDAR repository.
5. Select the polygon source.
6. Use Automatic selection mode.
7. Run Preflight.
8. Confirm selected source paths are real files inside the repository.
9. Run a small CHM job.
10. Confirm clipped source outputs and final GeoTIFF outputs are produced.

## Pass Criteria

- no plugin-load error;
- no false no-coverage result when direct headers show overlap;
- no EPT node-file regression;
- polygon batch manifest records `selection_method`;
- selected source paths exist on disk;
- Results can load generated outputs when clicked.

Do not mark this live validation passed unless QGIS has actually run the workflow.
