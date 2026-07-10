# Process LiDAR Folder by Polygon

Phase 27E expands the Dataset page polygon-folder workflow so users can choose a polygon from QGIS or disk instead of typing WKT by hand.

## Guided Inputs

- LiDAR folder containing LAS, LAZ, COPC, COPC LAZ, or local `ept.json` sources.
- Polygon source:
  - selected features from a loaded QGIS polygon layer;
  - an entire loaded QGIS polygon layer;
  - a vector file from disk;
  - Advanced WKT fallback.
- Output folder.
- Products.
- Analyze / Preflight.

WKT remains available under **Advanced WKT** for troubleshooting and reproducible tests, but it is no longer required for the guided path.

## Using A QGIS Polygon Layer

1. Add a polygon or multipolygon layer to QGIS.
2. Open Mission Control > Dataset > Process Folder by Polygon.
3. Set Polygon source to **Use QGIS Layer**.
4. Choose the polygon layer from the dropdown.
5. Choose **Use Selected Features** or **Use Entire Layer**.
6. Leave **Dissolve multiple features** enabled unless you need to preserve separate processing features later.

The layer dropdown lists polygon and multipolygon vector layers only. Point and line layers are hidden. If the selected layer was removed or the selected feature count changed, click **Refresh Layers**.

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

Preflight also compares intersecting LiDAR source CRS metadata when available and warns about mismatches before any heavy processing is attempted.

## What Preflight Does

- Recursively discovers `.las`, `.laz`, `.copc`, `.copc.laz`, and local `ept.json` sources.
- Refuses arbitrary JSON as EPT.
- Reads local `ept.json` metadata for bounds, CRS, and point count when present.
- Normalizes the chosen polygon source into one Polygon/MultiPolygon geometry.
- Attempts safe QGIS geometry repair when available.
- Derives polygon bounds automatically.
- Intersects known source bounds with the polygon envelope.
- Derives broad EPT bounds from the polygon envelope.
- Produces warnings for empty/invalid polygon geometry, unknown source bounds, CRS mismatches, large source selections, and large point estimates.

## Execution Status

The current workflow is a guarded preflight/planning path. Full clipped product execution must be routed through PBM/chunked processing before it is enabled for normal users. The plugin does not read an entire folder indiscriminately.
