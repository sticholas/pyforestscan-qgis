# Phase 28H FlyPath UX Reference

Reference: [FlyPath repository](https://github.com/dronnix-io/FlyPath) and [QGIS plugin listing](https://plugins.qgis.org/plugins/FlyPath/). No FlyPath source code or styling is included.

## Patterns worth borrowing

- One focused dock beside the map.
- Spatial selection is a map action, not a separate administrative workflow.
- Derived values update near their inputs.
- A sequential workflow stays visible without page-by-page navigation.
- One dominant final action changes the panel into a result state.
- Contextual detail is available without making diagnostics permanently visible.

## Patterns not appropriate here

PyForestScan has a managed scientific backend, long-running resumable jobs, multiple repository types, batch processing, and a QGIS Processing provider. Those capabilities require a secondary setup/tools surface and durable history that a flight-path exporter does not need.

## Applied changes

Mission Control now exposes only **Process** and **Tools & Setup**. Process contains data, area, products, output, readiness, execution progress, current result actions, and collapsed Previous Runs. Tools & Setup synthesizes environment, preferences, backend management, guidance access, and the existing Processing Toolbox. The redundant footer is hidden, normal width starts at 420 px, and detailed checks/repository tools remain progressively disclosed.
