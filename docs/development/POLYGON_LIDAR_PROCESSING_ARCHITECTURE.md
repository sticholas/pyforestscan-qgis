# Polygon LiDAR Processing Architecture

Phase 27F makes polygon-folder processing a Batch-owned workflow. Dataset remains a single-dataset page; Batch owns folder discovery, polygon preflight, clipped-source staging, checkpointing, resume, retry, summaries, and Results handoff.

## Modules

- `core/lidar_inventory.py`: folder request, source records, inventory cache signatures, supported source discovery.
- `core/spatial_selection.py`: QGIS-free polygon WKT validation and bounds derivation.
- `core/polygon_source.py`: QGIS-free polygon source and normalized-selection models.
- `core/polygon_normalization.py`: QGIS-free WKT fallback normalization helpers.
- `ui/polygon_source_selector.py`: QGIS layer, selected-feature, vector-file, GeoPackage/container, CRS, dissolve, repair, and WKT extraction helpers.
- `core/polygon_processing.py`: source intersection records, processing plan, preflight summary, workload warnings.
- `core/polygon_batch.py`: Batch-facing preflight request/report, polygon manifest writer, selected-source filtering, clipped-source staging, and standard Batch executor handoff.
- `ui/pages.py`: Batch mode selector, Polygon Area Processing controls, preflight/run UI, and polygon batch worker wiring.

## Responsibilities

QGIS UI handles polygon source discovery, geometry extraction, repair, dissolve, CRS transformation, and user-facing state recovery. The QGIS-free core receives a normalized WKT/CRS/bounds representation and remains testable without QGIS.

Batch owns execution. Polygon preflight discovers and filters candidate sources, then `execute_polygon_batch()` stages clipped source files and runs the normal `BatchExecutor` against those staged files. That keeps existing Batch checkpointing, summaries, retry semantics, and Results behavior instead of creating a separate folder-processing engine.

PBM continues to provide the routed execution backend used by the adapter and Batch executor. External Worker mode remains disabled.

## Source Modes

- `qgis_selected_features`: selected polygon features from a loaded QGIS layer. Empty selections are rejected with guidance.
- `qgis_full_layer`: all polygon features from a loaded QGIS layer, dissolved for preflight.
- `vector_file`: a QGIS/OGR-readable polygon vector file. GeoPackage and other containers expose polygon sublayers when available.
- `wkt`: Advanced fallback for direct POLYGON/MULTIPOLYGON text.

All modes normalize to `NormalizedPolygonSelection` before polygon batch preflight runs.

## Batch Mode Strategy

1. User selects **Polygon Area Processing** on the Batch page.
2. Batch collects LiDAR folder, polygon source, output folder, products, and shared settings.
3. Preflight inventories supported sources and selects only sources whose known bounds intersect the polygon envelope.
4. Preflight writes `polygon_batch_manifest.json` beside the normal Batch manifest and records polygon source metadata, selected sources, skipped sources, blockers, and warnings.
5. Execution creates a `polygon_clipped_sources` staging folder under the batch run folder.
6. Each selected source is clipped with the existing adapter normalization path using the normalized polygon WKT.
7. The standard Batch executor runs selected products against the clipped LAZ files.
8. Results receives the normal Batch summaries and output paths.

## Safe Strategy

- Inventory source footprints before reading point data.
- Normalize and validate one Polygon/MultiPolygon processing geometry.
- Skip non-intersecting sources.
- Skip unknown-bounds sources until metadata inventory can prove they intersect.
- Use broad bounds for EPT reads and exact polygon crop parameters during clipped-source staging.
- Block or warn on CRS mismatches instead of silently merging incompatible sources.
- Warn on large source/point selections and route work through existing Batch guardrails.
- Keep Parallel Safe secondary and bounded; external subprocess workers remain disabled.
- Do not concatenate arbitrary arrays without memory checks.

## CRS Behavior

The normalized polygon stores source CRS and processing CRS text. When QGIS can transform a layer/file polygon before preflight, the transformed WKT is passed to the QGIS-free core. During execution, sources whose metadata CRS differs from the polygon processing CRS are routed through the adapter normalization request with reprojection enabled. Sources without CRS metadata are allowed only with warnings and should be verified by the user before scientific interpretation.

## State Recovery

Mission Control exposes **Refresh Polygon Layers** to rescan current QGIS polygon layers, preserve the selected layer when it still exists, update selected-feature counts, and recover from stale layer references without crashing. Polygon Batch preflight can be rerun after changing the LiDAR folder, polygon source, output folder, or products.

## Current Limitations

Local LAS/LAZ/COPC footprint extraction requires PDAL/PBM metadata inspection. Current QGIS-free discovery records unknown bounds for local files and skips them until metadata inventory is available. Local EPT `ept.json` sources with readable bounds can participate in polygon preflight.

Raster products are generated from clipped point inputs, but exact polygon raster masking to NoData outside the polygon is not yet a dedicated post-processing step. Users should visually QA polygon-edge raster cells before scientific interpretation.

Folder mosaicking, catalog products, folder monitoring, per-polygon split outputs, and project files remain deferred.
