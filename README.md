# PyForestScan QGIS Plugin

PyForestScan QGIS is the planned professional QGIS Processing interface for
PyForestScan, an open-source Python library for generating forest structural
products from airborne lidar data.

This repository is the QGIS plugin home. It does not reimplement PyForestScan.
The plugin will guide users through lidar product generation while delegating
scientific computation to PyForestScan as the engine.

## Project Status

Phase 5: Dataset Explorer workflow.

This repository contains the project governance foundation, QGIS Processing
provider scaffold, environment validation, packaging helpers, dependency
documentation, adapter layer, and the first complete user workflow: Dataset
Explorer, Product Planner, and Mission Control. Dataset Explorer inspects lidar
datasets and writes JSON, CSV, and HTML inspection reports. Product Planner turns
those inspection reports into product generation plans. Mission Control provides
a dockable guided operating environment for these workflows. Scientific
PyForestScan product generation is still intentionally not implemented.

## Long-Term Goals

The plugin is intended to support:

- Canopy Height Models (CHM)
- Plant Area Index (PAI)
- Plant Area Density (PAD)
- Foliage Height Diversity (FHD)
- Canopy cover
- Rumple index
- Forest structural complexity metrics
- Batch processing
- Polygon summaries
- Publication-quality outputs

## Repository Layout

- `pyforestscan_qgis/`: Future QGIS plugin package.
- `pyforestscan_qgis/algorithms/`: Future QGIS Processing algorithms.
- `pyforestscan_qgis/core/`: Future plugin domain services and validation.
- `pyforestscan_qgis/processing/`: Future Processing provider integration.
- `pyforestscan_qgis/resources/`: Future QGIS resources.
- `pyforestscan_qgis/styles/`: Future QGIS style files and render presets.
- `pyforestscan_qgis/icons/`: Future plugin and algorithm icons.
- `tests/`: Future automated tests.
- `sample_data/`: Small documented test and tutorial data only.
- `scripts/`: Development and release helper scripts.
- `docs/`: Architecture, roadmap, strategy, testing, and release documentation.

Each directory contains a README explaining its purpose so empty folders are not
ambiguous.

## Documentation Entry Points

- [Project Vision](docs/PROJECT_VISION.md)
- [Product Requirements](docs/PRODUCT_REQUIREMENTS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/PLUGIN_ROADMAP.md)
- [Dependency Strategy](docs/DEPENDENCY_STRATEGY.md)
- [Installation Strategy](docs/INSTALLATION_STRATEGY.md)
- [Windows QGIS Dependencies](docs/development/WINDOWS_QGIS_DEPENDENCIES.md)
- [Testing Strategy](docs/TESTING_STRATEGY.md)
- [User Experience](docs/USER_EXPERIENCE.md)
- [User Guide](docs/USER_GUIDE.md)
- [Knowledge Engine](docs/development/KNOWLEDGE_ENGINE.md)
- [Mission Control](docs/ui/MISSION_CONTROL.md)

## Mission Control

Mission Control is the dockable graphical operating environment for PyForestScan
QGIS. It coordinates Environment, Dataset, Planning, Processing, Results, and
Settings pages while Processing Toolbox algorithms remain available for advanced
users.

## Dataset Explorer

Dataset Explorer is the first functional workflow. It validates and inspects LAS,
LAZ, COPC, and local EPT datasets, reports warnings and product feasibility, and
writes JSON, CSV, and HTML reports. The CSV report is automatically added to the
active QGIS project as a table when possible.

This workflow stops after inspection; it does not create CHMs or other scientific
products.

## Product Planner

Product Planner reads a Dataset Explorer JSON report, validates selected future
products, estimates output names, and writes product plan JSON, CSV, and HTML
reports. It does not create rasters or run PyForestScan calculations.

## Local QGIS Testing

Build and validate a local QGIS plugin ZIP with:

```bash
python3 scripts/package_plugin.py
python3 scripts/validate_plugin_package.py
```

Install `dist/pyforestscan_qgis.zip` through QGIS Plugin Manager using `Install from ZIP`. See [QGIS Local Testing](docs/development/QGIS_LOCAL_TESTING.md).

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

