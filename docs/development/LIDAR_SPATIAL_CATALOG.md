# LiDAR Spatial Catalog

Phase 27G adds a persistent indexed catalog for Polygon Area Processing. The catalog prevents normal polygon runs from recursively scanning very large LiDAR repositories.

## Purpose

Large repositories may contain millions of files. Polygon Area Processing now separates maintenance from execution:

1. Build or update a catalog once from Mission Control > Batch.
2. Select a polygon.
3. Preflight queries the catalog RTree index using the polygon envelope.
4. Execution opens only matched sources and clips them to the exact polygon.

Normal polygon preflight does not rebuild the catalog and does not enumerate the repository.

## Database

The default catalog location is:

```text
<lidar_root>/.pyforestscan/lidar_catalog.sqlite
```

If a future workflow cannot write beside the repository, the catalog model supports a workspace fallback under `.pyforestscan/catalogs/<stable-root-id>.sqlite`.

SQLite is used with an RTree table for XY source bounds. The schema stores one row per source:

- source id and relative path
- source type: LAS, LAZ, COPC, COPC LAZ, or local EPT
- xmin/xmax/ymin/ymax and optional zmin/zmax
- CRS when metadata exposes it
- point count
- file size and modified time
- header signature
- inventory status: indexed, error, or deleted
- metadata error text when inspection fails
- indexed timestamp and root id

Indexes are created for relative path, source type, modified time, root id, and inventory status. Bounded polygon queries use the RTree intersection predicate.

## Catalog Build Strategy

The builder is QGIS-free and designed for large trees:

- streaming `os.walk` traversal
- supported-source filtering before metadata inspection
- no complete sorted path list
- no point-array reads
- batched SQLite commits
- unchanged-file skipping by path, size, and modified time
- deleted-file marking after update passes
- explicit metadata error rows
- progress callbacks for discovered/indexed/unchanged/error counts

The first build can take time on very large repositories. It is a distinct maintenance action and should be started deliberately from Batch.

## Header Inspection

EPT sources read only `ept.json` metadata. EPT data nodes are not crawled.

LAS/LAZ/COPC sources use the LAS public header where available to read bounds and point count without reading point arrays. CRS extraction for local LAS/LAZ/COPC remains limited until PBM/PDAL metadata inspection is wired into the catalog worker. When metadata cannot be read, the row is recorded as an error and the user can update/retry the catalog later.

## Query Strategy

Polygon Area Processing derives an automatic envelope from the normalized Polygon/MultiPolygon geometry. The broad envelope is used for catalog and EPT reads; the original polygon WKT is retained for exact clipping.

The catalog query uses:

```sql
xmin <= polygon_xmax
xmax >= polygon_xmin
ymin <= polygon_ymax
ymax >= polygon_ymin
```

The query returns candidate count, selected records, metadata error count, skipped count, estimated points, estimated input bytes, query time, and threshold warnings.

## Execution Strategy

For EPT sources, the automatic envelope is passed as PyForestScan EPT bounds:

```text
([xmin, xmax], [ymin, ymax])
```

The exact polygon WKT is also passed so `read_lidar` can crop to the polygon.

For local LAS/LAZ/COPC, the catalog prevents non-intersecting files from being opened. The EPT bounds parameter is not used for local sources; exact polygon WKT is passed for cropping.

After products are generated, raster outputs are passed through a best-effort polygon mask using rasterio and shapely when available. Cells outside the exact polygon are set to NoData and metadata tags record polygon clipping. Rumple scalar CSV remains scalar.

## Safeguards

Default thresholds are conservative:

- maximum candidates per run: 10,000
- maximum estimated points: 250,000,000
- maximum estimated input bytes: 250 GiB
- header workers default: 2
- commit batch size: 500
- checkpoint interval: 5,000 discovered sources

Very large selections produce warnings before execution. External Worker mode remains disabled.

## Extension Points

The catalog builder supports include/exclude patterns, source-type filters, max traversal depth, hidden/temp/archive folder ignoring, and future repository-specific path adapters. Filename-based spatial inference is not assumed unless a future documented adapter supplies it.

## Phase 27H Responsive Jobs

