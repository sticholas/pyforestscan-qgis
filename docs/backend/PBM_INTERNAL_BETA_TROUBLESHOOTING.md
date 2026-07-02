# PBM Internal Beta Troubleshooting

Phase 23H adds actionable staged/final backend verification diagnostics for clean-machine installer failures.

## Diagnostic Command

Run from the repository root:

```bash
python3 scripts/pbm_backend_diagnostics.py --backend-root <backend-root>
```

On Windows internal beta machines, `<backend-root>` is normally:

```text
%LOCALAPPDATA%\PyForestScan\backend
```

The command does not require QGIS. It prints:

- final backend paths and config status,
- staged backend paths when `staging/` exists,
- executable existence checks,
- `python --version`,
- `pdal --version`,
- Python import checks for `pyforestscan`, `pdal`, `osgeo.gdal`, `rasterio`, `numpy`, `scipy`, `pandas`, `shapely`, `pyproj`, `fiona`, `geopandas`, `matplotlib`, and `tqdm`,
- a PyForestScan smoke import for `pyforestscan.calculate`, `pyforestscan.filters`, `pyforestscan.handlers`, `pyforestscan.process`, and `pyforestscan.visualize`,
- command, executable, stdout preview, and stderr preview for each command-backed check,
- filtered `micromamba list -p <env>` diagnostics for `python`, `gdal`, `libgdal`, `rasterio`, `numpy`, `scipy`, `pandas`, `shapely`, `pyproj`, `fiona`, `geopandas`, `matplotlib`, `tqdm`, `pdal`, `python-pdal`, `geos`, `proj`, `sqlite`, `libcurl`, `tiledb`, `zstd`, and `lz4`.

## Package and Import Mapping

The current backend spec and manifest expect:

| Purpose | Package source | Package name | Verification |
| --- | --- | --- | --- |
| Python runtime | conda-forge | `python>=3.12,<3.13` | `python --version` |
| PDAL executable | conda-forge | `pdal` | `pdal --version` |
| PDAL Python bindings | conda-forge | `python-pdal` | `import pdal` |
| GDAL runtime/bindings | conda-forge | `gdal`, `libgdal` | `gdalinfo --version`, `import osgeo.gdal` |
| rasterio | conda-forge | `rasterio>=1.3.10,<1.5` | `import rasterio`, report `rasterio.__gdal_version__`, open/close `MemoryFile` |
| NumPy | conda-forge | `numpy>=1.26,<2.0` | `import numpy` |
| SciPy | conda-forge | `scipy>=1.11,<1.15` | `import scipy` |
| pandas | conda-forge | `pandas>=2.1,<3` | `import pandas` |
| Shapely | conda-forge | `shapely>=2,<3` | `import shapely` |
| PyProj | conda-forge | `pyproj>=3.6,<4` | `import pyproj` |
| Fiona | conda-forge | `fiona>=1.9,<2` | `import fiona` |
| GeoPandas | conda-forge | `geopandas>=0.14,<1.1` | `import geopandas` |
| Matplotlib | conda-forge | `matplotlib>=3.8,<3.10` | `import matplotlib` |
| tqdm | conda-forge | `tqdm>=4.66,<5` | `import tqdm` |
| PyForestScan | PyPI | `pyforestscan>=0.4` | `import pyforestscan` plus calculate/filters/handlers/process/visualize smoke imports |

Micromamba installs the conda-forge packages first. PyPI-only packages are installed afterward through the staged backend Python with `pip install --no-deps` and a sanitized environment. Because pip dependency resolution is disabled, PyForestScan runtime imports such as SciPy, Matplotlib, and tqdm must be listed explicitly in the backend specs and manifest. On Windows, verification searches `env/Scripts`, `env/Library/bin`, `env/bin`, and `env` for executables, prepends `env`, `env/Scripts`, and `env/Library/bin` to subprocess PATH, and sets backend-local `GDAL_DATA`, `PROJ_DATA`, and `PROJ_LIB` when `env/Library/share/gdal` and `env/Library/share/proj` exist.

## Common Failure Patterns

`python-pdal import failed: No module named pdal`

The conda environment was created but the PDAL Python bindings are missing or unavailable for the selected Windows/Python combination. Confirm whether `python-pdal` exists for Windows and Python 3.12 on conda-forge, or pin a compatible backend Python/package set in a later manifest.

`osgeo.gdal import failed: DLL load failed`

GDAL Python bindings are present but cannot load their native DLLs. Check the staged environment `Library/bin`/DLL layout and the diagnostic command's PATH details. PBM verification should include backend-local conda DLL paths; if this still fails, the likely blocker is package solve compatibility or a missing native dependency in the conda environment.

`rasterio import failed: DLL load failed while importing _base: The specified procedure could not be found`

Rasterio is present but its compiled extension is not compatible with the active GDAL/libgdal DLL set or another native dependency. Phase 23J pins Windows beta ranges to `gdal/libgdal>=3.8,<3.10`, `rasterio>=1.3.10,<1.5`, and `numpy>=1.26,<2.0`, then verifies `rasterio.__gdal_version__` and `MemoryFile`. Diagnostics include filtered conda package/build lines for rasterio, GDAL/libgdal, GEOS, PROJ, SQLite, libcurl, TileDB, zstd, and lz4.

`pdal --version failed: executable not found`

The PDAL runtime package did not create `pdal.exe` under `env/Scripts`, `env/Library/bin`, `env/bin`, or `env`. Confirm package solve output and staged environment contents.

`pyforestscan import failed: No module named scipy` or `No module named tqdm`

PyForestScan installed from PyPI, but its runtime dependencies were not present because PBM intentionally uses `pip install --no-deps`. Phase 23K/23L makes SciPy, pandas, Shapely, PyProj, Fiona, GeoPandas, Matplotlib, and tqdm conda-forge dependencies installed before PyForestScan verification.

`GDAL_DATA is not defined`

PBM now sets backend-local `GDAL_DATA`, `PROJ_DATA`, and `PROJ_LIB` when matching conda data folders exist. If a warning still appears but the GDAL/rasterio/PyForestScan checks pass, PBM records it as a warning for diagnosis rather than failing the backend.

## Repair and Retry

If installation fails during staged verification, PBM rolls back staging enough for retry. If `staging/` remnants remain, the repair plan reports `staging_remnants` and recommends cleanup/retry. PBM must still not modify QGIS Python, QGIS install folders, system Python, PATH, shell profiles, or global user environment variables.
