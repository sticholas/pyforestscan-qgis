# Changelog

All notable changes to this project will be documented in this file.

This project follows semantic versioning once plugin releases begin. Until the
first public release, changes are tracked under `Unreleased`.

## Unreleased

- Phase 24E adds the PyForestScan Design System as the plugin-wide visual and interaction language, records a UI audit with recommendations, and adds QGIS-free tests for design-system status labels, button roles, spacing tokens, expandable sections, primary actions, and empty states without changing PBM, scientific processing, or Advanced Toolbox behavior.
- Phase 24D standardizes Mission Control UX with a permanent design standard, primary-action terminology, hidden empty sections, collapsed technical/default detail, lighter Advisor/Workspace/Results pages, and QGIS-free UX regression tests while leaving PBM, processing algorithms, scientific calculations, and the Advanced Toolbox unchanged.

## 0.1.0-beta.2 - 2026-07-06

- PBM backend installation is enabled for Windows internal beta builds and installs into the user-local PyForestScan backend folder without modifying QGIS Python, system Python, PATH, shell profiles, or QGIS installation folders.
- PBM execution routing supports Dataset Explorer local inspection plus CHM, Canopy Cover, PAD, PAI, FHD, Rumple, DTM, Point Density, and Voxel Statistic when the managed backend is READY.
- Environment Check now reports execution readiness: PBM READY means overall READY for routed products, with QGIS Python scientific packages shown as optional fallback details rather than blocking failures.
- Mission Control beta UX is simplified into a compact dashboard, PBM-first Environment page, explicit Processing backend label, output-first Results page, and a three-step Batch flow with technical details collapsed by default.
- Remaining limitations: Linux/macOS PBM install execution remains planned/experimental, External Worker mode remains disabled, Height Above Ground point-cloud export and Preprocess Point Cloud still require QGIS Python integration, and clean-machine GUI smoke testing must be recorded before broader sharing.

- Phase 24B simplifies Mission Control for internal beta users: Home is a compact dashboard, Environment foregrounds PBM execution readiness with QGIS fallback details collapsed, Processing shows the active backend, Results exposes output-first actions, Batch reads as Discover / Preflight / Run, and developer-heavy PBM details stay under Advanced/Troubleshooting.
- Phase 24A prepares the internal beta release candidate by recording final ZIP SHA-256, release QA pass/pending fields, clean-machine tester checklist updates, and tag/release command preparation without creating a GitHub release.
- Phase 23N aligns Environment Check with PBM execution readiness: PBM READY now reports overall `READY`, makes QGIS Python scientific packages an optional fallback section, and prevents missing QGIS Python PyForestScan/PDAL from appearing as blocking failures when routed PBM processing is available.
- Phase 23M corrected the first PBM/QGIS Python readiness distinction and added PBM installation progress UX with a Qt worker, estimated staged progress, elapsed-time/current-action UI, hidden technical logs, disabled install/repair controls while running, and Windows no-console subprocess flags.
- Phase 23L completes the PyForestScan runtime dependency closure by adding `tqdm`, extending manifest/spec verification, setting backend-local `GDAL_DATA`, `PROJ_DATA`, and `PROJ_LIB` when conda data folders exist, and treating lingering GDAL/PROJ data messages as warnings when functionality passes.
- Phase 23K adds PyForestScan runtime dependencies to the PBM backend: scipy, pandas, Shapely, PyProj, Fiona, GeoPandas, and Matplotlib are installed from conda-forge before the PyPI-only PyForestScan package, and verification now smoke-imports PyForestScan public modules including calculate, filters, handlers, process, and visualize.
- Phase 23J fixes the remaining PBM rasterio compatibility blocker by preventing PyPI dependency resolution from replacing conda-forge geospatial binaries, tightening GDAL/rasterio/numpy environment ranges, adding deeper rasterio/GDAL/MemoryFile verification, and printing filtered conda package/build diagnostics for the geospatial stack.
- Phase 23I fixes PBM geospatial backend verification for conda-forge Windows layouts by adding explicit `libgdal` to backend specs, searching `env/Scripts`, `env/Library/bin`, `env/bin`, and `env` for executables, and prepending backend-local conda DLL/runtime paths for verification, pip install, and PBM runner subprocesses.
- Phase 23H improves PBM staged/final verification diagnostics with per-check command/executable/stdout/stderr details, actionable install failure summaries, a QGIS-free `scripts/pbm_backend_diagnostics.py` command, package/import mapping regression tests, and internal beta troubleshooting documentation.
- Phase 23G fixes PBM staged install promotion by verifying staged Micromamba/env/Python paths before promotion without requiring final config, promoting verified staged files to final backend paths, writing final backend config only after promotion, then running strict final verification before READY. Promotion now preserves previous active backend files in staging backup and restores them on failure.
- Phase 23F fixes clean-machine PBM installer isolation blockers: Environment Check now reports PBM status without crashing, PBM installer/verification/runner subprocesses use sanitized environments that remove QGIS Python/profile contamination, PyPI-only backend packages install through managed backend Python after conda environment creation, failed staging is cleaned for retry, and diagnostics record command kind/executable/clean-env policy without dumping secrets.
- Phase 23E adds no-manual-setup beta readiness documentation, routes Dataset Explorer local point-cloud inspection through PBM when READY, expands Environment Check with no-manual-setup scope, documents safety verification for QGIS/system/PATH immutability, and records remaining clean-machine smoke blockers honestly.
- Phase 23D routes CHM, Canopy Cover, PAD, PAI, FHD, Rumple, DTM, Point Density, and Voxel Statistic processing through the PBM backend when READY, adds the packaged backend runner protocol, controlled backend subprocess execution service, adapter auto/fallback execution modes, Environment Check selected-backend reporting, batch preflight PBM routing, safety checks that reject QGIS GUI executables, docs, and QGIS-free mocked tests. External Worker mode remains disabled.
- Phase 23C enables the PBM backend installer for Windows internal beta builds with user confirmation, optional-checksum handling when no pinned Micromamba checksum exists, safe archive extraction, active backend verification, Backend page progress/log messaging, PBM Environment Check reporting, and internal beta smoke-test documentation. Linux/macOS remain planned until tested, and processing routes that still use QGIS Python continue to say so.
- Phase 23B clean-machine ZIP install readiness documentation, dependency-state matrix, clearer missing-dependency guidance, Backend page release-readiness labels, and manual setup instructions.

