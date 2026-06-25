# PyForestScan QGIS Plugin

PyForestScan QGIS is the planned professional QGIS Processing interface for
PyForestScan, an open-source Python library for generating forest structural
products from airborne lidar data.

This repository is the QGIS plugin home. It does not reimplement PyForestScan.
The plugin will guide users through lidar product generation while delegating
scientific computation to PyForestScan as the engine.

## Project Status

Phase 0: Foundation.

This repository currently contains project governance, architecture direction,
documentation strategy, and the planned directory structure. Processing
algorithms, PyForestScan API calls, and GUI code are intentionally not
implemented yet.

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
- [Testing Strategy](docs/TESTING_STRATEGY.md)
- [User Experience](docs/USER_EXPERIENCE.md)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

