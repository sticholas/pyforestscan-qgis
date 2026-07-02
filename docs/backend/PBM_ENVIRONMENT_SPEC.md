# PBM Environment Spec

Phase 22C adds backend environment spec files for the future managed PyForestScan backend.

## Spec Files

The repository now includes:

```text
backend_specs/
  environment.yml
  environment.windows.yml
  environment.linux.yml
  environment.macos.yml
  pins.md
```

The packaging script includes these files inside the plugin ZIP under `pyforestscan_qgis/backend_specs/` so the internal beta installer can locate them from an installed plugin.

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

Micromamba is handled by the bootstrap policy, not as an environment package.

## Pinning Strategy

Phase 22C uses conservative ranges rather than final production lock files:

- Python: `>=3.12,<3.13`.
- PDAL/GDAL/rasterio/numpy: conda-forge geospatial stack with conservative lower bounds.
- PyForestScan: `pyforestscan>=0.4` through pip until package-source validation is complete.

Exact lock files and platform-specific final pins are deferred until controlled installer validation succeeds on Windows, Linux, and macOS.

## Separation From QGIS

The environment is planned under the PBM backend root in the user's profile. It is separate from QGIS Python and must not install packages into QGIS, OSGeo4W, system Python, or global user site-packages.
