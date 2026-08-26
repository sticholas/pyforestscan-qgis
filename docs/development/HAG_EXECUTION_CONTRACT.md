# HAG Execution Contract

`HeightNormalizationDecision` is the authoritative PBM height contract. Modes are `EXISTING_HAG`, `DELAUNAY_HAG`, `DTM_HAG`, `NO_HAG_REQUIRED`, and `UNAVAILABLE`.

For source-local CHM and Rumple, only `EXISTING_HAG` is accepted. The request records the expected source dimension and method signature. PBM then validates the decision against the dimensions returned by its own PDAL read. It never silently falls back to Delaunay or another scientific method.

`PointDimensionCapabilities` recognizes `HeightAboveGround` and the deliberately supported aliases `height_above_ground`, `HAG`, and `NormalizedHeight`. Aliases are copied to the canonical field name while all other structured-array fields are retained.

When inspection reported HAG but execution cannot find it, the job fails with `SOURCE_DIMENSION_MISMATCH`, including expected and observed dimensions.

## Polygon continuity

The Phase 28F `HagExecutionDecision` remains the bounded polygon suitability contract: it records method, exact dimension, evidence, reason, implementation version, timestamp, and deterministic signature. Existing-HAG polygon execution still requires finite, meaningful, nonconstant values and writes bounded-read/statistics diagnostics. Phase 30F maps that established decision into the PBM-wide `HeightNormalizationDecision`; it does not weaken polygon checks.
