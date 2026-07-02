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
| `libgdal` | Native GDAL runtime library from conda-forge. |
| `rasterio` | Raster IO used by product workflows. |
| `numpy` | Numeric array dependency. |
| `scipy` | Scientific interpolation/statistics dependency imported by PyForestScan. |
| `pandas` | Tabular support used by geospatial/scientific dependencies. |
| `shapely` | Geometry runtime used by vector/geospatial handlers. |
| `pyproj` | CRS/projection runtime used by PyForestScan handlers. |
| `fiona` | Vector file runtime used by GeoPandas/Fiona-backed handlers. |
| `geopandas` | Vector/geospatial package used by polygon/vector helper paths. |
| `matplotlib` | Visualization dependency for PyForestScan visualize imports. |
| `tqdm` | Progress dependency imported by PyForestScan tiled processing. |

Micromamba is handled by the bootstrap policy, not as an environment package.

## Pinning Strategy

Phase 22C uses conservative ranges rather than final production lock files:

- Python: `>=3.12,<3.13`.
- PDAL: `>=2.6,<2.9` from conda-forge.
- GDAL/libgdal: `>=3.8,<3.10` from conda-forge so Python bindings and native DLLs solve together.
- rasterio: `>=1.3.10,<1.5` from conda-forge, verified with its reported GDAL version and a `MemoryFile` smoke check.
- NumPy: `>=1.26,<2.0` while the Windows internal beta geospatial stack is stabilized.
- PyForestScan runtime libraries: `scipy>=1.11,<1.15`, `pandas>=2.1,<3`, `shapely>=2,<3`, `pyproj>=3.6,<4`, `fiona>=1.9,<2`, `geopandas>=0.14,<1.1`, `matplotlib>=3.8,<3.10`, and `tqdm>=4.66,<5` from conda-forge. These are explicit because PBM installs PyForestScan with pip dependency resolution disabled.
- PyForestScan: `pyforestscan>=0.4` through backend Python pip after the conda geospatial/scientific stack is complete. PBM uses `pip install --no-deps` for PyPI-only packages so pip cannot replace conda-forge GDAL, rasterio, PDAL, NumPy, SciPy, tqdm, or vector-runtime binaries.

Exact lock files are still deferred until controlled installer validation succeeds on Windows, Linux, and macOS, but Phase 23L records the current Windows beta runtime closure above.

## Separation From QGIS

The environment is planned under the PBM backend root in the user's profile. It is separate from QGIS Python and must not install packages into QGIS, OSGeo4W, system Python, or global user site-packages.
