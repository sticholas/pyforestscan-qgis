# Changelog

All notable changes to this project will be documented in this file.

This project follows semantic versioning once plugin releases begin. Until the
first public release, changes are tracked under `Unreleased`.

## Unreleased

### Added

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

- `InspectionOptions.include_dimensions` is now honored by dataset inspection.
