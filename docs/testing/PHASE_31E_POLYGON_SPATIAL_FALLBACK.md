# Phase 31E Polygon Spatial Fallback

The automated regression uses unreferenced Olaa-like LAS bounds and a 24.4 ha `EPSG:6635` polygon. Strong raw overlap produces:

- mode `ASSUMED_MATCHING_COORDINATE_SPACE`;
- effective CRS `EPSG:6635`;
- effective units metres;
- coordinates transformed `false`;
- one selected source;
- preflight ready for shared HAG/CHM/Rumple preparation.

Safety cases verify projected-versus-geographic coordinates do not fallback, strict policy reports a CRS requirement while retaining raw-overlap truth, and repository assignments survive catalog/cache churn and apply to descendants.

Coverage lives in `tests/test_phase31e_spatial_fallback.py`.
