# Dependency State Matrix

This matrix defines expected behavior for clean-machine ZIP installs and backend readiness checks.

| State | QGIS Python deps | PBM backend | Expected UI status | Supported actions | Expected failures |
| --- | --- | --- | --- | --- | --- |
| No backend / no QGIS deps | Missing one or more of PyForestScan, PDAL, GDAL, rasterio, numpy | Not installed | Environment Check `NOT READY`; Backend Status `Not Installed`; PBM install required | Install ZIP, open Mission Control, view Settings, run diagnostics, preview PBM plan | Dataset Explorer and scientific processing require PBM install or QGIS Python dependencies; user sees missing dependency guidance. |
| QGIS deps installed manually | Required packages import in QGIS Python | Not installed | Environment Check `READY`; Backend Status `Not Installed`; manual setup not required for current QGIS-Python workflows | Guided Mode, Advanced Toolbox, batch workflows using current adapter path | PBM backend can be installed on Windows internal beta if desired; QGIS-Python workflows already work. |
| PBM backend detected | QGIS deps may or may not be installed | Backend files/config present and verification passes | Backend Status `Ready`; Backend verification passes; selected execution backend `PBM` | Dataset Explorer plus routed CHM, Canopy Cover, PAD, PAI, FHD, Rumple, DTM, Point Density, and Voxel Statistic use PBM | Height Above Ground point-cloud export and Preprocess Point Cloud still use QGIS Python until routed. |
| Broken backend | Any | Missing executable, missing Python, corrupt config, corrupt manifest, or broken env | Backend Status `Repair Required` or `Failed`; Repair shows plan | Preview repair actions, inspect logs, preview install plan | Repair guidance and logs are shown; Windows internal beta can retry install, while update/remove remain planned. |

## What A Normal User Should Understand

- The ZIP installs the plugin UI and Processing provider.
- Scientific processing requires dependencies in the active execution path. PBM backend readiness routes supported products through PBM; unsupported tools still report QGIS Python requirements.
- PBM can install the managed backend for Windows internal beta builds; Linux/macOS remain planned until tested.
- Missing dependencies should produce `NOT READY` diagnostics, not a plugin startup crash.
- Backend auto-install is enabled for Windows internal beta with safeguards; broader platform support still depends on checksums, lock files, platform tests, and repair/update policies.
