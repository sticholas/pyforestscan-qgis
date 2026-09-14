# RC1 Checklist

Use this checklist for the first formal release candidate gate. Record tester name, date, QGIS version, Windows version, ZIP SHA-256, and sample data path before starting.

## Candidate Metadata

- Candidate version:
- Commit hash:
- ZIP path:
- ZIP SHA-256:
- QGIS version:
- Windows version:
- Tester:
- Date:
- Sample dataset(s):

## Required Gate Checks

| Check | Required result | Status | Evidence / Notes |
| --- | --- | --- | --- |
| ZIP installs cleanly | QGIS Plugin Manager installs `dist/pyforestscan_qgis.zip` or versioned ZIP without error | Pending | |
| Plugin loads | Toolbar/menu/Mission Control open without plugin-load errors | Pending | |
| PBM installs on clean Windows QGIS | Backend installs into user-local PyForestScan folder only | Pending | |
| Environment Check | Reports `READY` with PBM backend after install | Pending | |
| Dataset Explorer | Runs on sample dataset and writes reports | Pending | |
| Guided products | CHM, Canopy Cover, PAD, PAI, FHD, Rumple, DTM, Point Density, Voxel Statistic run where routed | Pending | |
| Batch | Small batch run completes or records per-file failures cleanly | Pending | |
| Results loading | GeoTIFF/CSV outputs load without duplicates and use expected styling | Pending | |
| Advanced Toolbox | Opens and smoke tests representative groups | Pending | |
| No plugin-load errors | No traceback during QGIS startup or Mission Control open | Pending | |
| Docs current | README, Known Limitations, release notes, and QA docs match observed behavior | Pending | |
| Release validation | Automated validation commands pass | Pending | |

## Advanced Toolbox Smoke Coverage

Record at least one safe smoke test or dry-run-safe invocation per group:

- Diagnostics:
- Input / I/O:
- Preprocessing / Filters:
- Terrain:
- Metrics:

## Guided Product Evidence

- Dataset Explorer:
- CHM:
- Canopy Cover:
- PAD:
- PAI:
- FHD:
- Rumple:
- DTM:
- Point Density:
- Voxel Statistic:

## RC1 Decision

- Accepted for RC1:
- Blockers opened:
- Critical issues opened:
- Deferred issues documented:
- Release manager sign-off:
