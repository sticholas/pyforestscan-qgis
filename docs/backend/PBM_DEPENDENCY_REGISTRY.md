# PBM Dependency Registry

PBM uses a registry-driven model so backend dependencies can evolve without hardcoding PDAL assumptions into UI or orchestration code.

## Required Initial Dependencies

| Name | Purpose | Verification |
| --- | --- | --- |
| `micromamba` | User-local environment manager | Executable version command when present. |
| `python` | Managed backend Python runtime | Backend Python version command when present. |
| `pdal` | Point-cloud runtime | `pdal --version` from the backend environment when present. |
| `python-pdal` | PDAL Python bindings | `import pdal` through backend Python when present. |
| `gdal` | Raster/vector geospatial stack | `gdalinfo --version` and `import osgeo.gdal` when present. |
| `rasterio` | Raster writing/reading | `import rasterio` through backend Python when present. |
| `numpy` | Array processing | `import numpy` through backend Python when present. |
| `scipy` | Scientific interpolation/statistics runtime | `import scipy` through backend Python when present. |
| `pandas` | Tabular runtime used by vector/scientific dependencies | `import pandas` through backend Python when present. |
| `shapely` | Geometry runtime | `import shapely` through backend Python when present. |
| `pyproj` | CRS/projection runtime | `import pyproj` through backend Python when present. |
| `fiona` | Vector file runtime | `import fiona` through backend Python when present. |
| `geopandas` | Vector/geospatial runtime | `import geopandas` through backend Python when present. |
| `matplotlib` | PyForestScan visualize runtime | `import matplotlib` through backend Python when present. |
| `tqdm` | PyForestScan tiled-processing progress runtime | `import tqdm` through backend Python when present. |
| `pyforestscan` | Scientific engine | `import pyforestscan` and public submodules through backend Python when present. |

## Future Optional Modules

The initial registry also reserves optional entries for WhiteboxTools, Open3D, PyTorch, ONNX Runtime, Segment Anything, CloudCompare CLI, Entwine, and Potree Converter. These are not installed or required in Phase 22C.

## Dependency Fields

Each `BackendDependency` records:

- `name`
- `display_name`
- `category`
- `required`
- `version_spec`
- `source`
- `executable_name`
- `python_import_name`
- `verification_command`
- `install_status`
- `verification_status`
- `detected_version`
- `update_available`
- `notes`

Registry state can be serialized into `backend.json` as `dependency_registry_state`.
