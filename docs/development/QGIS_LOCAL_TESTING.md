# QGIS Local Testing

This guide explains how to install and smoke-test the development plugin in a
local QGIS profile. It does not install PyForestScan or any scientific
libraries. Dataset Explorer requires the inspected runtime dependencies to be
available in QGIS Python.

## Build the ZIP

From the repository root:

```bash
python3 scripts/package_plugin.py
python3 scripts/validate_plugin_package.py
```

The package is created at `dist/pyforestscan_qgis.zip`.

## Install the ZIP in QGIS

1. Open QGIS.
2. Go to `Plugins` > `Manage and Install Plugins...`.
3. Open `Install from ZIP`.
4. Select `dist/pyforestscan_qgis.zip`.
5. Install the plugin and enable it if QGIS does not enable it automatically.

## Optional Local Folder Sync

For rapid local testing, copy the plugin package folder into the default QGIS
profile plugin directory:

```bash
python3 scripts/package_plugin.py --sync-local
```

On Linux this targets:

```text
~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/pyforestscan_qgis
```

Use an explicit directory when testing a non-default profile or another platform:

```bash
python3 scripts/package_plugin.py --sync-local --qgis-plugin-dir /path/to/QGIS3/profiles/default/python/plugins
```

Restart QGIS after syncing so Python modules reload cleanly.

## Manual Smoke Test

Confirm the following in QGIS:

1. `Plugins` > `Manage and Install Plugins...` lists `PyForestScan`.
2. The plugin can be enabled without Python console errors.
3. Mission Control opens as a dockable panel, or can be opened from the PyForestScan toolbar/menu action.
4. Mission Control navigation switches between Home, Environment, Dataset, Planning, Processing, Results, and Settings.
5. The Environment page Refresh button displays dependency status rows.
6. The Dataset page can choose a small LAS/LAZ/COPC/EPT dataset and display an in-memory summary without writing outputs.
7. The Planning page can build an in-memory plan from the latest Dataset summary.
8. The Processing page shows the Phase 7 placeholder.
9. The Results page can choose and open an existing JSON, CSV, or HTML report.
10. `Processing` > `Toolbox` shows a `PyForestScan` provider.
11. The provider contains:
   - `Environment Check`
   - `Dataset Explorer`
   - `Product Planner`
   - `Forest Metrics Pack`
12. Run `Environment Check`.
13. Confirm the Processing log shows a readable PASS/FAIL/WARNING report.
14. Confirm missing dependencies are reported as FAIL or WARNING instead of
   crashing QGIS.
15. Run `Dataset Explorer` on a small LAS, LAZ, COPC, or local `ept.json` dataset.
16. Confirm JSON, CSV, and HTML reports are written.
17. Confirm the CSV summary is added to the QGIS project as a table when possible.
18. Run `Product Planner` with the Dataset Explorer JSON report.
19. Select one or more desired products, an output folder, grid resolution, and
   optional height bin size.
20. Confirm `product_plan.json`, `product_plan.csv`, and `product_plan.html` are
   written in the selected output folder.
21. Confirm the plan reports include product readiness, warnings, and estimated
   output paths, but no rasters are created.
22. Confirm `Forest Metrics Pack` still reports `Not yet implemented.` and does
   not create scientific outputs.

## Scope Boundary

This workflow verifies plugin loading, provider registration, package layout,
environment diagnostics, and Dataset Explorer report generation. It does not
validate CHM generation, raster creation, or scientific output correctness.
