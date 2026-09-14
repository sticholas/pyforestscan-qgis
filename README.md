# PyForestScan QGIS

PyForestScan QGIS is a QGIS plugin for processing forest structure products from LiDAR with [PyForestScan](https://pyforestscan.sefa.ai/).

## What it does

- Guided Mission Control workflow for folder and polygon processing.
- Products: CHM, DTM, PAD, PAI, FHD, canopy cover, rumple, point density, voxel statistics, and height-above-ground point clouds.
- EPT and local LiDAR support with bounded tiling, aligned mosaics, resume/checkpoints, retry, pause, and cancellation.
- Live progress with stage, product, tile, elapsed time, percentage, and ETA.
- Processing Toolbox tools for expert workflows.

Point-viewer functionality is not included in this baseline.

## Install

1. Download the versioned `pyforestscan_qgis-v0.1.0.zip` package from the release artifacts.
2. In QGIS, open **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Run the Environment Check before processing.

## Build and validate

```bash
python3 scripts/package_plugin.py --no-latest \
  --output dist/pyforestscan_qgis-v0.1.0.zip
python3 scripts/validate_plugin_package.py \
  dist/pyforestscan_qgis-v0.1.0.zip
python3 scripts/validate_packaged_import_graph.py \
  dist/pyforestscan_qgis-v0.1.0.zip
```

Focused preflight tests:

```bash
python3 -m unittest tests.test_lidar_catalog \
  tests.test_phase27j_polygon_ept tests.test_phase27o_repository_catalog -q
```

## Documentation

- [Quick Start](docs/getting-started/QUICK_START.md)
- [User Guide](docs/user-guide/README.md)
- [Product methods](docs/scientific-methods/README.md)
- [Compatibility](docs/COMPATIBILITY.md)
- [Release baseline](docs/releases/PRE_POINT_VIEWER_RELEASE_1.md)
- [Release Roadmap](docs/releases/RELEASE_ROADMAP.md)
- [Documentation index](docs/README.md)

## Development

The QGIS UI is in `pyforestscan_qgis/ui/`; processing and scheduling logic is in `pyforestscan_qgis/core/`. Historical phase notes remain in `docs/` but are not the primary specification.

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [LICENSE](LICENSE).
