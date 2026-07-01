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
| `pyforestscan` | Scientific engine | `import pyforestscan` through backend Python when present. |

## Future Optional Modules

The initial registry also reserves optional entries for WhiteboxTools, Open3D, PyTorch, ONNX Runtime, Segment Anything, CloudCompare CLI, Entwine, and Potree Converter. These are not installed or required in Phase 22A.

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
