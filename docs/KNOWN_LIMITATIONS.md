# Known Limitations

## Phase 32H live gate

- Automated plan/attempt lifecycle tests and the packaged click-path harness are complete. The exact default-profile QGIS 3.44.13 flow must still confirm Detailed Check has zero blockers and reaches the first managed worker after active QGIS sessions are saved and closed.

## Phase 32G live verification

- Repository and packaged click-path harnesses verify dispatch through `DISPATCH_STARTED`. A clean default-profile QGIS 3.44.13 test must still confirm the packaged build reaches coordinator process creation against the real UNC source after all active QGIS sessions are closed.

## Large polygon runtime QA

- Generic polygon preparation now runs in a detached PBM coordinator and reports durable five-second heartbeats. The 104.8-million-point UNC PAI/FHD scenario still requires a real default-profile Windows QGIS launch test and bounded completed pilot; repository validation does not substitute for measured network, point-count, memory, and output evidence.
- Cancellation is cooperative. A cancellation request is recorded immediately, but an individual native geospatial operation may finish its current safe operation before stopping.

## Packaged Build And Setup Integrity

- Packaged builds detect missing or mixed critical plugin files through `build_info.json`. Development source copies without package metadata report plugin installation status as Unknown.
- QGIS must be restarted after manually replacing plugin files. PyForestScan blocks processing if files change beneath a running session; it does not attempt unsafe wholesale `sys.modules` mutation.
- Internal beta Setup records the downloaded Micromamba SHA-256, but the manifest still uses the official `latest` endpoint without a release-pinned digest. Pinning a tested artifact digest remains a public-release gate. This does not make an already installed and verified Processing Engine unready.
- Future CloudCompare, Potree, PyTorch, SAM, and WhiteboxTools placeholders are not required for current PyForestScan processing and are no longer displayed as normal Processing Engine requirements.

## Runtime changes after Prerun

- Repair / Reload intentionally invalidates an older Prerun token. Mission Control reruns validation when active selections are available; otherwise the user must run Prerun again.
- A real executable, plugin-build, runner, dependency, protocol, capability, or environment change blocks launch with a precise diagnostic. These objective failures may still require Repair / Reload.

## Processing Engine setup scope

- Startup intentionally performs no full managed-runtime verification. A stale, missing, or corrupt setup record is shown as Setup/Repair required until the user runs the explicit action.
- Repair / Reload reconciles the managed environment and current plugin contract; it does not attach to or terminate unrelated external processes.
- Automatic spatial metadata remains best effort. Ambiguous CRS or units require a contextual Process-page assignment before processing can start.

## Phase 32B runtime coverage

Packaged startup and lifecycle testing passed in QGIS 3.44.13 LTR. QGIS 3.44.9 is present on the test host but does not expose a usable Python-QGIS launcher, so the automated packaged-profile smoke could not be repeated there. No network-offline setup attempt was made; startup was verified to perform no network operation.

## Tools & Setup QA

Phase 32A runtime state and responsive geometry were validated offscreen with QGIS 3.44.13 LTR. That renderer did not paint stylesheet text into captured images, so final typography and color remain subject to live in-application release QA. This does not affect widget behavior, setup transactions, or processing.

## Phase 31K notes

- COPC is measurably faster for the tested 11.4M-point bounded window, but automatic conversion is not enabled because the dimension-preserving conversion was not yet validated. Native COPC inputs remain supported.
- The new bounded local read removes the full-cloud-per-area defect. A complete optimized eight-area Windows/QGIS rerun is still required to establish end-to-end timing and memory behavior.
- Processing History currently provides the durable local registry foundation; richer Mission Control history and Re-run controls are deferred.
- A persistent processing service is an ADR-level future option. Current production execution remains one hidden durable coordinator per job.

- Phase 31J uses exact support-extent signatures for preparation reuse. A later smaller polygon inside a prior prepared extent is conservatively rebuilt unless its support extent matches exactly.
- The Olaa `_Norm` source is eligible for normalized-Z inspection from its observed range, but its live bounded statistical validation remains pending because the UNC source was unavailable during the final automated run.
- A bounded preparation artifact avoids full-source local duplication, but ordinary LAS/LAZ readers may still scan the network source because those formats lack COPC-style spatial seeking.

- Phase 31I validates Polygon coordinator launch and automatic canary policy, but the full 104.8-million-point Olaa CHM/Rumple run remains live manual QA.
- Alternative-source recommendation uses catalog point count, XY bounds, byte size, filename relationship, and Z ranges. Repositories lacking enough evidence remain ambiguous rather than silently double processed.
- Standard Folder processing is PBM-routed, but its runtime token is not yet serialized through the same durable preflight manifest contract used by Polygon processing.

## Phase 31H live gates

Authoritative state/token behavior, stale-handler detection, 100-transition soak, product API smoke, and production-route guards are automated. Clean Windows downloads, two simultaneous live QGIS instances, no-console observation, corrupted-package repair, and a fresh Polygon CHM/Rumple completion still require manual release evidence.

## Phase 31G live validation

Runtime identity, contract drift, no-QGIS-fallback behavior, and product mappings are automated. A fresh clean-Windows setup, multiple-QGIS-instance behavior, no-console observation, and the real two-LAS Polygon CHM plus rumple run still require live QGIS release-gate evidence. These are not claimed as passed by the QGIS-free suite.

## Processing Engine validation

- Phase 31F prevents a missing `pyforestscan.handlers` module from becoming a scientific batch failure and classifies partial installs as repair-required before launch.
- Clean Windows first-install, broken-install repair, and the reported two-source CHM/Rumple Polygon run still require live QGIS evidence before release sign-off.
- The managed setup action continues to use the existing transactional PBM installer; Linux and macOS installation support retains its existing experimental status.

