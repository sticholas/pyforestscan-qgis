# Changelog

All notable changes to this project will be documented in this file.

This project follows semantic versioning once plugin releases begin. Until the
first public release, changes are tracked under `Unreleased`.

## Unreleased

### Changed

- Audited and simplified the plugin for internal release readiness, including stale release-facing documentation cleanup, Settings page simplification, and clearer Batch run controls.
- Disabled unsafe External Worker batch mode in Mission Control and core guardrails after validation showed QGIS GUI Python could launch application windows; Parallel Safe mode now supports up to 6 workers with confirmation and stronger preflight recommendations.

### Added

- Advanced Processing Toolbox group with expert CHM, PAD, PAI, Canopy Cover, FHD, Rumple, and Height Above Ground/Normalize algorithms routed through adapter-backed request builders.
- Workspace Welcome and Resume UI with Continue Last Workspace, Start New Workspace, Recent Workspaces, workspace status, timeline viewer, notes editor, reset action, Home dashboard workspace state, and QGIS-free display helper tests.
- Local Workspace foundation with `.pyforestscan/` workspace folders, typed workspace/session/state/history/timeline/notes/version models, Mission Control session restore, and QGIS-free workspace tests.
- Internal release checklist, known limitations, manual QA script, product audit, and release-readiness regression tests.
- Experimental external worker research scaffold with worker job/result JSON files and subprocess entrypoint, retained behind disabled-by-default guardrails after unsafe QGIS GUI launcher behavior was found.
- Batch preflight and resume reliability with required preflight gating, disk-space checks, output conflict detection, READY environment validation, durable batch manifests, per-file job ids, checkpointed summaries after every file, skip-completed resume behavior, and retry-failed controls.
- Safe parallel batch execution framework with Sequential default, guarded Parallel safe mode, max worker validation, Qt worker-thread execution, per-file status updates, cancel/skip summaries, and QGIS-free executor tests.
- Batch Processing v2 UX with a streamlined Home dashboard, clearer batch file/result rows, pause-after-current-file, cancel-remaining, retry-failed-files, result filtering, opt-in QGIS output loading, and enhanced batch summaries.
- Batch Processing v1 with folder discovery, selectable files, sequential per-dataset execution, organized batch run folders, per-file failure recording, Mission Control Batch page, and JSON/CSV/HTML batch summaries.
- Processing Footprint summaries replaced misleading runtime prediction with selected products, raster dimensions, band counts, estimated output storage, and runtime caveats.
- Mission Control progressive disclosure UX with simplified Processing defaults, collapsed technical details, concise Scientific Advisor summaries, collapsed product explanations, and Processing Footprint output storage summaries.
- Mission Control full-window layout redesign with a 1400x900 default floating window, 1150x760 minimum size, bounded sidebar, full-page scroll regions, and grouped Planning controls.
- Scientific Advisor readability polish with a larger default Mission Control window, spacious card sections, wrapped recommendation rows, clearer warnings, and readable product explanation cards.
- Scientific Advisor Mission Control workflow with Knowledge Engine recommendations, product explanation cards, QGIS tool guidance, completed-product next steps, and UI support tests.
- Deterministic Knowledge Engine foundation with typed recommendation reports, configurable scientific thresholds, transparent calibration notes, QGIS tool suggestions, and unit tests.
- PAD default QGIS visualization as an RGB composite using bands 5/3/2, with safe fallback for shorter height-bin stacks.
- Raster auto-display stabilization with explicit QGIS raster statistics refresh, grayscale min/max contrast ranges, PAD band-1 naming, and display-range QA guidance.
- Full product workflow stabilization with floating Mission Control launch, lighter UI styling, grayscale raster defaults, friendly all-product result links, final HTML run summaries, and large dataset warnings.
- FHD and Rumple processing workflows with adapter-backed PyForestScan calls, Product Planner controls, pipeline execution, QGIS FHD raster loading, Rumple CSV summaries, tests, and manual QA documentation.
- PAD and PAI processing workflows with adapter-backed PyForestScan calls, Product Planner controls, pipeline execution, QGIS result loading, tests, and manual QA documentation.
- Dataset Footprint Preview in Mission Control with bounds-derived footprint summary, in-memory QGIS footprint layer creation, main canvas zoom, and plain-Python preview tests.
- Canopy Cover processing spike with adapter-backed PyForestScan canopy cover generation, planning controls, pipeline execution, QGIS result loading, tests, and manual QA guide.
- CHM production workflow stabilization with Mission Control parameters, stronger validation, job summary parameters, friendly CHM result links, best-effort QGIS raster polish, and QA documentation.
- CHM processing spike: adapter-backed PyForestScan CHM generation, CHM pipeline execution, Mission Control job launch, CHM result recording, and manual QGIS testing guide.
- Processing pipeline framework with validation-only registered product pipelines and Mission Control stage visualization.
- Mission Control run-folder workflow that automatically manages Dataset Explorer, Product Planner, and dry-run job files behind friendly result links.
- Dry-run job execution framework with typed job records, cancellable lifecycle, Mission Control Processing integration, Results job history, and JSON summaries.
- Mission Control manual QGIS validation record confirming dock, toolbar/menu, navigation, and placeholder behavior.
- Mission Control dock framework with Home, Environment, Dataset, Planning, Processing, Results, and Settings pages.
- Product Planner Processing workflow that reads Dataset Explorer JSON and writes JSON, CSV, and HTML product plan reports without scientific processing.
- Dataset Explorer Processing workflow with adapter-backed inspection, JSON/CSV/HTML reports, warnings, product feasibility, and CSV table loading.
- Adapter architecture audit documenting API alignment, non-QGIS core boundaries, and Phase 5 risks.
- PyForestScan adapter architecture with typed configuration, dataset validation, dataset inspection, structured logging, progress snapshots, and plugin-owned exceptions.
- Verified READY Windows/QGIS dependency baseline for PyForestScan API discovery.
- QGIS/OSGeo4W install-path mismatch troubleshooting for Windows dependency checks.
- Windows QGIS 3.44 dependency installation investigation and troubleshooting guide.
- Local QGIS plugin packaging and ZIP validation scripts.
- Manual QGIS local testing and packaging documentation.
- Environment Check Processing algorithm now produces a real PASS/FAIL/WARNING diagnostic report.
- Plain-Python dependency validation for QGIS Python, PyForestScan, PDAL, GDAL, rasterio, and numpy.
- Unit tests for dependency report creation, missing dependency handling, and report formatting.
- Initial project documentation foundation.
- Repository directory structure for the future QGIS Processing plugin.
- Architecture decision records for provider architecture, dependencies,
  repository structure, releases, testing, and user interface philosophy.

### Fixed

- Mission Control run folders now avoid overwriting previous runs by adding numeric suffixes when a timestamped folder already exists.
- Dataset Explorer Processing feedback now formats long CRS strings and numeric summaries more clearly after manual QGIS validation.
- `InspectionOptions.include_dimensions` is now honored by dataset inspection.
