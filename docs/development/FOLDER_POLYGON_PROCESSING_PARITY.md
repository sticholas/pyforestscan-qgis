# Folder and Polygon Processing Parity

Folder and Polygon CHM/Rumple use the same `pbm_lidar_preparation` planner, PDAL methods, checkpoint rules, and prepared-request contract. Polygon adds a bounded support extent and coordinator dependency; it does not introduce a second scientific implementation.

Polygon CHM/Rumple requests freeze the managed runtime at Prerun and use it for coordinator launch. Standard Folder processing remains explicitly PBM-routed; immutable token persistence across its complete preflight request is still tracked as a post-31I parity improvement.

Folder and Polygon now use the same shared engine service, managed adapter mode, token authority, environment builder, and failure-before-job rule. Their only intentional difference is source selection/coordinator planning.

Both normal modes now assert the same managed runtime, use `build_processing_engine_environment()`, and record the same runtime token and identity trace. Neither mode may fall back to QGIS Python science. Polygon adds a durable coordinator boundary, which validates the same frozen token before scheduling work.

## Runtime parity

Folder and Polygon execution share the same managed Processing Engine contract. Neither workflow requires QGIS Python to import PyForestScan for PBM-owned science. Required imports, protocol compatibility, environment initialization, and executable identity are mode-independent; only source selection and polygon geometry differ.

Normal Mission Control Folder Batch and Polygon execution both force the verified managed adapter. They do not silently fall back to QGIS Python after a transient readiness failure.

Folder Selection and Polygon Selection are entry points into one processing system.

## Shared systems

- Product settings, output policy, automatic execution profile, PBM ownership, adaptive concurrency, checkpoints, recovery, current-run isolation, output registry, QGIS loading, and technical diagnostics.
- The spatial assignment store and effective source spatial profile.
- LiDAR preparation assessment, bounded ground inspection, existing-HAG reuse, class-2 Delaunay planning, SMRF fallback, and preparation quality checks.
- CHM and Rumple share prepared HAG and aligned CHM intermediates where their contracts permit it.

## Folder only

Standalone source-local processing may continue with unknown CRS when coordinate units are trusted or safely assumed by the source-local policy. Outputs retain source coordinates and an undefined CRS (`crs=None`).

## Polygon only

Polygon processing requires a real source CRS because LiDAR and polygon coordinates must be aligned. It transforms the exact polygon to source coordinates, selects overlapping sources, uses buffered preparation context, and applies the exact polygon mask to final rasters. Source-local CRS assumptions are forbidden.

Mode-specific controls are limited to polygon source, polygon selection, spatial assignment intervention, and exact-mask status. Scientific and execution controls remain shared.

Phase 31E permits a controlled polygon-coordinate interpretation when unreferenced LiDAR and polygon envelopes are strongly compatible. This remains distinct from folder source-local units: polygon outputs receive the polygon CRS with explicit assumed provenance and no coordinate transformation.
