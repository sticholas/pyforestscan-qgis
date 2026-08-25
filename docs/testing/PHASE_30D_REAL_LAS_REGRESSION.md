# Phase 30D Real LAS Regression

Sanitized fixture: 58,017 conceptual LAS points, `HeightAboveGround`, classifications 1 and 2 only, no 3/4/5, and unknown CRS. Requested products are CHM and Rumple.

QGIS-free adapter regressions confirm both product pipelines reach scientific execution, produce requested artifacts, and finish `NEEDS_ATTENTION` because CRS remains unknown. Vegetation-class absence does not block. The existing HAG path is selected by the product contract; no Delaunay HAG requirement is introduced.

Live QGIS/PBM execution against the original file was not available in this environment and remains required before claiming real-raster equivalence.
