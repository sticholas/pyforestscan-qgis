# RC1 QA Results

This document records RC1 manual QA evidence for the current package artifact. The source of truth for procedure is [RC1 Manual QA Script](RC1_MANUAL_QA_SCRIPT.md). Issue severity follows the [Release Triage Policy](RELEASE_TRIAGE_POLICY.md).

## Artifact Under Test

- Candidate version: `0.1.0-beta.2`
- Commit hash: `971d72a648cccf73fa5957c8a9df0fee76370191`
- ZIP path: `dist/pyforestscan_qgis.zip`
- Versioned ZIP path: `dist/pyforestscan_qgis-v0.1.0-beta.2.zip`
- ZIP SHA-256: `3a2c630179b09f65b1fb3ec295ab48799f60615d03d06430ee28582f7f5aa626`
- QGIS version: Not executed in QGIS during this evidence-capture pass.
- Windows version: Not captured from a clean Windows/QGIS test machine during this evidence-capture pass.
- Test machine notes: Documentation and automated validation were run from the Codex development environment against the local WSL repository. Clean Windows/QGIS GUI QA remains required before RC1 can be accepted.
- Sample dataset(s): Not executed in this evidence-capture pass.
- QA date: 2026-07-07

## Summary Decision

RC1 is **not ready for tag/release draft** yet because clean Windows/QGIS manual QA evidence is still missing for installation, PBM setup, Environment Check, Guided products, Batch, Results loading, and Advanced Toolbox smoke coverage.

Automated repository validation is expected to pass as part of this Phase 27B commit and is recorded below after validation. Automated validation is necessary but not sufficient for RC1 acceptance.

## Evidence Matrix

| Area | Status | Notes | Screenshots needed | Blocker / non-blocker |
| --- | --- | --- | --- | --- |
| ZIP install | Pending manual QA | Must install the current ZIP through QGIS Plugin Manager on a clean profile. | QGIS Plugin Manager install result; plugin listed as installed | Blocker: evidence missing |
| Plugin load | Pending manual QA | Must open QGIS, load plugin, and open Mission Control with no traceback. | Mission Control Home; QGIS log/messages if clean | Blocker: evidence missing |
| PBM install | Pending manual QA | Must install backend from Mission Control Settings on clean Windows/QGIS and verify user-local install only. | Backend progress; final READY state; backend folder path | Blocker: evidence missing |
| Environment Check | Pending manual QA | Must report overall READY with PBM backend after PBM install. | Environment page/report showing READY | Blocker: evidence missing |
| Dataset Explorer | Pending manual QA | Must analyze a sample LAS/LAZ/COPC dataset and write reports. | Dataset summary; footprint preview | Blocker: evidence missing |
| Guided products | Pending manual QA | Must run routed Guided products through PBM where supported. | Processing complete; generated output list | Blocker: evidence missing |
| Batch | Pending manual QA | Must run a small sequential batch and verify summary counts. | Batch preflight and final summary | Blocker: evidence missing |
| Results loading | Pending manual QA | Must load outputs, retry load, and verify duplicate handling/styling. | QGIS Layers panel after load; Results message | Blocker: evidence missing |
| Advanced Toolbox smoke | Pending manual QA | Must open Processing Toolbox and smoke test representative groups. | Toolbox groups; representative successful/clear-failure dialogs | Blocker: evidence missing |
| Docs current | Prepared | README, release indexes, Known Limitations, roadmap/checklist/script/triage docs are updated for RC1 gate management. | None required | Non-blocking after docs link validation passes |
| Release validation | Passed | Phase 27B automated validation commands passed after these QA documents were added. | Terminal/log output optional | Non-blocking; automated gate passed |

## ZIP Install Evidence

- Result: Pending
- Notes: This requires QGIS Plugin Manager on a clean Windows/QGIS profile. It was not executed in the Codex/WSL development environment.
- Screenshots needed: Install-from-ZIP dialog result, installed plugin entry.
- Blocker status: Blocker until executed and passed.

## Plugin Load Evidence

- Result: Pending
- Notes: Mission Control must open without plugin-load traceback on the target QGIS profile.
- Screenshots needed: Mission Control Home and QGIS message/log panel if clean.
- Blocker status: Blocker until executed and passed.

## PBM Install Evidence

- Result: Pending
- Notes: PBM must install into the user-local PyForestScan backend folder without modifying QGIS Python, system Python, PATH, shell profiles, or requiring admin rights.
- Screenshots needed: Backend progress, final Backend READY status, backend folder path.
- Blocker status: Blocker until executed and passed.

## Environment Check Evidence

- Result: Pending
- Notes: Environment Check must report READY with PBM backend after install. QGIS Python scientific dependencies may remain optional fallback details.
- Screenshots needed: Environment page/report READY state.
- Blocker status: Blocker until executed and passed.

## Dataset Explorer Evidence

- Result: Pending
- Notes: Must analyze sample data and confirm compact summary, technical metadata, footprint preview, and report paths.
- Screenshots needed: Dataset page after analysis and output folder reports.
- Blocker status: Blocker until executed and passed.

## Guided Products Evidence

- Result: Pending
- Notes: Must run routed products through PBM where supported: CHM, Canopy Cover, PAD, PAI, FHD, Rumple, DTM, Point Density, and Voxel Statistic.
- Screenshots needed: Processing completion and Results generated-products list.
- Blocker status: Blocker until executed and passed.

## Batch Evidence

- Result: Pending
- Notes: Must discover files, preflight, run a small sequential batch, and verify completed/failed/skipped counts.
- Screenshots needed: Batch preflight and final summary.
- Blocker status: Blocker until executed and passed.

## Results Loading Evidence

- Result: Pending
- Notes: Must verify GeoTIFF/CSV load, duplicate avoidance, PAD RGB composite when applicable, and grayscale styling for other rasters.
- Screenshots needed: Results page message and QGIS Layers panel.
- Blocker status: Blocker until executed and passed.

## Advanced Toolbox Smoke Evidence

- Result: Pending
- Notes: Must verify Processing Toolbox groups open and run representative smoke checks for Diagnostics, Input / I/O, Preprocessing / Filters, Terrain, and Metrics.
- Screenshots needed: Toolbox group list and representative run results.
- Blocker status: Blocker until executed and passed.

## Automated Validation Evidence

Automated validation passed in the development environment for this evidence-capture commit. This does not replace clean Windows/QGIS manual QA.

| Command | Result |
| --- | --- |
| `python3 -m unittest discover tests` | Passed: 321 tests |
| `python3 -m compileall pyforestscan_qgis` | Passed |
| `python3 scripts/package_plugin.py` | Passed; ZIP SHA-256 unchanged |
| `python3 scripts/validate_plugin_package.py dist/pyforestscan_qgis.zip` | Passed |
| `python3 scripts/check_docs_links.py` | Passed |
| `python3 scripts/validate_release.py` | Passed |
| `git diff --check` | Passed |

## Screenshots Still Needed

- QGIS Plugin Manager ZIP install result.
- Mission Control Home after plugin load.
- Backend Settings page during/after PBM install.
- Environment page showing PBM READY.
- Dataset page after Dataset Explorer.
- Processing page after Guided product completion.
- Results page before and after Load Outputs.
- QGIS Layers panel after output loading.
- Batch preflight and final summary.
- Processing Toolbox PyForestScan groups and representative smoke outputs.

## RC1 Readiness

- RC1 ready for tag/release draft: **No**
- Reason: Required clean Windows/QGIS manual QA evidence is not yet executed for the current artifact.
- Current blocker document: [RC1 Blockers](RC1_BLOCKERS.md)
