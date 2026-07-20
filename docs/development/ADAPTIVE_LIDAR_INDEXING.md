# Adaptive LiDAR Indexing

Phase 27I adds an adaptive planning layer for large LiDAR repositories. The goal is to avoid a full per-file header catalog when the repository already exposes trustworthy spatial organization.

## Strategies

Mission Control models six strategies:

- `automatic`: choose the safest low-cost strategy from bounded capability detection.
- `existing_spatial_index`: use an existing PyForestScan catalog, PDAL tile index, or vector footprint index.
- `native_hierarchical_source`: register EPT roots and COPC sources as logical spatial sources without crawling EPT nodes or COPC chunks.
- `filename_grid`: derive tile bounds from an explicitly approved filename/grid profile.
- `partitioned_lazy`: index only polygon-relevant partitions first, then fill in more partitions later.
- `full_header_catalog`: fall back to the existing durable spatial-first catalog worker.

## Models

The core layer is QGIS-free in `pyforestscan_qgis/core/adaptive_lidar_indexing.py`:

- `LidarIndexStrategy`
- `RepositoryCapabilities`
- `RepositoryIndexPlan`
- `FilenameGridProfile`
- `LidarPartition`
- `ExistingIndexFieldMapping`
- `TwoPassCatalogPlan`
- `CatalogPerformanceReport`

The planner returns expected accuracy, expected build cost, sources or indexes to register, partitions to index, files avoided, and warnings.

## Capability Detection

`detect_repository_capabilities()` is intentionally bounded. It uses path selection and a top-level sample only. It does not recurse through the repository, inspect every header, count every file, or build a catalog.

Detected capabilities include:

- existing plugin catalog under `.pyforestscan/lidar_catalog.sqlite`
- top-level footprint or tile-index files (`.geojson`, `.json`, `.csv`, `.gpkg`, `.shp`, `.fgb`)
- PDAL tile-index naming such as `tile_index` or `tindex`
- top-level `ept.json` sources and directories containing `ept.json`
- top-level COPC sources
- optional filename/grid and partition profiles supplied by the caller

## Existing Indexes

QGIS-free registration currently supports CSV and GeoJSON/JSON footprint indexes with field mapping for source path, bounds, CRS, point count, and source type. GeoPackage, Shapefile, and FlatGeobuf are recognized as valid index formats but require QGIS/OGR field mapping in the UI layer before import.

Existing PyForestScan SQLite catalogs are used directly. Existing footprint indexes are imported into the plugin SQLite/RTree catalog so Polygon Area Processing can keep using the same query path.

## Native EPT And COPC

EPT is registered from the root `ept.json` only. The planner does not crawl `ept-data` nodes. COPC is treated as one logical source; COPC internals are not crawled during strategy detection.

## Filename/Grid Profiles

Filename/grid inference is disabled unless a profile is explicitly approved and declares a CRS. The profile must define a regex, coordinate groups, tile width and height, and coordinate interpretation. Sample validation against representative headers remains required before using a profile for production cataloging.

## Partitioned Lazy Indexing

`LidarPartition` describes a known spatial partition with bounds, CRS, estimated source count, status, and optional child catalog path. When polygon bounds are available, the planner selects only intersecting partitions and reports how many partitions were avoided.

## Full Catalog Fallback

When no trustworthy index is detected, the planner chooses the existing durable full catalog worker. The fallback is still spatial-first: polygon queries become possible after source bounds are indexed, while richer metadata enrichment can be deferred.

## Worker Audit

Phase 27I records a persistent-worker audit helper. Current catalog jobs use a durable job runner rather than intentionally launching one subprocess per source. A future PBM-backed fast-header worker can use the same strategy plan to tune worker counts and report measured bottlenecks.
