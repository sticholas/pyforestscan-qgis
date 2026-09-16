# PyForestScan QGIS — Pre-point-viewer Release 1

Status: **release baseline / accepted**

This document marks the current `0.2.0-beta.7` processing build as the main working baseline before point-viewer development begins. It is intentionally a distinct release label; the plugin version remains `0.2.0-beta.7` so existing QGIS compatibility and upgrade semantics are preserved.

## Included baseline

- Polygon and EPT processing with bounded tiled execution and aligned mosaicking.
- One shared live progress/heartbeat stream with current product, tile, stage, elapsed time, percent, and ETA information.
- Cooperative pause, cancellation, retry, and resumable work-unit checkpoints.
- Product dependency planning across CHM, DTM/HAG, PAD, PAI, FHD, canopy cover, rumple, point density, and voxel statistics.
- Fast preflight repository resolution and spatial coverage planning without an unnecessary repository-wide header scan.
- Wheel-safe UI input behavior: page scrolling does not change combo-box or numeric values.
- Durable diagnostics and failure summaries, including preflight forensic state and best-effort performance telemetry.
- Repair for the `KeyError: 'TOTAL'` preflight telemetry crash found in the prior installed build.

## Verification performed

- Focused EPT/catalog/preflight regression suite: 30 tests passed.
- Python bytecode compilation of plugin, scripts, and tests passed.
- Release ZIP structural validation passed.
- Packaged import-graph validation passed.

The release ZIP is named `pyforestscan_qgis-v0.1.0.zip`. Future point-viewer work should branch from the `main` baseline commit rather than rewriting this release history.

## Known scope

This baseline is the processing release point before point-viewer functionality. A full live remote-EPT production run still depends on the local QGIS/PyForestScan backend environment and should be recorded as runtime evidence when performed by the release tester.
