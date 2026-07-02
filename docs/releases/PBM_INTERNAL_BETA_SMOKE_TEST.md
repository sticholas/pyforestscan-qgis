# PBM Internal Beta Smoke Test

Target artifact: `dist/pyforestscan_qgis-v0.1.0-beta.1.zip`.

This checklist validates the Phase 23C Windows internal beta backend installer. It must be run on a clean Windows/QGIS 3.x profile where the plugin is installed only from the ZIP.

## Safety Preconditions

- Confirm the test user does not need administrator privileges.
- Confirm QGIS starts normally before installing the plugin.
- Confirm External Worker mode is unavailable/disabled.
- Confirm no manual Conda, Micromamba, or QGIS Python package setup is required for the PBM install path.
- Confirm the installer target is user-local, normally `%LOCALAPPDATA%\PyForestScan\backend`.
- Confirm PBM does not modify QGIS Python, the QGIS install folder, system Python, PATH, shell profiles, or user environment variables.

## ZIP Install

1. Open QGIS Plugin Manager.
2. Install `dist/pyforestscan_qgis-v0.1.0-beta.1.zip` from ZIP.
3. Confirm the plugin loads without traceback.
4. Open Mission Control.
5. Confirm Advanced Toolbox groups are visible.

Expected result: Mission Control and Processing provider load without requiring scientific dependencies at import time.

## Backend Install

1. Open Mission Control Settings > PyForestScan Backend Manager.
2. Confirm Backend Status is `Not Installed` on a clean machine.
3. Confirm platform support text says Windows internal beta is supported and Linux/macOS are planned/experimental.
4. Click **Preview Install Plan** and confirm paths, package list, platform, warnings, verification steps, rollback/repair notes, and offline placeholder are readable.
5. Click **Install Backend**.
6. Confirm the dialog says: `This will install PyForestScan backend packages into your user-local PyForestScan folder. It will not modify QGIS or system Python.`
7. Accept the dialog.
8. Watch progress/log preview through download, checksum-if-present, extraction, environment creation, verification, promotion, and config writing.

Expected result: PBM writes only under the user-local backend root and ends with Backend Status `Ready`.

## Verification

After install, click **Verify Backend** and confirm:

- Backend Python runs.
- `import pyforestscan` passes.
- `import pdal` passes.
- `import osgeo.gdal` passes.
- `import rasterio` passes.
- `import numpy` passes.
- `pdal --version` passes.
- Backend config exists and status is `Ready`.
- Environment Check reports PBM managed backend readiness.

## Processing Routing Smoke

Confirm Environment Check shows:

- QGIS Python scientific dependencies.
- PBM backend readiness.
- Selected execution backend.

When PBM is Ready, CHM, Canopy Cover, PAD, PAI, FHD, Rumple, DTM, Point Density, and Voxel Statistic should report/use the PBM backend execution path. Height Above Ground point-cloud export and Preprocess Point Cloud may still require QGIS Python dependencies until routed.

## Guided / Advanced / Batch Smoke

Run these with a tiny known-good LAS/LAZ dataset:

1. Run Environment Check and record QGIS Python readiness plus PBM backend readiness.
2. Run Dataset Explorer.
3. Run CHM from Guided Mode if the workflow reports dependencies ready for its execution path.
4. Run one Advanced Toolbox diagnostic or metric that is supported by the active execution path.
5. Run a one-file sequential batch.

If a tool still uses QGIS Python and dependencies are missing there, it must fail with clear guidance rather than claiming PBM powers that tool.

## Failure / Repair Smoke

- Disconnect network and confirm install failure shows the failed stage and log path.
- Click **View Logs** and confirm install log entries are visible.
- Click **Repair** and confirm repair guidance is shown.
- Confirm retry does not require admin rights or manual Micromamba installation.

## Result Record

- QGIS version:
- Windows version:
- ZIP SHA-256:
- Backend root:
- Install result:
- Verify Backend result:
- Environment Check result:
- Dataset Explorer result:
- CHM result:
- Batch result:
- Failures/log snippets:
- Processing integration gaps:
