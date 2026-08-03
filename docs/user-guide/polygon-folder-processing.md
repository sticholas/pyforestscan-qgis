# Process LiDAR Folder by Polygon

Phase 27F moves polygon-driven LiDAR folder processing into **Mission Control > Batch**. The Dataset page is again focused on one dataset at a time, while Batch owns workflows that discover multiple LiDAR sources and clip them by an area of interest.

## Guided Inputs

- LiDAR repository/catalog containing LAS, LAZ, COPC, COPC LAZ, or local `ept.json` sources.
- Polygon source:
  - selected features from a loaded QGIS polygon layer;
  - an entire loaded QGIS polygon layer;
  - a vector file from disk;
  - Advanced WKT fallback.
- Output folder.
- Products.
- Preflight.
- Run Polygon Batch.

WKT remains available under **Advanced WKT** for troubleshooting and reproducible tests, but it is no longer required for the guided path.

## Batch Modes

Mission Control > Batch has two modes:

- **Standard File Batch**: the default folder-to-products workflow. Users select individual discovered files and run the same product plan across them.
- **Polygon Area Processing**: the polygon-driven workflow. Users choose a LiDAR repository, build or update its catalog, choose a polygon source, output folder, and products. Preflight queries the catalog for intersecting sources, stages clipped inputs, then runs the normal Batch executor against those clipped inputs.

Batch is optional and is not part of the default single-dataset Continue path.

## Using A QGIS Polygon Layer

1. Add a polygon or multipolygon layer to QGIS.
2. Open Mission Control > Batch.
3. Set Batch Mode to **Polygon Area Processing**.
4. Choose the LiDAR Repository and output folder. Build or update the catalog only when Mission Control shows **No Catalog**, **Interrupted**, or **Out of Date** and you explicitly choose a catalog action.
5. Set Polygon source to **Use QGIS Layer**.
6. Choose the polygon layer from the dropdown.
7. Choose **Use Selected Features** or **Use Entire Layer**.
8. Leave **Dissolve multiple features** enabled unless you need to preserve separate processing features later.

The layer dropdown lists polygon and multipolygon vector layers only. Point and line layers are hidden. If the selected layer was removed or the selected feature count changed, click **Refresh Polygon Layers**.

## Using Selected Features

When one or more polygon features are selected in QGIS, Mission Control defaults to **Use Selected Features**. Multiple selected features are dissolved into one processing geometry for the current preflight plan. Holes are preserved by QGIS geometry handling.

If no features are selected, Mission Control shows concise guidance and offers **Use Entire Layer** instead.

## Using A Vector File

Choose **Choose Vector File** and browse to polygon vector data. Supported guided formats include:

- GeoPackage (`.gpkg`)
- ESRI Shapefile (`.shp`)
- GeoJSON (`.geojson`, valid vector `.json`)
- FlatGeobuf (`.fgb`)
- KML (`.kml`, where QGIS/OGR can read valid polygon geometry)

Mission Control uses QGIS/OGR provider capabilities rather than a custom parser. Arbitrary JSON is not treated as valid polygon input.

For GeoPackage or other multi-layer containers, Mission Control inspects available vector sublayers and shows a layer selector when multiple polygon layers are available. Non-polygon sublayers are rejected rather than silently selected.

Guided default: all polygon features in the selected file layer are dissolved into one processing geometry.

## CRS Handling

For QGIS layers and vector files, Mission Control reads the layer CRS. An optional processing CRS override is available under Advanced WKT/CRS controls. When a valid override differs from the source CRS, QGIS transforms the polygon before preflight and reports that transformation.

Preflight also compares intersecting LiDAR source CRS metadata when available and warns about mismatches before any heavy processing is attempted. Sources with known CRS differences are passed through the same guarded normalization path used by existing Height Above Ground processing.

## What Preflight Does

- Requires an existing LiDAR catalog; normal preflight does not recursively scan the repository.
- Refuses arbitrary JSON as EPT.
- Queries the SQLite/RTree catalog with the polygon envelope when using the catalog path.
- In Automatic mode, cross-checks ordinary LAS/LAZ/COPC folders with Direct Header Scan and can use real overlapping files if the catalog is missing or inconclusive.
- Reports catalog query time, candidate count, metadata-error count, estimated points, and estimated bytes.
- Normalizes the chosen polygon source into one Polygon/MultiPolygon geometry.
- Attempts safe QGIS geometry repair when available.
- Derives polygon bounds automatically.
- Intersects known source bounds with the polygon envelope.
- Derives broad EPT bounds from the polygon envelope.
- Produces warnings for empty/invalid polygon geometry, unknown source bounds, CRS mismatches, large source selections, and large point estimates.

## Execution Strategy