- Polygon processing cannot use the folder-only source-local CRS fallback. A real embedded, sidecar, file, repository, consensus, or exact QGIS datasource CRS is required.
- Legacy catalogs may contain historical repository override metadata. New assignments use the shared spatial assignment store and are applied at query time.
- Automatic polygon-coordinate fallback is an assumed interpretation, not authoritative CRS discovery. It is intentionally unavailable when raw coordinate spaces are incompatible or spatial evidence conflicts.

- Durable automatic artifact routing is initially enabled for standalone CHM/Rumple; other HAG consumers retain existing execution paths.
- Source-local ground/HAG preparation requires trusted linear units; magnitude and LAS scale are insufficient evidence.
- Large preparation is isolated in PBM, but adaptive tiled Delaunay HAG is deferred until buffered-boundary equivalence is validated.
- The 104,819,538-point production LAS was unavailable for Phase 31A live execution; its classification fraction and outputs remain unclaimed.

- Source-local CHM and Rumple require an existing normalized-height dimension. Source-local polygon processing remains blocked because spatial alignment cannot be proven without a CRS.
- The real scientific subprocess regression is skipped on development hosts without the managed geospatial dependency stack; clean Windows/QGIS evidence must record the managed-backend run separately.

The spatial Rumple raster is mathematically regression-tested against upstream scalar behavior and synthetic tiling, and adaptive work-unit execution now shares durable CHM support with verified plan/grid/checksum mosaicking. A fresh real LAS/EPT adaptive run, visual seam inspection, runtime/memory benchmarking, and interactive QGIS loading remain release checks. QGIS 3.44.9's local runtime launcher was unavailable; 3.44.13 failed before plugin import due to a local Qt DLL error. Rumple is scale-sensitive: CHM resolution, interpolation, and minimum-height settings must match for comparison.

Phase 30C automated coverage validates immutable single-file/folder requests and 100 semantic UI transitions. Live expandable geometry and consecutive QGIS jobs still require a working QGIS Qt runtime.

Phase 29E automated hardening is complete, but clean Windows/QGIS install, cancel/crash process-tree, upgrade-from-older-beta, and real-LiDAR scientific validation remain explicitly untested live. Historical job folders are retained; the maintenance API reports stale temporary/cache candidates but has no normal-user UI.

EPT CHM is temporarily limited to one active worker. Live Windows confirmation of native DLL isolation, QGIS close/reopen recovery, and safe-mode pilot processing remains required; alternate HAG behavior is not enabled without measured evidence.

Phase 29D corrects adaptive point-memory budgeting and measures synthetic planning/read amplification. It does not claim faster real LiDAR execution: representative EPT/LAS timing, peak RSS, live pilot replanning, and numeric CHM equivalence remain pending. The permanent planning benchmark is `scripts/benchmark_adaptive_processing.py`.

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

- Large-product tiling is not enabled until product-specific scientific equivalence is validated; automatic mode monitors liveness but cannot provide exact progress for quiet third-party calls.
- Source-aware partitioning is enabled only for CHM. Live numerical equivalence, network performance, and interactive pause/cancel validation remain pending.

## Phase 28F live validation

Real formerly collinear EPT, medium job, QGIS restart, equivalence, and full 120-unit tests remain pending. Scalable tiling remains CHM-only.


## Phase 28G Exact Polygon Completion

Phase 28G exact filtering and recovery are covered by QGIS-free regression tests, but the reported 120-area job still requires the documented live QGIS completion sequence before release promotion.


## Phase 28H Adaptive Scale and Compact Workspace

Phase 28H adaptive scale and current-job isolation are covered by QGIS-free tests. Live PBM pilot calibration, real small/medium/very-large timings, two-coordinator stale-output behavior, and 420-800 px visual checks remain pending.
# Phase 30B Validation Boundary

Adaptive Rumple coordinator integration is synthetically validated, but medium and large real-source equivalence and consecutive-job QGIS interaction remain to be recorded live. The original closed 130 ha error dialog could not be recovered; durable records show the science and batch completed successfully.
# Phase 30D notes

- Standalone unknown-CRS processing preserves source coordinates and does not assign a guessed CRS. Polygon alignment and reprojection still require a resolved CRS.
- Automatic source concurrency is bounded at five by default; EPT internal work-unit scheduling is governed separately.
- Recovery only reads an explicitly selected batch folder. Complete metadata/signature compatibility enforcement remains planned.
# Phase 30E notes

- Source-local outputs intentionally have no named CRS and cannot be overlaid safely until a CRS is assigned.
- Repository consensus is bounded and conservative; any sampled known-CRS conflict prevents inheritance.
- Automatic file-header discovery continues through Dataset Explorer/PDAL. The resolver's standalone API accepts discovered embedded metadata rather than duplicating every native reader.
- Live QGIS/PBM validation of the original unknown-CRS LAS remains outstanding.
- The 104,819,538-point Olaa production LAS was not available in the development workspace, so its real Delaunay/CHM/Rumple runtime and spatial ground distribution remain a managed-Windows QA gate.
- Units-only assignments cannot support polygon alignment, reprojection, or map overlay. A confirmed source CRS is required.
- Repository assignments invalidate conservatively when the bounded inventory fingerprint changes and must then be revalidated.
- Assumed source-local units reduce confidence in distance-sensitive preparation. They are enabled only for reviewed standalone CHM/Rumple paths and must not be treated as survey metadata.
- Independent unknown-source batch products may use per-source fallback, but mosaicking or cross-source spatial comparison still requires compatibility evidence.
