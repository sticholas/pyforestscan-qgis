# Phase 31F Engine Repair Matrix

| Fault | Classification | Recovery |
|---|---|---|
| `pyforestscan` absent | Repair required | Restore packaged dependency contract |
| `pyforestscan.handlers` absent | Repair required | Reinstall compatible PyForestScan |
| PDAL/Rasterio/GDAL import failure | Repair required | Repair managed geospatial environment |
| Runner protocol mismatch | Incompatible/update required | Apply packaged engine contract |
| Runtime executable mismatch | Repair required | Reject accidental QGIS/user Python and repair |
| Current valid contract | Ready | Idempotent no-op |

The technical missing module is logged, while normal UI says the Processing Engine needs repair.
