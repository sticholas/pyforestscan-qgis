# No-Manual-Setup Beta Smoke Test

Target artifact: `dist/pyforestscan_qgis-v0.1.0-beta.1.zip`.

## Status

Clean Windows/QGIS GUI smoke test status: **prepared, not executed in this Codex environment**.

This repository validation environment can run unit tests, compile checks, package validation, documentation link checks, and release validation. It cannot provide a fresh Windows desktop with QGIS Plugin Manager, a clean QGIS profile, and interactive Mission Control backend installation. The exact smoke procedure below is ready for the internal tester machine, and code-level blockers found during Phase 23E were closed.

Phase 23F resolved two critical clean-machine blockers reported during installer testing: Environment Check no longer raises `NameError` when PBM is missing or repair-required, and PBM installer subprocesses no longer inherit QGIS profile Python dependency paths such as `%APPDATA%\\QGIS\\QGIS3\\profiles\\default\\python\\dependencies`.

Phase 23G fixes the staged install promotion order found in clean-machine testing: PBM verifies the staged backend first, promotes verified files to final paths, writes final config, then verifies the final backend before reporting `Ready`.

Phase 23H improves staged verification diagnostics. If installation fails at `VERIFY PACKAGES`, run `python3 scripts/pbm_backend_diagnostics.py --backend-root %LOCALAPPDATA%\\PyForestScan\\backend` from a checkout to capture exact missing imports, command failures, stdout previews, and stderr previews. Phase 23I updates geospatial verification so Windows conda executables and DLLs under `env/Library/bin` are discovered without modifying global PATH.

## Preconditions

- Fresh Windows user profile or clean QGIS profile.
- QGIS 3.x installed and starts normally.
- No manually installed `pyforestscan`, `pdal`, `rasterio`, or extra scientific packages in QGIS Python.
- No existing `%LOCALAPPDATA%\PyForestScan\backend` unless testing repair/resume.
- External Worker mode is not selectable.
- Plugin installed only from `dist/pyforestscan_qgis-v0.1.0-beta.1.zip`.

## Safety Verification

Before and after PBM install, record:

- QGIS install folder timestamp/contents spot check.
- QGIS Python `site-packages` spot check for no PBM writes.
- System Python `site-packages` spot check for no PBM writes.
- User PATH before/after.
- PowerShell profile and shell profile timestamps before/after.
- PBM backend root: `%LOCALAPPDATA%\PyForestScan\backend`.
- PBM install log confirms sanitized environment policy for Micromamba, backend Python pip, verification, and runner subprocesses.

Expected result: only the user-local PBM backend folder changes. QGIS folders, QGIS Python, system Python, PATH, and shell profiles are unchanged.

## Procedure

1. Install ZIP through QGIS Plugin Manager.
2. Open Mission Control.
3. Open Settings > PyForestScan Backend Manager.
4. Click **Install Backend** and accept the confirmation.
5. Click **Verify Backend** until status is `Ready`.
6. Run Environment Check.
7. Confirm Environment Check reports:
   - QGIS Python scientific dependency status.
   - PBM backend status.
   - Selected execution backend.
   - No-manual-setup scope for Dataset Explorer and routed products.
8. Run Dataset Explorer on a small LAS/LAZ file.
9. Build a Product Plan.
10. Run CHM from Guided Mode and confirm the log/status reports PBM backend execution.
11. Run routed Advanced Toolbox products:
    - CHM.
    - Canopy Cover.
    - PAD.
    - PAI.
    - FHD.
    - Rumple.
    - DTM.
    - Point Density.
    - Voxel Statistic.
12. Run a one-file sequential batch with CHM and one additional routed product.
13. Confirm QGIS loads output rasters/tables from files written by the PBM backend.

## Expected Results

| Area | Expected result |
| --- | --- |
| ZIP install | Plugin loads without manual Python package setup. |
| PBM install | Backend installs under `%LOCALAPPDATA%\PyForestScan\backend`. |
| Environment Check | PBM Ready and selected execution backend are visible. |
| Dataset Explorer | LAS/LAZ/COPC inspection uses PBM backend when ready. |
| Routed products | CHM, Canopy Cover, PAD, PAI, FHD, Rumple, DTM, Point Density, and Voxel Statistic run through PBM. |
| Batch | Sequential and Parallel Safe modes use adapter routing; External Worker remains disabled. |
| Manual setup | No manual QGIS Python PyForestScan/PDAL setup required for Dataset Explorer and routed products. |

## Current Blockers / Deferred Items

- Manual clean Windows/QGIS execution still must be performed and recorded by an internal tester.
- Height Above Ground point-cloud export remains QGIS-Python routed.
- Preprocess Point Cloud remains QGIS-Python routed.
- Long-running PBM subprocess progress is stage/log based; fine-grained in-process progress is future work.
- Linux/macOS PBM installation remains planned/experimental until platform smoke testing is complete.

## Result Log

Fill this section during the clean-machine run.

- Date:
- Tester:
- Windows version:
- QGIS version:
- ZIP SHA-256:
- PBM backend root:
- QGIS Python scientific deps before PBM install:
- PBM install result:
- PBM verify result:
- Environment Check result:
- Dataset Explorer result:
- CHM result:
- Canopy Cover result:
- PAD result:
- PAI result:
- FHD result:
- Rumple result:
- DTM result:
- Point Density result:
- Voxel Statistic result:
- Batch result:
- QGIS folder unchanged:
- QGIS Python unchanged:
- System Python unchanged:
- PATH unchanged:
- Shell profiles unchanged:
- Tracebacks/log excerpts:
