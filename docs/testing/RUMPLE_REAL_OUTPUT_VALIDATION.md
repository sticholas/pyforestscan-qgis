# Rumple Real Output Validation

Use `python scripts/validate_rumple_output.py RUMPLE.tif --summary rumple_summary.csv` and optionally `--chm CHM.tif` in the PBM environment. The report covers opening, bands, dtype, CRS, transform, bounds, resolution, dimensions, NoData, tags, statistics, values below one, scalar agreement, and the CHM half-cell relationship.

For the redacted 130 ha run, structural checks passed and no values were below one. The original scalar used pre-mask support and differed from the final exact-mask raster by about 0.156%. Phase 30B finalization makes support explicit and writes the published scalar from the final masked raster.

Visual appearance is useful QA but is not scientific validation. Polygon holes, multipart edges, concavity, diagonal edges, and coverage gaps require numeric mask checks in a live QGIS validation environment.
