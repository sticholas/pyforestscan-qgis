# Architecture

PyForestScan QGIS is structured as a thin QGIS-facing application layer around
PyForestScan.

## Architectural Boundaries

- QGIS Plugin Layer: plugin loading, metadata, resources, Processing provider
  registration, and QGIS UI integration.
- Processing Layer: QGIS Processing algorithm classes, parameters, outputs,
  feedback, cancellation, and context handling.
- Core Layer: plugin-owned validation, dependency checks, configuration,
  output naming, metadata writing, and adapter interfaces.
- PyForestScan Engine: external scientific computation library.

## Dependency Direction

Processing algorithms may depend on plugin core services. Core services may
depend on stable public APIs from PyForestScan once functional work begins.
PyForestScan must not depend on the plugin.

## Planned Package Layout

- `pyforestscan_qgis/processing/`: provider registration and Processing glue.
- `pyforestscan_qgis/algorithms/`: individual algorithm definitions.
- `pyforestscan_qgis/core/`: validation, dependency strategy, output metadata,
  and adapter boundaries.
- `pyforestscan_qgis/resources/`: QGIS resources and static assets.
- `pyforestscan_qgis/styles/`: QML styles and symbology presets.
- `pyforestscan_qgis/icons/`: icons for plugin and algorithms.

## Design Rules

- Keep PyForestScan calls behind small adapter functions or services.
- Keep algorithm classes focused on QGIS parameter and result handling.
- Prefer explicit parameter schemas over implicit defaults.
- Use QGIS feedback and cancellation APIs for long-running tasks.
- Treat output metadata as part of the product, not an afterthought.

