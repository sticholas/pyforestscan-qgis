# Packaged Import Graph

`scripts/validate_packaged_import_graph.py` extracts the built ZIP into a clean temporary directory, indexes every packaged Python module, parses internal imports, and fails when a `pyforestscan_qgis.*` dependency cannot resolve.

The release gate explicitly requires `core.adaptive_processing`, `core.polygon_batch`, `backend_runner.job_coordinator`, and `backend_runner.polygon_job_coordinator`. This complements package-shape validation and catches incomplete installed/runtime payloads before release.

The Phase 31K incident was not caused by the current package builder: the source file and current ZIP both contain `adaptive_processing.py`. The coordinator traceback proves QGIS ran an incomplete or stale plugin copy from its profile plugin directory. Removing finalization replanning also removes that avoidable late import.
