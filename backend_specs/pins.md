# PBM Environment Pins

Phase 22C uses conservative version ranges rather than final production lock files.

## Strategy

- Python is constrained to `>=3.12,<3.13` to stay close to current QGIS-compatible Python expectations while keeping the managed backend separate from QGIS Python.
- PDAL, GDAL, rasterio, and numpy are sourced from `conda-forge` so binary geospatial dependencies resolve together.
- PyForestScan is currently specified as `pyforestscan>=0.4` through `pip` because final package-source validation is still pending.
- Exact platform locks are deferred until controlled installer validation confirms Windows, Linux, and macOS solve consistently.

These pins are not production-ready. Phase 22C proves installer architecture, staging, rollback, and verification behavior.
