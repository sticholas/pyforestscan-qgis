# PBM Native Runtime Isolation

Processing workers receive PBM environment paths first and remove inherited QGIS, QGIS Python, Qt, GRASS, OSGeo4W, GDAL, and PROJ paths and variables. QGIS-hosted certificate paths are removed; PBM-local GDAL/PROJ data paths are restored from the managed environment. This changes only the child process environment.

Run the managed command:

```text
python -m pyforestscan_qgis.backend_runner.run_processing_job inspect_native_runtime
```

The JSON report includes imports, package versions, DLL candidates, PATH policy, data paths, QGIS candidates, and a release-blocker flag. Live Windows output remains required before release readiness is claimed.
