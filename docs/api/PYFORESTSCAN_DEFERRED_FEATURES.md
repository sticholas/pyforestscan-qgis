# PyForestScan Deferred Features

Phase 20D does not claim unsupported workflows as implemented. This document records every public PyForestScan capability that remains deferred or intentionally not exposed in the Advanced Toolbox.

| Feature | Source function(s) | Decision | Reason | Future path |
| --- | --- | --- | --- | --- |
| EPT tiled processing | `process.process_with_tiles` | Deferred | High-value but complex; needs QGIS-safe progress, cancellation, summaries, output naming, skip-existing controls, and careful EPT/DTM path validation. | Design a dedicated Advanced Large Data / Tiling algorithm after manual QA with small EPT fixtures. |
| Pipeline helpers | `pipeline._*` | Not exposed | Installed source marks them internal with leading underscores. | Use public `filters`, `handlers`, and `process` functions only. |
| Matplotlib visualizations | `plot_2d`, `plot_metric`, `plot_pad` | Deferred / not applicable | QGIS native point/raster rendering is the better primary interface. Matplotlib PNG export may be useful later but should not replace QGIS styling. | Add optional saved-figure tools only if users need publication PNG previews outside QGIS layouts. |
| Standalone CRS helpers | `simplify_crs`, `validate_crs` | Deferred | QGIS CRS widgets/provider APIs already validate CRS in context. | Add diagnostics only if users need a standalone CRS report. |
| Standalone extension validator | `validate_extensions` | Deferred | Adapter validates plugin-supported LAS/LAZ/COPC/EPT and output extensions; PyForestScan helper is narrower. | Keep adapter validation. |
| Standalone raster EPSG helper | `get_raster_epsg` | Deferred | QGIS raster providers expose CRS directly. | Add to Environment/Dataset diagnostics only if needed. |
| Standalone polygon loader | `load_polygon_from_file` | Deferred | QGIS vector-layer selection/index UX is needed to avoid brittle file-index behavior. | Implement product crop using QGIS layer/feature selection and adapter read options. |
| EPT utility SRS/bounds helpers | `utils.get_srs_from_ept`, `utils.get_bounds_from_ept` | Deferred | Dataset Explorer already inspects EPT metadata through plugin-owned paths. | Use only if adapter EPT inspection needs a stable public fallback. |
| LAS in-memory tiling | `utils.tile_las_in_memory` | Deferred | Potentially memory-heavy and overlaps batch/run-folder architecture. | Design as batch/tiling workflow with preflight and resume. |
| Product-level crop/bounds on every metric | `read_lidar(... bounds/crop_poly/poly ...)` | Partial | HAG/Normalize exposes low-level read options; product tools do not have a consistent crop UX. | Add crop controls once vector/bounds selection is designed across guided and advanced workflows. |
| Product-specific `create_geotiff(nodata)` controls | `create_geotiff(... nodata=-9999)` | Partial | Advanced DTM exposes NoData; product rasters keep stable defaults for now. | Expose per-product NoData only after output QA and styling tests. |
