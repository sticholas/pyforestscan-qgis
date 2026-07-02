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
- Python import checks for `pyforestscan`, `pdal`, `osgeo.gdal`, `rasterio`, and `numpy`,
- command, executable, stdout preview, and stderr preview for each command-backed check.

## Package and Import Mapping

The current backend spec and manifest expect:

| Purpose | Package source | Package name | Verification |
| --- | --- | --- | --- |
| Python runtime | conda-forge | `python>=3.12,<3.13` | `python --version` |
| PDAL executable | conda-forge | `pdal` | `pdal --version` |
| PDAL Python bindings | conda-forge | `python-pdal` | `import pdal` |
| GDAL runtime/bindings | conda-forge | `gdal` | `gdalinfo --version`, `import osgeo.gdal` |
| rasterio | conda-forge | `rasterio` | `import rasterio` |
| NumPy | conda-forge | `numpy` | `import numpy` |
| PyForestScan | PyPI | `pyforestscan>=0.4` | `import pyforestscan` |

Micromamba installs the conda-forge packages first. PyPI-only packages are installed afterward through the staged backend Python with a sanitized environment.

## Common Failure Patterns

`python-pdal import failed: No module named pdal`

The conda environment was created but the PDAL Python bindings are missing or unavailable for the selected Windows/Python combination. Confirm whether `python-pdal` exists for Windows and Python 3.12 on conda-forge, or pin a compatible backend Python/package set in a later manifest.

`osgeo.gdal import failed: DLL load failed`

GDAL Python bindings are present but cannot load their native DLLs. Check the staged environment `Library/bin`/DLL layout and whether the sanitized environment still needs a backend-local DLL path for verification on Windows.

`pdal --version failed: executable not found`

The PDAL runtime package did not create the expected `pdal.exe` under the staged environment. Confirm package solve output and staged `env/Scripts` contents.

## Repair and Retry

If installation fails during staged verification, PBM rolls back staging enough for retry. If `staging/` remnants remain, the repair plan reports `staging_remnants` and recommends cleanup/retry. PBM must still not modify QGIS Python, QGIS install folders, system Python, PATH, shell profiles, or global user environment variables.
