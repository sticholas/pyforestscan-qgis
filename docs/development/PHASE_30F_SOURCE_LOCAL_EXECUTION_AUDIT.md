# Phase 30F Source-Local Execution Audit

Phase 30F traced unknown-CRS standalone LAS processing through Dataset Explorer, pipeline context, PBM JSON, backend deserialization, PDAL arrays, CHM/Rumple calculation, writers, and result presentation.

## Root causes

1. `BackendJobSpec` converted a missing CRS with `str(None)`. Rumple later passed the truthy string `"None"` to Rasterio's `crs` profile field, which raised `Could not import coordinate system 'None'`.
2. The frontend's existing-HAG observation was represented only by an adapter default. Standard PBM jobs did not independently inspect the execution array, and source-local CHM rejected the stale Delaunay default before reading the LAS.
3. PBM launches backend Python with the current plugin parent as its working directory. Runtime identity was implicit, so version skew could not be distinguished from a scientific failure.

## Repair

PBM protocol 2 carries explicit `spatial_reference` and `height_normalization` objects. The backend canonicalizes absent CRS values to JSON `null`, verifies protocol compatibility before science, records module locations, and validates expected HAG against the actual PDAL structured array. Source-local readers retain all dimensions. Supported HAG aliases are canonicalized without dropping unrelated fields.

Source-local raster writers omit CRS metadata and identify source-coordinate output explicitly. Polygon alignment remains prohibited without a resolved CRS.

## Evidence

Each source-local job writes `diagnostics/source_local_trace.json` and `diagnostics/backend_module_locations.json`. See [the regression procedure](../testing/PHASE_30F_PBM_SOURCE_LOCAL_REGRESSION.md).

