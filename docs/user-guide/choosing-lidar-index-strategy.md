# Choosing A LiDAR Index Strategy

Polygon Area Processing can now preview the best indexing strategy before you build a catalog.

## Recommended Workflow

1. Open **Mission Control > Batch**.
2. Choose **Polygon Area Processing**.
3. Choose or paste the LiDAR repository path.
4. Click **Detect Best Indexing Strategy**.
5. Review the strategy, cost, warnings, and sources or indexes that would be registered.
6. Use **Build Relevant Index** when the plan can register an existing index or native EPT/COPC source.
7. Use **Build Complete Repository Index** when no trustworthy shortcut exists.

Detection is a bounded top-level probe. It should not crawl a large repository or read every header.

## Strategy Meanings

- **Automatic**: lets Mission Control choose the safest detected strategy.
- **Existing Spatial Index**: uses an existing PyForestScan catalog, PDAL tile index, or vector footprint index.
- **EPT/COPC Native**: registers EPT roots or COPC files as logical sources.
- **Filename/Grid Profile**: uses an approved naming convention to derive tile bounds.
- **Partitioned Lazy**: indexes only relevant mapped partitions first.
- **Full Header Catalog**: uses the durable catalog builder and reads headers/metadata for supported sources.

## What To Choose

Use **Automatic** unless you already know the repository has a maintained footprint index or a documented grid naming convention.

Use **Existing Spatial Index** when your data provider ships a tile index or when you already built a PyForestScan catalog.

Use **EPT/COPC Native** for repositories that are mostly local EPT roots or COPC files.

Use **Full Header Catalog** when Mission Control cannot detect a trustworthy shortcut.

## Safety Notes

Filename/grid profiles must be approved and include a CRS. Do not use filename-derived bounds for scientific work until representative samples have been validated.

GeoPackage, Shapefile, and FlatGeobuf footprint indexes are recognized, but they need QGIS/OGR field mapping before import. CSV and GeoJSON footprint indexes can be imported by the QGIS-free core when they expose the expected fields.

## Guided Labels

Mission Control uses plain setup labels in Guided mode:

- **Automatic Setup (Recommended)**
- **Use an Existing Footprint Index**
- **Use Built-in Spatial Access** for EPT or COPC
- **Use Tile Names**
- **Use Folder Regions**
- **Scan File Headers**

Technical strategy names are kept for logs and Advanced diagnostics.


## Guided Help

Use the blue information badges beside repository setup controls for concise explanations. Automatic Setup remains recommended. Technical strategy names are reserved for Advanced diagnostics and logs.
