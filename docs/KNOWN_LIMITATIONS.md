# Known Limitations

This document records current limitations for the internal release candidate. It is user-facing and should stay honest: limitations are not failures, but they must be visible before scientific interpretation or wider deployment.

## Scientific Processing

- Product generation uses either PBM backend Python for routed products or QGIS Python for remaining QGIS-Python-only tools. Missing QGIS Python PyForestScan/PDAL packages are optional fallback warnings and do not block PBM-routed products when PBM is `Ready`.
- CHM, Canopy Cover, PAD, PAI, FHD, and Rumple summary are implemented for single datasets, but outputs still require visual QA in QGIS before interpretation.
- PAD is an authoritative multi-band height-bin volume. Mission Control displays a representative grayscale height slice by default; single-band PAD derivatives and RGB composites are visualizations, not replacements for the full PAD volume.
- Rumple currently writes a CSV summary rather than a raster layer.
- Polygon Area Processing now lives in Batch and uses a persistent SQLite/RTree LiDAR catalog for fast polygon source selection. Catalog building reads headers/metadata only and records failures explicitly. Local LAS/LAZ/COPC CRS extraction remains limited until PBM/PDAL metadata inspection is wired into the catalog worker. Raster masking outside the exact polygon is best-effort when rasterio/shapely are available; PBM catalog jobs have a backend-runner entrypoint, while richer backend-Python progress streaming and real 2.6-million-file benchmarks still need clean-machine validation. Mosaicking, folder monitoring, and project files remain deferred.

## Batch Processing

- Sequential mode is the safest default.
- Parallel Safe mode runs inside QGIS with bounded workers and guardrails; users should start with two workers.
- Cancellation and pause are checked between files, not during a native PyForestScan/PDAL product calculation.
- Batch output loading into QGIS is off by default to avoid overwhelming a project with many layers.
- External Worker mode is disabled because QGIS GUI Python launched application windows during validation. It remains disabled until a true headless launcher is proven.

## User Experience

- Mission Control manages internal JSON/CSV/HTML files automatically, but raw files remain visible under technical details for reproducibility.
- The Dataset footprint preview is a rectangular extent from inspected bounds, not an exact point-cloud coverage polygon.
- The Scientific Advisor uses deterministic, documented rules and configurable thresholds. It is guidance, not a substitute for scientific review.

## Release Scope

`v0.1.0-beta.2` is intended for controlled QGIS testing, workflow validation, and scientific QA. It is not a public QGIS Plugin Repository release candidate. Formal RC1 readiness is gated by the [Release Roadmap](releases/RELEASE_ROADMAP.md), [RC1 Checklist](releases/RC1_CHECKLIST.md), [RC1 Manual QA Script](releases/RC1_MANUAL_QA_SCRIPT.md), and [Release Triage Policy](releases/RELEASE_TRIAGE_POLICY.md). Versioned ZIP artifacts are traceable through `dist/release_manifest.json`.


## PyForestScan Backend Manager

The PyForestScan Backend Manager can run backend installation for Windows internal beta builds only. Linux and macOS installer execution remain planned/experimental until clean platform smoke testing is complete. PBM installs only into the user-local PyForestScan backend folder and must not install into QGIS Python, modify QGIS folders, require administrator privileges, change user environment variables, or enable External Worker mode.

PBM verification can report the managed backend as `Ready`, and Environment Check reports overall `READY` for PBM-routed execution while listing QGIS Python scientific packages as optional fallback status. Phase 23D/23E routes Dataset Explorer local point-cloud inspection, CHM, Canopy Cover, PAD, PAI, FHD, Rumple, DTM, Point Density, and Voxel Statistic through PBM when ready. Phase 23F isolates PBM subprocesses from QGIS profile Python paths and installs PyPI-only backend packages through managed backend Python. Phase 23G verifies staged backend paths before promotion and strict final paths after config write. Phase 23H adds exact dependency diagnostics for staged verification failures; Phase 23I adds backend-local conda DLL/executable discovery for Windows; Phase 23J adds tighter Windows beta GDAL/rasterio/numpy ranges, `pip install --no-deps` for PyPI-only packages, and conda package-build diagnostics for rasterio DLL compatibility; Phase 23K adds explicit conda-forge PyForestScan runtime dependencies before PyForestScan smoke verification; Phase 23L adds tqdm and backend-local GDAL/PROJ data env wiring. If Windows/Python 3.12 package availability still blocks `python-pdal`, `pdal.exe`, `gdalinfo.exe`, `osgeo.gdal`, or `rasterio`, the diagnostic output is the source of truth for the next manifest pinning decision. Height Above Ground point-cloud export and Preprocess Point Cloud still execute inside QGIS Python until their runner payloads are validated separately. QGIS 3.x is the supported target; QGIS 4.x compatibility is prepared defensively but must be tested when available.

