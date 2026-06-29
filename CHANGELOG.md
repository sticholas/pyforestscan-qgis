# Changelog

All notable changes to this project will be documented in this file.

This project follows semantic versioning once plugin releases begin. Until the
first public release, changes are tracked under `Unreleased`.

## Unreleased

### Added

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