Phase 27H adds lightweight repository selection, bounded Quick Probe, durable catalog job state, single-writer locks, pause-after-current-chunk, resume, stage/counter progress, and a PBM runner entrypoint (`pyforestscan_qgis.backend_runner.run_catalog_job`).

The Batch UI starts catalog work only from explicit Build/Update/Resume actions. Folder browse, pasted path use, page open, workspace restore, and Refresh Catalog Status do not call `os.walk`, recursive globbing, header inspection, or catalog building.

Catalog build/update remains streaming: traversal yields incrementally, SQLite commits are batched, seen paths are written to a temporary SQLite table for deletion reconciliation, and unchanged files are skipped before metadata inspection.

## Progress And State Files

Catalog jobs write JSON state under `catalog_jobs/` beside the catalog and use a `.lock` file to prevent concurrent writers. States are queued, running, pausing, paused/interrupted, completed, and failed. Stages are Preparing, Discovering Sources, Reading Metadata, Writing Spatial Index, Detecting Deleted Sources, Verifying Catalog, Finalizing, and Ready.

Progress starts as indeterminate while the total repository size is unknown. Counters and rate are preferred over fake exact percentages. ETA remains pending until enough information exists to make it honest.

## Filesystem Profiles

Quick Probe reports conservative filesystem notes for local, mounted, UNC/network, or unknown paths. Default metadata worker settings remain conservative; future PBM catalog workers can use these notes to choose smaller queues and worker counts for network or mounted storage.

## Phase 27I Adaptive And Lazy Indexing

Phase 27I adds `pyforestscan_qgis/core/adaptive_lidar_indexing.py` as the strategy layer above the catalog worker. It detects repository capabilities with a bounded top-level probe, chooses a `RepositoryIndexPlan`, and supports registration of existing CSV/GeoJSON footprint indexes and native EPT/COPC logical sources into the same SQLite/RTree catalog.

The full catalog remains the fallback. It is now described as a two-pass path: spatial fields first so polygon queries can work, richer metadata enrichment later. Filename/grid and partitioned-lazy profiles are modeled but require explicit profile approval or supplied partition metadata before use.

## EPT Pruning And Repair

Catalog traversal prunes EPT internals when `ept.json` is present. The catalog stores one logical EPT source and does not descend into `ept-data` or `ept-hierarchy`.

`pyforestscan_qgis/core/ept_repository.py` detects node-level EPT catalogs and repairs them by backing up the SQLite file, deleting internal-node records, inserting one logical EPT record, and rebuilding RTree state without walking the EPT node tree.

Mounted and network-like paths default to user-local catalog storage under PyForestScan application data. Repository-side catalogs remain readable for compatibility, and the Batch page can copy them to the local catalog store with **Move Catalog Local** without deleting the source catalog.


## Phase 27K Workload Estimates

Catalog point counts from EPT or COPC root metadata are not treated as polygon-subset estimates. Unless a measured or otherwise defensible subset estimate exists, preflight reports estimated points as unavailable and records the reason. Independent local tile point-count sums may still be shown with High confidence when catalog assumptions are valid.

## Phase 27O Notes

Repository discovery, catalog identity, catalog integrity, repair, source-view, coverage-model, diagnostic-export, and repository action-state services now back Polygon Area Processing setup. Broken catalogs are reported as catalog repair/readiness issues instead of generic no-coverage results. The RTree contract is `id, xmin, xmax, ymin, ymax`; EPSG:6635 overlap fixtures cover the observed polygon envelope regression.

## Phase 27Q Notes

Polygon Area Processing can now compare the catalog path with Direct Header Scan for ordinary local LAS/LAZ/COPC repositories. Catalogs remain the performance path, but Direct Header Scan is the correctness fallback when catalog selection is missing or inconclusive. EPT keeps native logical-source handling. See [Polygon LiDAR Selection Contract](POLYGON_LIDAR_SELECTION_CONTRACT.md) for the developer contract and [Process LiDAR Folder by Polygon](../user-guide/polygon-folder-processing.md) for user-facing guidance.

## Phase 27R Notes

Phase 27R adds the stabilized ordinary-folder contract: direct header metadata is the beta correctness reference, catalogs are optional optimization, selected real paths are serialized and invariant-checked before PBM clipping, and EPT remains a separate logical-source path. See [Polygon LiDAR Stabilization](POLYGON_LIDAR_STABILIZATION.md).