After a successful preflight, **Run Polygon Batch** stages clipped source files under the batch output folder and then runs the standard Batch executor on those staged files. That keeps checkpointing, summaries, retry behavior, and Results integration aligned with normal Batch processing.

The current implementation clips point inputs before product generation. Exact raster masking outside the polygon is still a remaining limitation: products are generated from clipped points, but interpolated raster cells near the polygon envelope may still need visual QA before scientific interpretation.

Local LAS/LAZ/COPC source bounds are read during catalog building when the public header can be inspected. Metadata failures are recorded in the catalog and shown as warnings. Local EPT sources with readable metadata can be selected during preflight. See [LiDAR Catalogs](lidar-catalog.md).


## Catalog Maintenance

Use **Detect Best Indexing Strategy** first. Then use **Build Relevant Index** when supported, or **Build Complete Repository Index** the first time a full repository catalog is needed. Use **Update Catalog** after files are added, modified, moved, or deleted. Normal polygon preflight uses the catalog and does not trigger a complete rebuild.

## Adaptive Repository Indexing

Polygon Area Processing now separates repository strategy detection from heavy catalog work. **Detect Best Indexing Strategy** is safe to run first because it uses a bounded top-level probe only. It can identify existing PyForestScan catalogs, PDAL tile indexes, CSV/GeoJSON footprint indexes, EPT roots, COPC sources, and configured repository profiles.

The default path remains safe: if no trustworthy shortcut is found, use **Build Complete Repository Index**. Batch preflight uses a usable catalog when available. For ordinary local LAS/LAZ/COPC folders, Automatic mode can fall back to Direct Header Scan when a catalog is missing or returns no intersecting files even though real headers overlap the polygon.

## EPT Datasets

You can choose `ept.json`, the EPT root folder, or the `ept-data` folder. Mission Control automatically uses the parent EPT dataset and treats it as one logical input. Internal EPT node files are not listed, cataloged, or staged as separate Batch files.

Preflight now checks the managed PBM backend before Run. If the backend cannot import PyForestScan, preflight is **Ready: NO** and tells you to repair or rebuild the backend from Environment.


## Polygon Input Contract

When you run Polygon Area Processing, Mission Control stores the selected geometry and CRS in the job manifest. The managed backend creates a real clipping polygon file inside the job folder before processing. This prevents WKT text from being mistaken for a filename and keeps the job independent of the original QGIS layer after submission.

## Request validation

Before polygon EPT products run, PBM validates the EPT metadata, polygon file, CRS, output folder, API contract, and canonical bounds expression. This should catch malformed range requests before a CHM or other product starts reading points.


## Exact Raster Masking

Under Advanced Batch Options > Polygon Finalization, Exact raster mask is enabled by default. Automatic uses the managed backend mask path for PBM-produced rasters and can use QGIS/GDAL Clip Raster by Mask Layer when selected inside QGIS.

Load generated outputs into QGIS waits for final masking and output registration. Temporary unmasked intermediates are not loaded as successful polygon outputs.

## Guided Polygon Workflow

Use the Batch page in order: choose LiDAR data, choose area, choose outputs, choose output and quality settings, review the plan, then run. EPT repositories stay identified as EPT regardless of polygon shape; outside polygons show a coverage diagnosis rather than a generic catalog message.

## Phase 27O Notes

Repository discovery, catalog identity, catalog integrity, repair, source-view, coverage-model, diagnostic-export, and repository action-state services now back Polygon Area Processing setup. Broken catalogs are reported as catalog repair/readiness issues instead of generic no-coverage results. The RTree contract is `id, xmin, xmax, ymin, ymax`; EPSG:6635 overlap fixtures cover the observed polygon envelope regression.

## Phase 27P Notes

Catalog health now separates embedded CRS from effective CRS. A bounded LAS/LAZ catalog with all source CRS values missing is `CRS Assignment Required`, not healthy, and polygon preflight does not report true no coverage until comparable CRS metadata exists. Repository CRS override metadata is explicit and reversible. Live QGIS coverage/zoom services now require actual layer insertion or canvas extent changes before reporting success.

## Phase 27Q Notes

The Batch page now exposes selection mode controls for Polygon Area Processing: Automatic, Catalog Index, and Direct Header Scan. Automatic is recommended. Direct Header Scan is slower on large repositories, but it reads real file headers and restores the folder-selection behavior used before the indexed catalog became the default. It still requires a known effective CRS before comparing source and polygon bounds.

## Phase 27R Notes

Phase 27R makes ordinary LAS/LAZ/COPC folder processing use direct header metadata when a verified catalog is unavailable or inconsistent. Catalog tools remain available under Repository Tools, but catalog absence should not block a normal folder run after an explicit CRS assignment. See [Polygon LiDAR Stabilization](../development/POLYGON_LIDAR_STABILIZATION.md).
