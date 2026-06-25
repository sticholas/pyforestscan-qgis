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
3. `Processing` > `Toolbox` shows a `PyForestScan` provider.
4. The provider contains:
   - `Environment Check`
   - `Dataset Explorer`
   - `Forest Metrics Pack`
5. Run `Environment Check`.
6. Confirm the Processing log shows a readable PASS/FAIL/WARNING report.
7. Confirm missing dependencies are reported as FAIL or WARNING instead of
   crashing QGIS.
8. Run `Dataset Explorer` on a small LAS, LAZ, COPC, or local `ept.json` dataset.
9. Confirm JSON, CSV, and HTML reports are written.
10. Confirm the CSV summary is added to the QGIS project as a table when possible.
11. Confirm `Forest Metrics Pack` still reports `Not yet implemented.` and does
   not create scientific outputs.

## Scope Boundary

This workflow verifies plugin loading, provider registration, package layout,
environment diagnostics, and Dataset Explorer report generation. It does not
validate CHM generation, raster creation, or scientific output correctness.
