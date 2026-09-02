# Phase 32R Market Comparison

Reviewed 2026-09-02 from the public
[`AkmaulHoque/world_lidar_feature_collector`](https://github.com/AkmaulHoque/world_lidar_feature_collector)
repository. This is a product and interaction review only. No competitor code,
layout, names, formulas, thresholds, or scientific implementation were copied.

## Comparison

| Area | PyForestScan QGIS | LiDAR AutoVector Studio |
| --- | --- | --- |
| Scientific foundation | Official PyForestScan forest-structure calculations behind an adapter boundary. | QGIS Processing/PDAL-derived surfaces and heuristic candidate vector extraction. |
| Inputs | LAS, LAZ, native COPC, and local/network EPT infrastructure. | README states LAS, LAZ, COPC, and EPT support. |
| Runtime | User-local, isolated, verified Processing Engine. No OSGeo4W setup is required for routed products after successful setup. | Requires QGIS GDAL Python utilities and PDAL available in QGIS/OSGeo4W. |
| Large work | Polygon subdivision, source-bounded reads, durable job identity, checkpoints/resume, adaptive isolated workers, and exact finalization. | Uses registered QGIS Processing PDAL algorithms; public README does not claim equivalent checkpoint/resume architecture. |
| Products | Forest structure products including CHM, PAD, PAI, FHD, canopy cover, Rumple, DTM, density, and voxel statistics where routed/supported. | DTM, DSM, CHM, density, roughness, slope, plus separate candidate-class GeoPackage layers. |
| Candidate classes | Not part of the current release candidate. Future derived/candidate layers must be scientifically framed and provenance-labelled. | Buildings, settlements, vegetation, low vegetation, cropland, bare land, roads, water, and elevated linear candidates. README explicitly requires imagery validation. |
| Output organization | Final scientific products and provenance are user-facing; managed job state, cache, and checkpoints remain internal. | Separate raster and GeoPackage outputs provide a direct deliverable story. |
| Progress/recovery | Region progress, elapsed time, ETA, health, checkpoints, resume, and isolated-worker diagnostics. | Public materials describe the processing route but do not document comparable durable recovery evidence. |
| Installation | Plugin ZIP plus one-click managed Processing Engine setup on supported Windows beta builds. | Plugin plus compatible QGIS/OSGeo4W dependencies. |
| UI density | Phase 32R reduces the normal polygon path to source, area, products, output, Prerun, Process, and results. | Public positioning is concise and output-led; detailed live width/height behavior was not independently validated. |
| Release maturity | Internal beta with extensive automated gates and targeted real QGIS/PBM evidence; remaining RC blockers are tracked explicitly. | Public repository identifies version 0.6.1; this review does not infer test coverage beyond published evidence. |

## What We Should Learn

- Use plain derived-product language and make final outputs easy to locate.
- Keep source, area, products, and destination visibly close together.
- Distinguish measured/derived scientific products from candidate classifications.
- State validation limits directly. Candidate classifications should never be
  presented as authoritative land-cover truth without imagery or field review.
- Present dependency readiness as one understandable state.

## What We Should Not Copy

- Scientific formulas, thresholds, candidate-class rules, naming, code, or layout.
- A runtime model that requires users to configure QGIS/OSGeo4W when the managed
  Processing Engine can provide an isolated and verifiable path.
- Candidate feature extraction merely to expand the release feature count.

## PyForestScan QGIS Release Identity

Validated differentiators are the PyForestScan scientific foundation, isolated
managed Processing Engine, automatic setup on the tested Windows path,
LAS/LAZ/COPC/EPT infrastructure, large-area polygon execution, exact polygon
finalization, durable job identity, adaptive process isolation, checkpoint/resume,
CRS safeguards, and local provenance. Future forest-specific products remain a
direction, not a current release claim.

