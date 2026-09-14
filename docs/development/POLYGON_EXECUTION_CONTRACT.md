# Polygon Execution Contract

Phase 27K separates polygon geometry content from polygon vector file paths.

## Responsibilities

QGIS / Mission Control:

- captures selected-feature, layer, vector-file, or Advanced WKT geometry
- records source CRS, processing CRS, feature count, area, envelope, and exact WKT
- writes a durable manifest with geometry fields that are clearly named as geometry
- requests a PBM job and monitors progress

PBM backend:

- reads the polygon execution input from the job spec
- validates Polygon and MultiPolygon WKT
- creates `<job_workspace>/inputs/clipping_polygon.gpkg` when GDAL/OGR GeoPackage support is available
- falls back to `<job_workspace>/inputs/clipping_polygon.geojson`
- passes only the generated vector dataset path to PyForestScan

## Manifest Fields

Geometry fields are content:

- `polygon.wkt`
- `polygon.exact_query_wkt`
- `polygon.polygon_original_crs`
- `polygon.clipping_geometry_crs`

Path fields are filesystem paths:

- `crop_polygon_path`
- `temporary_vector_path`

WKT must never be passed through a field named path, file, or filename.

## CRS Chain

The manifest records:

- polygon original CRS
- EPT source/catalog CRS
- bounds query CRS
- clipping geometry CRS
- processing CRS
- output CRS

EPT bounds are derived from the polygon query geometry, not from the full EPT root extent. If CRS transformation is unavailable, preflight records a warning and uses the already-normalized polygon coordinates rather than silently claiming a transform occurred.

## Progress Stages

Polygon logical jobs use named stages: Preparing Inputs, Validating Geometry, Preparing Spatial Read, Applying EPT Bounds, Reading Point Cloud, Normalizing Heights, Generating Product, Writing Raster, Masking Output, Writing Metadata, Finalizing, and Completed.

## Phase 27L EPT request validation

Polygon EPT jobs now use `EptBounds` as the typed bounds contract. The polygon envelope is stored in manifests as `ept_bounds` JSON and converted to PyForestScan list-ranges only by the adapter. PBM request validation runs before product generation and blocks incompatible API signatures, malformed bounds, non-overlapping EPT bounds, invalid polygon files, CRS gaps, and unwritable output folders.

## Phase 27M Finalization Contract

Polygon raster jobs are not complete until product generation, exact polygon masking, validation, and output registration finish. Temporary unmasked rasters may be retained for diagnostics, but they are not registered as primary user outputs. Default mask failure policy fails the product rather than presenting an unmasked envelope raster as successful.

## Phase 27S Alignment Invariants

Before Run, EPT polygon processing requires a valid repository CRS, valid polygon CRS, validated transformation state, finite EPT bounds, root-extent overlap, exact polygon geometry in the EPT/clipping CRS, one logical `ept.json` source, and a current plan signature. It must not silently fall back to untransformed coordinates.
## Work-unit contract
Every CHM unit records core/read extents, global grid, sources, signature, attempts, method, checksum, and status. Only a complete masked final mosaic enters the registry.
