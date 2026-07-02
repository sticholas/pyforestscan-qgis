# PBM Environment Spec

Phase 22B defines the initial dry-run environment specification for the future managed PyForestScan backend.

## Required Packages

The initial environment spec is registry-driven and includes:

| Package | Purpose |
| --- | --- |
| `python` | Managed backend runtime, separate from QGIS Python. |
| `pyforestscan` | Scientific engine. |
| `pdal` | Point-cloud runtime. |
| `python-pdal` | Python bindings for PDAL. |
| `gdal` | Raster/geospatial runtime and Python bindings. |
| `rasterio` | Raster IO used by product workflows. |
| `numpy` | Numeric array dependency. |

Micromamba is handled by the bootstrap plan, not as an environment package.

## Channels

The dry-run channel policy is:

- `conda-forge`: primary planned channel for Python, PDAL, GDAL, rasterio, numpy, and compatible geospatial binaries.
- `pypi-placeholder`: placeholder for PyForestScan if a conda-compatible package is unavailable in a future installer phase.

Exact version pins and lock files are deferred to Phase 22C after controlled installer validation.

## Separation From QGIS

The environment is planned under the PBM backend root in the user's profile. It is separate from QGIS Python and must not install packages into QGIS, OSGeo4W, system Python, or global user site-packages.
