# Polygon Source Selection

Phase 27N makes repository identity independent from polygon geometry. A selected EPT root, `ept.json`, or EPT internal folder resolves once to one logical EPT dataset. Later polygon changes can affect overlap, but they cannot turn that repository into a generic catalog workflow.

## Models

- `ResolvedLidarRepository`: selected path, normalized path, repository kind, logical sources, EPT metadata path, source CRS, source extent, detection method, warnings, and errors.
- `SpatialEnvelope`: bounds plus CRS. Envelope comparisons raise when CRSs differ.
- `PolygonSourceSelectionResult`: selected sources, rejected sources, transformed envelope, source extent, overlap result, warnings, blockers, timings, and workload estimate.
- `RejectedSource`: path, source kind, rejection code, user reason, technical reason, CRS, extents, and details.

## Native EPT Rule

For EPT, preflight reads `ept.json`, derives the root CRS and extent, normalizes the polygon, and selects exactly one logical `ept.json` source when the transformed polygon envelope overlaps the EPT extent. It does not require an RTree catalog query to rediscover the known EPT source.

Unknown or mismatched CRS is a blocker unless the polygon has already been transformed to the source CRS by the QGIS normalization layer.

## No-Coverage Experience

Outside polygons keep the repository identity as EPT and report no LiDAR coverage. Diagnostics include polygon extent, repository extent, comparison CRS, overlap status, and rejected-source reason codes.
