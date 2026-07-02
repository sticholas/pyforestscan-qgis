# Dependency State Matrix

This matrix defines expected behavior for clean-machine ZIP installs and backend readiness checks.

| State | QGIS Python deps | PBM backend | Expected UI status | Supported actions | Expected failures |
| --- | --- | --- | --- | --- | --- |
| No backend / no QGIS deps | Missing one or more of PyForestScan, PDAL, GDAL, rasterio, numpy | Not installed | Environment Check `NOT READY`; Backend Status `Not Installed`; manual setup required | Install ZIP, open Mission Control, view Settings, run diagnostics, preview PBM plan | Scientific Guided/Advanced processing cannot run; user sees missing dependency guidance. |
| QGIS deps installed manually | Required packages import in QGIS Python | Not installed | Environment Check `READY`; Backend Status `Not Installed`; manual setup not required for current QGIS-Python workflows | Guided Mode, Advanced Toolbox, batch workflows using current adapter path | PBM backend execution still unavailable; Install Backend remains planned/disabled. |
| PBM backend detected | QGIS deps may or may not be installed | Backend files/config present and verification passes | Backend Status `Ready`; Backend verification passes | Backend can be inspected/verified; future execution bridge can target it later | Current scientific workflows still use QGIS Python until backend execution bridge is implemented. |
| Broken backend | Any | Missing executable, missing Python, corrupt config, corrupt manifest, or broken env | Backend Status `Repair Required` or `Failed`; Repair shows plan | Preview repair actions, inspect logs, preview install plan | Repair execution and auto-install remain disabled for normal users. |

## What A Normal User Should Understand

- The ZIP installs the plugin UI and Processing provider.
- Scientific processing requires scientific dependencies in QGIS Python for this beta.
- PBM is visible for transparency and future backend management, but it does not install packages for normal users yet.
- Missing dependencies should produce `NOT READY` diagnostics, not a plugin startup crash.
- Backend auto-install cannot be enabled until checksums, lock files, platform tests, and repair/update policies are complete.