## Adaptive LiDAR Indexing

Adaptive LiDAR indexing can detect and plan lower-cost strategies, but not every shortcut is fully automated. CSV and GeoJSON footprint indexes can be imported by the QGIS-free core. GeoPackage, Shapefile, and FlatGeobuf index import requires QGIS/OGR field mapping. Filename/grid and partition profiles require explicit approval and representative validation before scientific use. Real-world 2.6-million-file benchmarks remain pending.

## Phase 27J Remaining EPT Limits

EPT node cataloging is blocked and repair is available for older incorrect catalogs. Clean-machine testing is still needed against the reported 2.6-million-node repository to measure real RTree lookup, row loading, and workload-estimation timings. CRS transformation quality still depends on QGIS/OGR transformation availability in the UI layer.


## Phase 27K Remaining Validation

The polygon transport fix is covered by QGIS-free regression tests and synthetic backend materialization tests. The real Windows/QGIS network EPT workflow must still be run manually with the checklist in [Real EPT Polygon Validation](testing/REAL_EPT_POLYGON_VALIDATION.md) before claiming that specific dataset passed.

## Phase 27L limitations

`Test Spatial Read` is documented as a troubleshooting-only behavior and is not automatically run during preflight. Real Windows/QGIS EPT production success must not be claimed unless the specific dataset was actually run. Diagnostics are standard for failures, while sanitized export controls remain basic.

## Phase 27M Remaining Limitations

- Live QGIS automatic loading and real EPT polygon mask validation require a QGIS/PBM test machine and are not proven by the headless unit suite.
- QGIS/GDAL mask integration is exposed through a normalized Processing parameter wrapper; backend rasterio masking remains the default finalization path for PBM-generated rasters.
- Retry Mask and Retry Load are represented in the execution contract, but full independent UI retry buttons remain a future refinement.

## Phase 27N Remaining Limitations

Live QGIS spatial diagnostic layers are represented by UI actions and structured details, but full temporary map-layer rendering still needs live QGIS validation. Saved-workspace stale-plan blocking is recorded by plan signature but remains a follow-up for deeper workspace integration.

## Phase 27O Notes

Repository discovery, catalog identity, catalog integrity, repair, source-view, coverage-model, diagnostic-export, and repository action-state services now back Polygon Area Processing setup. Broken catalogs are reported as catalog repair/readiness issues instead of generic no-coverage results. The RTree contract is `id, xmin, xmax, ymin, ymax`; EPSG:6635 overlap fixtures cover the observed polygon envelope regression.

## Phase 27P Notes

Catalog health now separates embedded CRS from effective CRS. A bounded LAS/LAZ catalog with all source CRS values missing is `CRS Assignment Required`, not healthy, and polygon preflight does not report true no coverage until comparable CRS metadata exists. Repository CRS override metadata is explicit and reversible. Live QGIS coverage/zoom services now require actual layer insertion or canvas extent changes before reporting success.

## Phase 27Q Notes

Polygon Area Processing can now compare the catalog path with Direct Header Scan for ordinary local LAS/LAZ/COPC repositories. Catalogs remain the performance path, but Direct Header Scan is the correctness fallback when catalog selection is missing or inconclusive. EPT keeps native logical-source handling. See [Polygon LiDAR Selection Contract](development/POLYGON_LIDAR_SELECTION_CONTRACT.md) for the developer contract and [Process LiDAR Folder by Polygon](user-guide/polygon-folder-processing.md) for user-facing guidance.

## Phase 27R Notes

Phase 27R documents that ordinary folder processing now treats direct header metadata as the beta correctness reference and catalogs as optional optimization. Live QGIS validation is still required for the user's real repositories. See [Polygon LiDAR Stabilization](development/POLYGON_LIDAR_STABILIZATION.md) and [Real Ordinary LiDAR Polygon Validation](testing/REAL_ORDINARY_LIDAR_POLYGON_VALIDATION.md).

## Phase 27S EPT CRS Notes

EPT CRS detection now handles WKT/WKT2, PROJJSON, and authority plus horizontal code. Live end-to-end QGIS validation against the real 130 ha EPT polygon remains a manual QA item; automated tests cover the reported EPSG:6635 extent overlap and CRS failure messaging without user-specific paths.

- Processing Toolbox provider-tree expansion varies across QGIS versions. Mission Control opens/focuses the toolbox and provides a searchable fallback page, but may not expand the PyForestScan tree automatically.
- Phase 28B interactive validation remains pending until the matrix in `docs/testing/PHASE_28B_LIVE_QGIS_VALIDATION.md` is completed in QGIS 3.44.9.

- Phase 28C passed QGIS 3.44.9 offscreen construction at 620/980/1400 pixel widths and 100%/150% scale factors. Interactive light/dark theme, keyboard, map-action, and end-to-end workflow validation remains pending and is not claimed as passed.
