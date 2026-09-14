# RC1 Blockers

This document lists RC1 blockers found or recorded during Phase 27B QA evidence capture for artifact `3a2c630179b09f65b1fb3ec295ab48799f60615d03d06430ee28582f7f5aa626` at commit `971d72a648cccf73fa5957c8a9df0fee76370191`.

## Summary

RC1 is currently blocked by missing clean Windows/QGIS manual QA evidence. No new product, PBM, processing, Advanced Toolbox, scientific-calculation, or External Worker code changes were made for this evidence capture.

## Blocker 1: Clean Windows/QGIS ZIP Install Evidence Missing

- Category: Blocker
- Status: Open
- Affected artifact: `dist/pyforestscan_qgis.zip`
- Reproduction / execution steps:
  1. Start QGIS with a clean or throwaway user profile.
  2. Open **Plugins > Manage and Install Plugins > Install from ZIP**.
  3. Select `dist/pyforestscan_qgis-v0.1.0-beta.2.zip` or `dist/pyforestscan_qgis.zip`.
  4. Confirm install succeeds and plugin is listed as installed.
- Expected result: ZIP installs cleanly with no blocking warnings.
- Actual result: Not executed in this evidence-capture pass.
- Required evidence: Screenshot or notes from QGIS Plugin Manager and any QGIS message log entries.

## Blocker 2: Plugin Load / Mission Control Evidence Missing

- Category: Blocker
- Status: Open
- Reproduction / execution steps:
  1. Start QGIS after ZIP install.
  2. Open PyForestScan Mission Control from toolbar or menu.
  3. Check QGIS message log and Python console for traceback.
- Expected result: Mission Control opens; no plugin-load errors.
- Actual result: Not executed in this evidence-capture pass.
- Required evidence: Mission Control Home screenshot and note that no traceback occurred.

## Blocker 3: PBM Install And READY Evidence Missing

- Category: Blocker
- Status: Open
- Reproduction / execution steps:
  1. Open Mission Control Settings.
  2. Confirm Backend page states user-local install and no QGIS/system Python modification.
  3. Click **Install Backend** and confirm.
  4. Wait for install to finish.
  5. Click **Verify Backend** if needed.
- Expected result: Backend installs into user-local PyForestScan folder and reports READY.
- Actual result: Not executed in this evidence-capture pass.
- Required evidence: Backend progress/final-state screenshot, backend folder path, and logs if failure occurs.

## Blocker 4: Environment Check READY Evidence Missing

- Category: Blocker
- Status: Open
- Reproduction / execution steps:
  1. After PBM install, open Mission Control Environment.
  2. Refresh Environment Check.
  3. Confirm overall status is READY with PBM backend.
- Expected result: Environment Check reports READY for PBM-routed products.
- Actual result: Not executed in this evidence-capture pass.
- Required evidence: Environment Check screenshot/report.

## Blocker 5: Guided Workflow Evidence Missing

- Category: Blocker
- Status: Open
- Reproduction / execution steps:
  1. Select a sample dataset on the Dataset page.
  2. Run Dataset Explorer.
  3. Build a Product Plan.
  4. Run routed Guided products through PBM where supported.
  5. Review generated outputs in Results.
- Expected result: Dataset Explorer and routed Guided products complete or report clear actionable failures.
- Actual result: Not executed in this evidence-capture pass.
- Required evidence: Dataset, Planning, Processing, and Results notes/screenshots.

## Blocker 6: Batch Evidence Missing

- Category: Blocker
- Status: Open
- Reproduction / execution steps:
  1. Open Batch.
  2. Select a small folder with two or more datasets.
  3. Discover files.
  4. Run preflight.
  5. Run sequential batch.
- Expected result: Batch completes or records per-file failures cleanly with accurate summary counts.
- Actual result: Not executed in this evidence-capture pass.
- Required evidence: Batch preflight and final summary screenshots/notes.

## Blocker 7: Results Loading Evidence Missing

- Category: Blocker
- Status: Open
- Reproduction / execution steps:
  1. Open Results after products are generated.
  2. Click **Load Outputs**.
  3. Click **Load Outputs** again.
  4. Inspect QGIS Layers panel and raster styling.
- Expected result: Outputs load once, duplicates are avoided, PAD styling is appropriate, other rasters use grayscale defaults.
- Actual result: Not executed in this evidence-capture pass.
- Required evidence: Results message and QGIS Layers panel screenshots/notes.

## Blocker 8: Advanced Toolbox Smoke Evidence Missing

- Category: Blocker
- Status: Open
- Reproduction / execution steps:
  1. Open QGIS Processing Toolbox.
  2. Confirm PyForestScan groups: Diagnostics, Input / I/O, Preprocessing / Filters, Terrain, Metrics.
  3. Run one representative smoke test per group.
- Expected result: Toolbox opens and representative tools run or fail clearly without crashing QGIS.
- Actual result: Not executed in this evidence-capture pass.
- Required evidence: Toolbox group screenshot and smoke-test notes.

## Non-Blocker Notes

- Automated repository validation can be executed in the development environment and will be recorded in [RC1 QA Results](RC1_QA_RESULTS.md).
- Linux/macOS PBM install execution, QGIS 4.x certification, External Worker mode, and post-v1 workflow expansions remain deferred per [Release Roadmap](RELEASE_ROADMAP.md).
