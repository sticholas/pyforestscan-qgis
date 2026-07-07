# RC1 Manual QA Script

This script is the step-by-step manual test for RC1. It assumes a clean Windows/QGIS environment and the current candidate ZIP.

## Preparation

1. Record the candidate commit and ZIP SHA-256.
2. Start QGIS with a clean or throwaway user profile.
3. Confirm PyForestScan QGIS is not already installed.
4. Keep a sample LAS/LAZ/COPC dataset and a small folder of two or more datasets available.
5. Do not manually install PyForestScan, PDAL, GDAL, rasterio, or numpy into QGIS Python for this test.

## ZIP Install

1. Open **Plugins > Manage and Install Plugins > Install from ZIP**.
2. Select `dist/pyforestscan_qgis-v0.1.0-beta.2.zip` or `dist/pyforestscan_qgis.zip`.
3. Confirm installation succeeds without warnings that prevent loading.
4. Restart QGIS if QGIS requests it.
5. Open PyForestScan Mission Control from the plugin menu or toolbar.
6. Record any plugin-load traceback as a blocker.

## PBM Backend Setup

1. In Mission Control, open **Settings**.
2. Verify the Backend page says installation is user-local and does not modify QGIS Python or system Python.
3. Click **Install Backend**.
4. Confirm the internal beta installation dialog.
5. Observe progress until completion.
6. Click **Verify Backend** if needed.
7. Confirm backend status is `READY`.
8. Open **Environment** and refresh if needed.
9. Confirm Environment Check reports overall `READY` with PBM backend.

## Single-Dataset Guided Workflow

1. Open **Dataset**.
2. Select the sample dataset.
3. Set an output folder.
4. Click **Analyze Dataset**.
5. Confirm Dataset Summary, Technical Metadata, and footprint preview are reasonable.
6. Open **Planning**.
7. Select CHM, Canopy Cover, PAD, PAI, FHD, Rumple, DTM, Point Density, and Voxel Statistic where available in the Guided flow.
8. Build the plan.
9. Open **Processing**.
10. Confirm execution backend says PBM when READY.
11. Run processing.
12. Wait for completion and record failures as blocker/critical depending on impact.

## Results Loading

1. Open **Results**.
2. Confirm generated products are listed.
3. Click **Load Outputs**.
4. Confirm GeoTIFF and CSV outputs load into QGIS.
5. Click **Load Outputs** again.
6. Confirm duplicate layers are not loaded.
7. Confirm PAD uses the expected RGB composite when enough bands are present and other rasters use grayscale styling.

## Batch Smoke Test

1. Open **Batch**.
2. Select a small folder with two or more datasets.
3. Discover files.
4. Run preflight.
5. Run Batch in Sequential mode.
6. Confirm summary reports completed/failed/skipped counts clearly.
7. Confirm batch outputs are not loaded unless explicitly requested.

## Advanced Toolbox Smoke Test

1. Open QGIS Processing Toolbox.
2. Confirm PyForestScan groups are visible: Diagnostics, Input / I/O, Preprocessing / Filters, Terrain, Metrics.
3. Run one safe smoke test per group using sample data or a dry-run-safe configuration.
4. Confirm failures are clear and do not crash QGIS.

## Final Review

1. Reopen Mission Control Home.
2. Confirm Backend, Environment, Dataset, Workspace, generated products, loaded products, and last run are summarized compactly.
3. Review Known Limitations and release notes against observed behavior.
4. Fill out `RC1_CHECKLIST.md` evidence fields or copy them into the release issue.
5. File issues using `RELEASE_TRIAGE_POLICY.md`.
