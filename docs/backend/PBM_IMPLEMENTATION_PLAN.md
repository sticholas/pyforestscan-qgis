# PBM Implementation Plan

## Phase 22A: Foundation

Implemented scope:

- Core backend package.
- Cross-platform user-local path resolution.
- Typed backend models.
- Dependency registry with required and future modules.
- Config serialization helpers.
- Safe state detection and verification.
- Structured log paths and helpers.
- BackendService facade.
- Mission Control Settings status section.
- QGIS-free unit tests.

No installation or backend execution occurs.

## Phase 22B: Installer Design Validation

Implemented scope:

- QGIS compatibility layer with version parsing, Processing provider checks, settings/message-log detection, safe wrappers, and QGIS 4.x defensive warnings.
- Registry-driven dry-run install plan.
- Initial managed environment spec for python, pyforestscan, pdal, python-pdal, gdal, rasterio, numpy, scipy, pandas, shapely, pyproj, fiona, geopandas, matplotlib, and tqdm.
- Package channel policy and Micromamba bootstrap placeholders.
- Mission Control Settings buttons for Preview Install Plan and Verify QGIS Compatibility.
- Documentation and QGIS-free tests.

No downloads, installs, environment creation, QGIS Python modification, user environment-variable changes, or backend execution occur.

## Phase 22C: Controlled Installer Prototype

Implemented scope:

- Micromamba source URL policy, archive naming, download helper, checksum verification helper, and retry behavior.
- Backend environment spec files under `backend_specs/` with conservative ranges and package notes.
- User-facing Windows internal beta install guard with explicit confirmation before installer execution.
- Staging layout under `<backend_root>/staging/` with rollback on failure.
- Service methods for planning, downloading, verifying, extracting, environment creation, staged verification, config writing, and rollback.
- Mission Control Settings button that shows **Install Backend** for Windows internal beta builds and remains planned/disabled on untested platforms.
- Package script support for including backend specs in the plugin ZIP.
- QGIS-free tests with mocked downloads and no real environment creation.

Normal user installation remains disabled.

Remaining design work before broad enablement:

- Add pinned SHA-256 checksums for selected Micromamba artifacts.
- Validate exact package source strategy for PyForestScan.
- Generate locked per-platform environment files after real installer tests.
- Manually test Windows QGIS installation from ZIP with developer flag.

## Phase 22D: Production Backend Installation Engine

Implemented scope:

- `backend_manifest.json` as the single source of truth for backend version, environment version, package list, channels, artifact sources, hashes, and plugin compatibility bounds.
- Production-oriented download manager with provider abstraction, retries, resume support, progress callbacks, checksum verification, cancellation, cache reuse, and partial cleanup.
- Transactional installer stages with automatic rollback on failure or cancellation.
- Backend version manager for plugin/backend compatibility and future migration checks.
- Repair planner for missing executables, missing Python, broken environments, corrupt config, corrupt manifest, and blocked package verification.
- Structured JSON-lines logs for install, download, verify, repair, update, and remove operations.
- Declarative future module registry for PDAL, PyTorch, SAM, WhiteboxTools, CloudCompare, and Potree placeholders.
- Mission Control Settings backend controls for status, compatibility, dependency summary, storage location, install preview, repair planning, logs, advanced details, and internal beta controls.
- QGIS-free tests for manifest parsing, download behavior, transaction rollback, repair planning, version mismatch, cancellation, partial downloads, and module registration.

Windows internal beta backend installation is enabled; broader public/platform enablement remains pending checksums, lock files, platform testing, and upgrade policy.

## Phase 22E: Backend Execution Bridge

Potential scope:

- Run selected PyForestScan operations through backend Python.
- Define JSON job specs/results for backend execution.
- Keep QGIS responsive and protected from backend crashes.
- Preserve current QGIS Python workflow until backend execution is proven.
