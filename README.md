# PyForestScan QGIS Plugin

PyForestScan QGIS is a professional QGIS interface for PyForestScan, an open-source Python library for generating forest structural products from airborne lidar data. The plugin does not reimplement PyForestScan; it guides users through inspection, planning, processing, review, and batch operations while delegating scientific computation through the adapter layer.

## Current Status

The project is preparing for a stable internal release. Current implemented workflows include:

- Mission Control guided desktop workflow
- Environment Check
- Dataset Explorer with JSON, CSV, and HTML reports
- Dataset footprint preview
- Scientific Advisor recommendations
- Product Planner
- Single-dataset processing for CHM, Canopy Cover, PAD, PAI, FHD, and Rumple summary
- Batch folder-to-products workflow with preflight, manifest, resume, retry, and guarded Parallel Safe mode
- QGIS result loading and product-aware raster styling

External Worker mode is disabled. Sequential batch processing remains the safest path, and Parallel Safe mode is available with preflight guardrails.

## Product Outputs

Implemented output defaults are:

| Product | Default output | Notes |
| --- | --- | --- |
| CHM | `chm.tif` | Single-band GeoTIFF. |
| Canopy Cover | `canopy_cover.tif` | Single-band GeoTIFF. |
| PAD | `pad.tif` | Multi-band GeoTIFF; default QGIS display uses RGB bands 5/3/2 when available. |
| PAI | `pai.tif` | Single-band GeoTIFF. |
| FHD | `fhd.tif` | Single-band GeoTIFF. |
| Rumple | `rumple_summary.csv` | CSV summary table. |

## Repository Layout

- `pyforestscan_qgis/`: QGIS plugin package.
- `pyforestscan_qgis/algorithms/`: QGIS Processing algorithms for Environment Check, Dataset Explorer, Product Planner, and current placeholder toolbox entries.
- `pyforestscan_qgis/core/`: QGIS-free domain services, adapter, planning, pipeline, jobs, batch, and knowledge modules.
- `pyforestscan_qgis/ui/`: Mission Control and QGIS integration helpers.
- `pyforestscan_qgis/worker/`: disabled external-worker research scaffold, not user-facing.
- `tests/`: plain-Python unit tests that do not require QGIS.
- `scripts/`: packaging and validation helpers.
- `docs/`: architecture, user, development, testing, and release documentation.

## Documentation Entry Points

- [User Guide](docs/USER_GUIDE.md)
- [Mission Control](docs/ui/MISSION_CONTROL.md)
- [Known Limitations](docs/KNOWN_LIMITATIONS.md)
- [Internal Release Checklist](docs/releases/INTERNAL_RELEASE_CHECKLIST.md)
- [Manual QA Script](docs/development/MANUAL_QA_SCRIPT.md)
- [Batch Processing](docs/development/BATCH_PROCESSING.md)
- [External Workers](docs/development/EXTERNAL_WORKERS.md)
- [Architecture](docs/ARCHITECTURE.md)

## Local QGIS Testing

Build and validate a local QGIS plugin ZIP with:

```bash
python3 scripts/package_plugin.py
python3 scripts/validate_plugin_package.py dist/pyforestscan_qgis.zip
```

Install `dist/pyforestscan_qgis.zip` through QGIS Plugin Manager using `Install from ZIP`. See [QGIS Local Testing](docs/development/QGIS_LOCAL_TESTING.md).

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