## 0.1.0-beta.1 - 2026-07-02

Internal beta release target with versioned ZIP packaging, release manifest generation, release validation, release notes, and dry-run GitHub release preparation.

### Changed

- Matured repository documentation for internal release readiness with a professional README, master documentation index, scientific-method pages, current architecture/output docs, GitHub issue and PR templates, citation guidance, release audit report, and Markdown link checking.
- Audited and simplified the plugin for internal release readiness, including stale release-facing documentation cleanup, Settings page simplification, and clearer Batch run controls.
- Disabled unsafe External Worker batch mode in Mission Control and core guardrails after validation showed QGIS GUI Python could launch application windows; Parallel Safe mode now supports up to 6 workers with confirmation and stronger preflight recommendations.

### Added

- Phase 22D PBM production backend installation engine architecture with backend manifest, resumable download manager, transaction stages, rollback verification, repair planning, backend version manager, structured operation logs, future module registry, professional Settings backend controls, documentation, and QGIS-free tests. Public one-click installation remains disabled.

- Phase 22C PBM controlled installer prototype with Micromamba bootstrap policy, checksum/download helpers, environment spec files, developer-only install guard, staging/rollback mechanics, package spec inclusion, Settings experimental-install label, documentation, and QGIS-free mocked tests. Normal user installation remains disabled.

- Phase 22B PyForestScan Backend Manager dry-run install planning, registry-driven environment spec, Micromamba bootstrap plan placeholders, QGIS compatibility reporting, Settings page install preview, compatibility docs, and QGIS-free tests. Installation remains disabled and no downloads or environment changes occur.
- Phase 22A PyForestScan Backend Manager foundation with user-local backend path resolution, typed backend models, dependency registry, safe verification, service placeholders, Settings UI status, PBM documentation, and QGIS-free tests.
- Phase 20F parameter and language polish with clearer Processing help strings, unit-aware parameter labels, current plugin metadata, user-guide cleanup, audit artifact, and naming/metadata regression tests.
- Phase 20E full PyForestScan site rescrape, usage/examples audit, source/docs diff, Processing Toolbox reorganization, Diagnostics group, clean tool names, and hidden legacy guided toolbox entries.
- Phase 20D full PyForestScan documentation/source inventory, function parameter parity matrix, Advanced Toolbox map, deferred feature registry, grouped Advanced Toolbox labels, full SMRF filter controls, PointSourceId filtering, outlier `remove`, and HAG auto method mapping.
- Phase 20C exact Advanced Toolbox parameter parity with a parameter-by-parameter PyForestScan calculate matrix plus Advanced Point Density and Advanced Voxel Statistic algorithms.
- Phase 20B API coverage audit with Advanced DTM, Advanced Point Cloud Preprocess / Filters, expanded HAG read options, full PyForestScan coverage matrix, gap analysis, and parameter coverage docs.
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
