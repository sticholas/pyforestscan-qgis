# Rumple Product Finalization

Rumple output roles are explicit:

- Primary: exact-mask spatial Rumple GeoTIFF.
- Secondary: scalar summary CSV.
- Supporting: CHM when CHM was not requested.
- Intermediate: buffered CHM and Rumple work-unit rasters.
- Diagnostic: requests, checkpoints, statistics, errors, and coordinator snapshots.

A valid primary raster and mask are required. Secondary CSV or QGIS auto-load failure yields success with warning. Registration failure after a verified primary is recoverable and must not trigger scientific recomputation. Mask or primary-raster failure is a product failure. Supporting CHM is published only when CHM was requested.

Recovery verifies current-job identity, grid signature, checksum, method, and mask before registration. Scalar recovery may read the verified final raster or combine persisted non-overlapping core totals; it does not reread LiDAR.
