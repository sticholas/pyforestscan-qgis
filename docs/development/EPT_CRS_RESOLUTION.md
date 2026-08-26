# EPT CRS Resolution

Phase 27S centralizes EPT coordinate-system parsing in `pyforestscan_qgis.core.ept_spatial_reference`.

Resolution priority:

1. Valid WKT2/WKT from `ept.json`
2. Valid PROJJSON from `ept.json`
3. Valid authority plus horizontal code, for example `authority=EPSG` and `horizontal=6635` becomes `EPSG:6635`
4. PBM/PDAL metadata probe placeholder
5. User override

An authority string alone is not a CRS. Values such as `EPSG`, `EPSG:`, `:6635`, `UNKNOWN`, and empty strings are rejected with `INCOMPLETE_CRS_AUTHORITY` and must not enter comparison CRS, EPT bounds, or execution manifests.

The typed `ResolvedSpatialReference` result records the normalized CRS text, source, horizontal and vertical codes, raw SRS object, parser warnings, and parser errors. Technical details expose this evidence; Guided mode only reports whether spatial alignment is ready or whether the user must choose a LiDAR coordinate system.

Use `python3 scripts/inspect_ept_spatial_reference.py <path-to-ept.json>` for support diagnostics without reading point data.
# Phase 30E integration

EPT authority, WKT/WKT2, PROJJSON, compound-horizontal, and PDAL probe results feed the unified resolver as authoritative evidence. Existing semantic comparison and exact polygon transformation remain unchanged.
