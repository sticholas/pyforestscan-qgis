# Phase 30E Unknown LAS Regression

The sanitized `ohia_01_5m_norm.las` pattern contains 58,017 conceptual points, projected-looking X/Y values, `HeightAboveGround`, classes 1/2, no CRS, and no polygon.

Expected and automated result: no coordinate-based EPSG guess; resolution is `SOURCE_LOCAL_ONLY`; CHM and Rumple reach adapter science; CHM uses existing HAG; outputs retain blank CRS. The source-local writer test verifies an unassigned GeoTIFF and explicit provenance tags. The polygon variant blocks with a concise assignment action because source-local coordinates cannot be aligned safely.

The original file was not available to the WSL test runtime, so real PBM raster values and live QGIS loading remain manual validation items.
