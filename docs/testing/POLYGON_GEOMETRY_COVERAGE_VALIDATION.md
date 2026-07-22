# Polygon Geometry Coverage Validation

Phase 27N test coverage proves that polygon shape does not change repository identity.

## Automated Coverage

`tests/test_phase27n_polygon_source_selection.py` covers:

- rectangle
- rotated rectangle
- concave polygon
- multipart polygon with one outside and one inside component
- polygon with a hole
- polygon containing the source extent
- outside polygon
- CRS mismatch
- plan signature changes
- rejected 110-billion root estimate

## Manual Live Cases

Do not mark these passed unless run in live QGIS:

- working rectangle against the real EPT repository
- large irregular polygon against the same EPT repository
- outside-coverage polygon
- multipart polygon with one overlapping component
- polygon with hole and final masked raster NoData validation
