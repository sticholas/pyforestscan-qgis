# Folder and Polygon Processing Parity

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
