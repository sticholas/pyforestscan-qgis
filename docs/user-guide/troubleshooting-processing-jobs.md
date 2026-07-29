# Troubleshooting Processing Jobs

Use **Validate Processing Request** before a long polygon EPT run when something looks suspicious. The check verifies the PBM backend contract, EPT metadata, requested bounds, polygon file, CRS, output folder, and product settings before a full product is generated.

For EPT jobs, valid bounds must use square-bracket coordinate ranges when converted for PDAL:

```text
([xmin, xmax], [ymin, ymax])
```

If a job fails, open the job folder and inspect `diagnostics/`. The most useful files are `summary.json`, `request_validation.json`, `backend_contract.json`, `pyforestscan_arguments.json`, and `traceback.txt`.

**Test Spatial Read** is a troubleshooting-only concept. It should be run explicitly when request validation passes but the EPT reader still fails. It is not part of normal preflight because it touches the EPT source.

**Diagnostic Test Run** means validating the request and, optionally, probing the reader without generating a full CHM or other product.

Support summaries should include product, failed stage, error code, request bounds, backend versions, and the diagnostic bundle path. They should not include credentials or raw environment dumps.

## Polygon No-Coverage Diagnostics

If Polygon Area Processing finds no coverage, use Preview Spatial Selection, Zoom to Polygon, Zoom to Repository Extent, and Check Coordinate Systems. For EPT datasets, no-coverage does not mean the repository stopped being EPT.

## Phase 27O Notes

Repository discovery, catalog identity, catalog integrity, repair, source-view, coverage-model, diagnostic-export, and repository action-state services now back Polygon Area Processing setup. Broken catalogs are reported as catalog repair/readiness issues instead of generic no-coverage results. The RTree contract is `id, xmin, xmax, ymin, ymax`; EPSG:6635 overlap fixtures cover the observed polygon envelope regression.

## Phase 27P Notes

Catalog health now separates embedded CRS from effective CRS. A bounded LAS/LAZ catalog with all source CRS values missing is `CRS Assignment Required`, not healthy, and polygon preflight does not report true no coverage until comparable CRS metadata exists. Repository CRS override metadata is explicit and reversible. Live QGIS coverage/zoom services now require actual layer insertion or canvas extent changes before reporting success.

## Phase 27Q Notes

Polygon Area Processing can now compare the catalog path with Direct Header Scan for ordinary local LAS/LAZ/COPC repositories. Catalogs remain the performance path, but Direct Header Scan is the correctness fallback when catalog selection is missing or inconclusive. EPT keeps native logical-source handling. See [Polygon LiDAR Selection Contract](../development/POLYGON_LIDAR_SELECTION_CONTRACT.md) for the developer contract and [Process LiDAR Folder by Polygon](../user-guide/polygon-folder-processing.md) for user-facing guidance.
