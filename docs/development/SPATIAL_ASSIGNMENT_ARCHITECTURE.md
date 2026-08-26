# Spatial Assignment Architecture

Phase 31B separates coordinate meaning from coordinate transformation. `SpatialAssignment` is the authoritative typed record for explicit file or repository evidence. It can carry a horizontal/vertical CRS, trusted `LinearUnit`, fingerprints, scope, provenance, confidence, confirmation, timestamp, and notes.

## Evidence order

1. Embedded authoritative CRS
2. Exact sidecar
3. Exact file assignment
4. Exact repository assignment
5. High-confidence repository consensus
6. Exact loaded QGIS datasource assignment
7. Trusted units-only assignment
8. Source-local unresolved

Conflicting authoritative/high-confidence CRS evidence produces `CONFLICT`; it is never silently overridden. Assignment changes metadata interpretation only. Reprojection remains a separate coordinate transformation.

## Runtime profile

`LidarSpatialProfile` reports effective CRS, trusted units, assignment scope, evidence, standalone-preparation safety, polygon-alignment safety, and conflicts. Units-only evidence can authorize source-local distance operations. It cannot authorize polygon alignment.

Persistence is user-local at the PBM root in `spatial_assignments.json`. File fingerprints and repository inventory fingerprints invalidate stale records after material source changes. Original LAS/LAZ bytes are never modified.

Previously source-local rasters may be copied and registered with a later confirmed CRS through `register_raster_crs_copy`; pixels and transform remain unchanged and the original is preserved.
