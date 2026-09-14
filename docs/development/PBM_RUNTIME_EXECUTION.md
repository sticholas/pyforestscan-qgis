# PBM Runtime Execution

Managed processing runs in the user-local PBM Python environment, not QGIS Python. Phase 28E-Stabilization removes inherited QGIS, Qt, GRASS, OSGeo4W, GDAL, and PROJ runtime paths from worker processes, restores backend-local geospatial data paths, and evaluates process exit status independently from stderr.

EPT CHM uses one safe-mode worker while native stability is validated. A worker access violation is classified as `NATIVE_BACKEND_CRASH`, generates parent-owned diagnostics, and stops the queue without discarding completed checkpoints. Use `inspect_native_runtime` to report DLL candidates and QGIS contamination before controlled live testing.
