# PyForestScan Full Documentation Inventory

Phase 20D performed a source-backed sweep of the official PyForestScan documentation site and the installed package source visible on this workstation.

## Official Site Inventory

Base site: https://pyforestscan.sefa.ai/

| Area | Page | URL | Phase 20D finding |
| --- | --- | --- | --- |
| Home | PyForestScan Documentation | `https://pyforestscan.sefa.ai/` | Project overview, feature list, examples, attribution. |
| Installation | Installation | `https://pyforestscan.sefa.ai/installation/` | PDAL/GDAL prerequisites, PyPI/GitHub/Docker installation guidance. |
| Usage | Importing, Preprocessing, and Writing Data | `https://pyforestscan.sefa.ai/usage/getting-started-import-and-preprocess/` | `read_lidar`, `remove_outliers_and_clean`, `classify_ground_points`, `add_height_above_ground`, `write_las`. |
| Usage | Digital Terrain Models | `https://pyforestscan.sefa.ai/usage/digital-terrain-models/` | `filter_select_ground`, `generate_dtm`, `create_geotiff`, `plot_metric`. |
| Usage | Forest Structure Introduction | `https://pyforestscan.sefa.ai/usage/forest-structure/intro/` | Product concepts and Kamoske et al. method context. |
| Usage | Canopy Height Models | `https://pyforestscan.sefa.ai/usage/forest-structure/chm/` | CHM calculation, gridded CHM, abstract polygon discussion. |
| Usage | Rumple Index | `https://pyforestscan.sefa.ai/usage/forest-structure/rumple/` | Rumple from CHM. |
| Usage | Plant Area Density | `https://pyforestscan.sefa.ai/usage/forest-structure/pad/` | PAD from voxel returns. |
| Usage | Plant Area Index | `https://pyforestscan.sefa.ai/usage/forest-structure/pai/` | PAI from PAD. |
| Usage | Foliage Height Diversity | `https://pyforestscan.sefa.ai/usage/forest-structure/fhd/` | FHD from voxel returns. |
| Benchmarks | Benchmarks | `https://pyforestscan.sefa.ai/benchmarks/` | Runtime/memory context; not a plugin API. |
| Examples | Getting Started: Importing, Preprocessing, DTMs and CHMs | `https://pyforestscan.sefa.ai/examples/getting-started-importing-preprocessing-dtm-chm/` | End-to-end import, clean, classify, DTM, point density, CHM. |
| Examples | Calculate Forest Metrics | `https://pyforestscan.sefa.ai/examples/calculate-forest-metrics/` | Voxelization, CHM, PAD, PAI, canopy cover, FHD, visualization. |
| Examples | Working with Large Point Clouds | `https://pyforestscan.sefa.ai/examples/working-with-large-point-clouds/` | EPT reads, bounds, `process_with_tiles`, polygon clipping examples. |
| API | calculate module | `https://pyforestscan.sefa.ai/api/calculate/` | Public calculate functions inventoried in full API surface. |
| API | filters module | `https://pyforestscan.sefa.ai/api/filters/` | Public filter functions inventoried in full API surface. |
| API | handlers module | `https://pyforestscan.sefa.ai/api/handlers/` | Public I/O helpers inventoried in full API surface. |
| API | pipeline module | `https://pyforestscan.sefa.ai/api/pipeline/` | The docs page returned an internal server error during Phase 20D; installed source was inspected instead. |
| API | process module | `https://pyforestscan.sefa.ai/api/process/` | `process_with_tiles` signature and workflow inventoried. |
| API | visualize module | `https://pyforestscan.sefa.ai/api/visualize/` | `plot_2d`, `plot_metric`, `plot_pad` inventoried. |
| Project | Contributing / Code of Conduct / changelog / issues | Official links | Project process pages; no Processing Toolbox API. |

## Installed Package Source Inventory

Installed package source inspected at:

`/mnt/c/Users/Lama/AppData/Roaming/Python/Python312/site-packages/pyforestscan`

Files found:

- `__init__.py`
- `calculate.py`
- `filters.py`
- `handlers.py`
- `pipeline.py`
- `process.py`
- `utils.py`
- `visualize.py`

No public classes were found in the installed package source. Public functions are documented in `PYFORESTSCAN_FULL_API_SURFACE.md`. Underscored pipeline helpers are internal and must not be called directly by the QGIS plugin unless PyForestScan documents them as public in a future release.

## Inventory Limitations

- The official pipeline API page failed during this audit. Installed source was used to identify pipeline helper functions and mark them internal.
- WSL Python did not have `pyforestscan`; installed source was inspected from the visible Windows user site-packages directory.
- QGIS/OSGeo4W Python remained the verified runtime environment for plugin execution, but this audit did not mutate that environment.
