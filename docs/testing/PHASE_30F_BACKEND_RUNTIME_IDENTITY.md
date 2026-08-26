# Phase 30F Backend Runtime Identity

Run with managed backend Python:

```text
<backend-python> -m pyforestscan_qgis.backend_runner.run_processing_job inspect_runtime_contract
```

Required fields are `protocol_version`, `backend_api_version`, `runner_sha256`, `plugin_version`, `python_executable`, `python_version`, `versions`, and `module_locations`. Protocol must be `2` for Phase 30F source-local requests.

The command is read-only. A protocol mismatch must stop before PDAL reading or product calculation and direct the user to Repair Backend.

Observed on 2026-08-25: managed Python 3.12.13, PDAL 3.4.5, Rasterio 1.4.2, protocol 2, plugin 0.1.0-beta.3. The runner, adapter, and pipeline resolved to the current repository checkout; scientific dependencies resolved to the PBM environment. A GDAL data warning appeared only because this standalone diagnostic invocation did not use the plugin's normal backend data-path environment builder.
