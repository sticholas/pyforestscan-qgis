# Processing Engine Convergence

Phase 31G makes the managed Processing Engine the sole owner of production scientific execution. QGIS Python owns UI, QGIS integration, request construction, and result loading; it must not import PyForestScan, PDAL, Rasterio, or GDAL to execute science.

## Root cause

The real Polygon click failed in `PyForestScanAdapter._import_required` inside QGIS Python. An auto-mode branch returned from PBM selection when readiness was stale, then continued into the legacy local adapter path and attempted `pyforestscan.handlers` before a coordinator directory was created. Verification and execution therefore referred to different interpreters.

## Converged path

`Process LiDAR` performs `ProcessingEngineService.assert_ready_for(products)`, freezes a `ProcessingRuntimeToken`, and launches the managed Python through the shared environment builder. The coordinator and worker validate that token against their actual executable and runtime contract. Mismatch or drift stops before scientific work.

The runtime trace records launcher, coordinator, and worker identity in `diagnostics/execution_runtime_trace.json`. It includes process identity, executable, prefix/search paths, module locations, protocol, and contract hash.

## Failure behavior

QGIS-local scientific imports are blocked by `ScientificRuntimeBoundary`. Missing dependencies are classified as `ENGINE_DEPENDENCY_MISSING`; token or contract drift is `ENGINE_RUNTIME_CHANGED`. Normal UI text directs the user to repair the Processing Engine while technical diagnostics retain the missing module and runtime identity.

## UI ownership

`ProcessingEngineStateModel` is the common state projection. Setup success performs verification immediately. The normal card and footer use Processing Engine terminology; technical PBM/backend details remain troubleshooting information.
