# Point cloud selection contract

See [identity ADR](../adr/ADR_POINT_CLOUD_EDIT_IDENTITY.md).

Implemented: immutable source SHA256, source CRS, inclusive finite XYZ bounds,
original classification filter, explicit full-resolution addressing marker.
Wrong source/CRS, invalid bounds/classes and LOD-index addressing are rejected.

Not yet implemented: renderer previews, polygon/lasso/frustum geometry,
add/subtract/intersect combinations, full-resolution query resolution,
selection counts/statistics, edited-attribute snapshot membership and EPT
immutable-tree identity. Do not expose these as working controls yet.

A displayed count is a sample count until an authoritative background query
finishes. Never label an estimate as exact or silently omit unseen points.
