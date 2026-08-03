# Real EPT CRS Alignment Validation

Phase 27S adds a regression fixture for the observed clean-machine preflight:

- Polygon CRS: `EPSG:6635`
- Polygon bounds: X `197779-199103`, Y `2235470-2236500`
- EPT SRS: `authority=EPSG`, `horizontal=6635`
- EPT bounds: X `167757-318703`, Y `2092940-2243880`

Expected result:

- Resolved EPT CRS: `EPSG:6635`
- Spatial alignment: Ready
- Transformation required: No
- Overlap: Yes
- Logical source count: 1
- No `CRS_TRANSFORM_FAILED`
- No false `No LiDAR coverage` blocker

Manual live QGIS validation still needs to be run against the real EPT repository before claiming end-to-end processing success. The automated tests exercise parser, same-CRS selection, injected different-CRS transformation, malformed CRS messaging, and true non-overlap messaging without user-specific paths.
