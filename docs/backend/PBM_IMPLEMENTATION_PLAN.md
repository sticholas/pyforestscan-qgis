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
- Initial managed environment spec for python, pyforestscan, pdal, python-pdal, gdal, rasterio, and numpy.
- Package channel policy and Micromamba bootstrap placeholders.
- Mission Control Settings buttons for Preview Install Plan and Verify QGIS Compatibility.
- Documentation and QGIS-free tests.

No downloads, installs, environment creation, QGIS Python modification, user environment-variable changes, or backend execution occur.

## Phase 22C: Controlled Installer Prototype

Implemented scope:

- Micromamba source URL policy, archive naming, download helper, checksum verification helper, and retry behavior.
- Backend environment spec files under `backend_specs/` with conservative ranges and package notes.
- Developer-only installer guard using `PYFORESTSCAN_QGIS_ENABLE_BACKEND_INSTALL=1`.
- Staging layout under `<backend_root>/staging/` with rollback on failure.
- Service methods for planning, downloading, verifying, extracting, environment creation, staged verification, config writing, and rollback.
- Mission Control Settings button that remains planned/disabled unless the developer flag is present, then shows `Install Backend Experimental`.
- Package script support for including backend specs in the plugin ZIP.
- QGIS-free tests with mocked downloads and no real environment creation.

Normal user installation remains disabled.

Remaining design work before broad enablement:

- Add pinned SHA-256 checksums for selected Micromamba artifacts.
- Validate exact package source strategy for PyForestScan.
- Generate locked per-platform environment files after real installer tests.
- Manually test Windows QGIS installation from ZIP with developer flag.

## Phase 22D: Backend Execution Bridge

Potential scope:

- Run selected PyForestScan operations through backend Python.
- Define JSON job specs/results for backend execution.
- Keep QGIS responsive and protected from backend crashes.
- Preserve current QGIS Python workflow until backend execution is proven.
