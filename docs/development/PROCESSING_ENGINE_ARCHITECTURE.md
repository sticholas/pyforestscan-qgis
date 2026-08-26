# Processing Engine Architecture

The Processing Engine is the single user-facing readiness boundary for PyForestScan scientific work. QGIS owns interface state, spatial selection, request construction, and output loading. The isolated user-local engine owns PyForestScan, PDAL, Rasterio, GDAL/PROJ, preparation, and scientific execution.

`ProcessingEngineVerifier` probes the same executable used by `BackendExecutionService`. Folder and Polygon processing share this service. A job cannot be created when the engine contract is incomplete; setup faults are engine errors rather than scientific batch results.

States are `READY`, `CHECKING`, `SETUP_REQUIRED`, `UPDATING`, `REPAIR_REQUIRED`, `INCOMPATIBLE`, and `FAILED`. Normal UI translates backend implementation details into Processing Engine status. PBM terminology and module-level diagnostics remain under troubleshooting.

The engine lives under the user-local PyForestScan backend directory. It does not alter QGIS Python, system Python, global `PATH`, or shell profiles. External Worker mode remains disabled.
