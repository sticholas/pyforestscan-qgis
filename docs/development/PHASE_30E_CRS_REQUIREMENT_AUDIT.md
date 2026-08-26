# Phase 30E CRS Requirement Audit

CRS is not one universal scientific prerequisite. The audit distinguishes calculation, georeferencing, comparison, and transformation.

| Operation | Science | Georeferencing | Spatial comparison | Reprojection |
|---|---|---|---|---|
| LAS/LAZ/COPC header inspection | Optional | Metadata only | Optional | Optional |
| EPT bounded read | Optional for full source; required for cross-CRS bounds | Metadata | Required for polygon bounds | Required when polygon differs |
| Dataset Explorer | Optional | Reported when available | Optional | Optional |
| CHM | Source-local allowed with valid HAG | Named CRS optional | Required for polygon workflow | Required only if target differs |
| Rumple | Source-local allowed; derives from CHM | Named CRS optional | Required for polygon workflow | Required only if target differs |
| PAD/PAI/FHD/Canopy Cover | Source-local mathematics allowed | Named CRS optional | Required for polygon workflow | Required only if target differs |
| Point Density/Voxel Statistic/DTM | Source-local allowed when source units are meaningful | Named CRS optional | Required for cross-layer use | Required only if target differs |
| HAG with existing dimension | CRS optional | Optional | Required only for spatial clipping | Required only if requested |
| DTM-assisted/recomputed HAG | Inputs must align | Required for reliable alignment | Required | Required if systems differ |
| Exact polygon clipping/masking | Calculation follows aligned coordinates | Required | Required | Automatic when systems differ |
| Mosaicking | Inputs must share grid/CRS | Required | Required | Required for differing sources |
| QGIS raster loading | File may load unassigned | Required for map alignment | Required for overlays | Optional display transform |
| Advanced Toolbox | Product-specific | Operation-specific | Required for multi-source spatial tools | Required for transform tools |

## Assertion trace

Phase 30D removed pipeline-level CHM/Rumple CRS blockers. Phase 30E found the remaining fatal checks in `PyForestScanAdapter.create_chm` and `create_rumple`. PyForestScan 0.4.1 exposes `read_lidar(input_file, srs, ...)`; rather than pass a fake SRS, source-local execution now uses a PDAL reader with no `spatialreference` key. Existing `HeightAboveGround` is preserved. Raster output is written with no CRS and explicit source-local tags.

Polygon selection already transforms exact geometry through `crs_alignment`; it remains blocked when the source CRS is unresolved. EPT semantic parsing remains authoritative and is consumed by the unified resolver.
