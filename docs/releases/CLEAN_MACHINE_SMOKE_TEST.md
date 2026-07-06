# Clean Machine ZIP Smoke Test

Target artifact: `dist/pyforestscan_qgis-v0.1.0-beta.1.zip`.

This checklist is for a clean Windows/QGIS environment where PyForestScan QGIS is installed only from the ZIP. It separates plugin install readiness from scientific dependency readiness.

## Preflight

- Confirm QGIS 3.x is installed and starts normally.
- Confirm the plugin ZIP is the versioned artifact, not an unpacked working tree.
- Confirm no existing `pyforestscan_qgis` plugin folder is present in the active QGIS profile.
- Confirm External Worker mode is not selectable after install.
- Confirm the build is the Windows internal beta ZIP when testing backend install. No developer environment variable should be required for the normal PBM flow.

## ZIP Install

1. Open QGIS Plugin Manager.
2. Choose **Install from ZIP**.
3. Select `dist/pyforestscan_qgis-v0.1.0-beta.1.zip`.
4. Confirm QGIS accepts the ZIP without traceback.
5. Restart QGIS if QGIS requests it.

Expected result: plugin loads, toolbar/menu entry appears, and Mission Control opens or can be opened from the PyForestScan menu.

## Startup And UI

- Mission Control opens as a floating/movable window.
- Home page renders without requiring PyForestScan imports.
- Settings > PyForestScan Backend Manager renders without creating backend files.
- Backend page says Windows internal beta backend auto-install is available, or explains why the platform is planned/experimental.
- Manual Setup Instructions button explains PBM backend versus QGIS Python execution paths.

## Environment Check

1. Open Mission Control > Environment.
2. Click Refresh Environment.
3. Run Processing Toolbox > PyForestScan / Diagnostics / Environment Check.

Expected result with missing dependencies: no crash; report is `NOT READY` and lists missing `pyforestscan`, `pdal`, `osgeo.gdal`, `rasterio`, or `numpy` with guidance.

Expected result with dependencies present: report is `READY`; Guided Mode and Advanced Toolbox processing can be tested with a small LAS/LAZ file.

## Advanced Toolbox

- Confirm Processing Toolbox shows PyForestScan groups:
  - Diagnostics
  - Input / I/O
  - Preprocessing / Filters
  - Terrain
  - Metrics
- Confirm algorithms open dialogs without importing PyForestScan at dialog construction time.
- If dependencies are missing, running scientific algorithms should fail with a clear Processing error rather than crashing QGIS.

## Guided Mode Smoke

Only run this section when Environment Check is `READY`.

1. Select a small LAS/LAZ/COPC/EPT dataset.
2. Run Dataset Explorer.
3. Build Product Planner output.
4. Run CHM only.
5. Confirm outputs and reports are written under `pyforestscan_runs/`.
6. Confirm output raster loads into QGIS.

## Backend Page Smoke

- Verify Backend reports missing/not installed state clearly when no PBM backend exists.
- Preview Install Plan shows paths, package list, verification steps, rollback notes, and warnings.
- Repair shows a plan and log guidance.
- On Windows internal beta builds, Install Backend is enabled and requires confirmation before action.
- On Linux/macOS, Install Backend remains planned/experimental until platform smoke testing is complete.

## Release Readiness Status

| Item | Status for v0.1.0-beta.1 | Notes |
| --- | --- | --- |
| ZIP install ready | Yes, pending this clean-machine smoke result | Structural package validation passes. |
| Mission Control startup | Expected yes | Does not require scientific deps at import time. |
| Environment Check with missing deps | Expected yes | Must report `NOT READY`, not crash. |
| Advanced Toolbox visible | Expected yes | Provider registration should not require PyForestScan import. |
| Guided Mode scientific processing | Yes when its active execution path has dependencies | PBM backend readiness is reported separately; tools not routed through PBM still require QGIS Python deps. |
| Backend auto-install ready | Yes for Windows internal beta | Linux/macOS remain planned/experimental until tested. |
| Manual dependency setup required | No after successful PBM install for backend readiness | Current QGIS-Python workflows still report their own requirements until routed through PBM. |

## Result Log

Record the following after testing:

- QGIS version:
- Windows version:
- ZIP SHA-256:
- Install result:
- Mission Control result:
- Environment Check result:
- Advanced Toolbox result:
- Guided Mode result:
- Backend page clarity issues:
- Tracebacks or QGIS log messages:


## Phase 24A Result Fields

Artifact SHA-256: `70708bce2c719b338a692e34f448100980bba1e6c8bc664f7a7ee3601e89b4ba`

| QA item | Status | Notes |
| --- | --- | --- |
| ZIP install in QGIS | Pending manual tester | Requires clean Windows/QGIS GUI profile. |
| Mission Control opens | Pending manual tester | Confirm toolbar/menu launch. |
| PBM backend install | Pending manual tester | Confirm progress UI reaches Backend Ready. |
| Environment Check after PBM | Pending manual tester | Expected overall `READY`. |
| Guided Dataset Explorer | Pending manual tester | Small LAS/LAZ/COPC. |
| Guided CHM | Pending manual tester | PBM-routed. |
| Guided Canopy Cover | Pending manual tester | PBM-routed. |
| Guided PAD | Pending manual tester | PBM-routed. |
| Guided PAI | Pending manual tester | PBM-routed. |
| Guided FHD | Pending manual tester | PBM-routed. |
| Guided Rumple | Pending manual tester | PBM-routed. |
| Advanced Toolbox groups | Pending manual tester | Confirm groups appear cleanly. |
| Small batch run | Pending manual tester | Sequential PBM-routed batch. |
| No manual QGIS Python deps | Pending manual tester | Confirm routed products run without QGIS Python PyForestScan/PDAL. |
