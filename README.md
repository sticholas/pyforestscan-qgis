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
- Local Workspace foundation with session, timeline, history, recent items, notes, and version metadata
- QGIS result loading and product-aware raster styling
- Processing Toolbox expert surface with CHM, PAD, PAI, Canopy Cover, FHD, Rumple, Point Density, Voxel Statistic, HAG/normalization, DTM, and point-cloud preprocessing/filter controls

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
- `pyforestscan_qgis/algorithms/`: QGIS Processing algorithms. Mission Control owns guided Dataset Explorer and Product Planner workflows; the toolbox now registers Diagnostics and expert PyForestScan tools.
- `pyforestscan_qgis/core/`: QGIS-free domain services, adapter, planning, pipeline, jobs, batch, workspace, and knowledge modules.
- `pyforestscan_qgis/ui/`: Mission Control and QGIS integration helpers.
- `pyforestscan_qgis/worker/`: disabled external-worker research scaffold, not user-facing.
- `tests/`: plain-Python unit tests that do not require QGIS.
- `scripts/`: packaging and validation helpers.
- `docs/`: architecture, user, development, testing, and release documentation.

## Documentation Entry Points

- [User Guide](docs/USER_GUIDE.md)
- [Mission Control](docs/ui/MISSION_CONTROL.md)
- [Known Limitations](docs/KNOWN_LIMITATIONS.md)
- [Workspace Architecture](docs/development/WORKSPACE_ARCHITECTURE.md)
- [Internal Release Checklist](docs/releases/INTERNAL_RELEASE_CHECKLIST.md)
- [Manual QA Script](docs/development/MANUAL_QA_SCRIPT.md)
- [Batch Processing](docs/development/BATCH_PROCESSING.md)
- [External Workers](docs/development/EXTERNAL_WORKERS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Processing Toolbox Expert Tools](docs/development/ADVANCED_PROCESSING_TOOLBOX.md)
- [PyForestScan API Coverage Matrix](docs/api/PYFORESTSCAN_API_COVERAGE_MATRIX.md)
- [PyForestScan Exact Parameter Matrix](docs/api/PYFORESTSCAN_EXACT_PARAMETER_MATRIX.md)
- [PyForestScan Full Docs Inventory](docs/api/PYFORESTSCAN_FULL_DOCS_INVENTORY.md)
- [PyForestScan Full Site Crawl](docs/api/PYFORESTSCAN_FULL_SITE_CRAWL.md)
- [PyForestScan Usage and Examples Audit](docs/api/PYFORESTSCAN_USAGE_EXAMPLES_AUDIT.md)
- [PyForestScan Source / Docs Difference Audit](docs/api/PYFORESTSCAN_SOURCE_DOCS_DIFF.md)
- [PyForestScan Function Parameter Parity](docs/api/PYFORESTSCAN_FUNCTION_PARAMETER_PARITY.md)

## Local QGIS Testing

Build and validate a local QGIS plugin ZIP with:

```bash
python3 scripts/package_plugin.py
python3 scripts/validate_plugin_package.py dist/pyforestscan_qgis.zip
```

Install `dist/pyforestscan_qgis.zip` through QGIS Plugin Manager using `Install from ZIP`. See [QGIS Local Testing](docs/development/QGIS_LOCAL_TESTING.md).

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
