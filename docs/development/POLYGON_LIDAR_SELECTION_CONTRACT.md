# Polygon LiDAR Selection Contract

Phase 27Q restores the ordinary folder selection contract for Polygon Area Processing.

For local LAS, LAZ, and COPC folders, the authoritative correctness rule is simple:

1. Discover supported point-cloud files under the selected repository.
2. Read each public header for bounds, point count, size, and embedded CRS when available.
3. Establish an effective source CRS from embedded metadata or an explicit repository CRS override.
4. Compare source bounds and polygon bounds only when the CRSs are known to match.
5. Select every source whose 2D bounds overlap or touch the polygon envelope.
6. Return real source file paths to the polygon clipping and Batch execution plan.

The overlap equation is:

```text
source.xmax >= polygon.xmin
source.xmin <= polygon.xmax
source.ymax >= polygon.ymin
source.ymin <= polygon.ymax
```

Catalogs remain the fast path for large repositories, but a catalog returning zero rows is not by itself proof of no coverage. In automatic mode, a direct header scan now acts as a correctness fallback for ordinary local folders when catalog selection is missing or inconclusive.

## Selection Modes

- `automatic`: use catalog selection when available, compare with direct header scan for ordinary local repositories, and use direct results when the catalog finds no files but direct headers find overlapping files.
- `catalog`: use the catalog/index path only. This is useful when validating catalog behavior or avoiding a slow direct scan.
- `direct_header_scan`: bypass the catalog and scan source headers directly. This is slower on large repositories but is the reference path for real file selection.

EPT repositories keep their native logical-source path. Direct header scan does not recurse into EPT internals or treat EPT node files as ordinary LAS/LAZ tiles.

## CRS Requirements

Direct selection is intentionally conservative. If source headers have no CRS, a repository CRS override must be supplied before bounds can be compared. The selector does not silently assume the project CRS or polygon CRS for unknown LiDAR metadata.

When CRS metadata is missing, users should either assign a repository CRS through Mission Control catalog integrity controls or pass a repository CRS to the diagnostic script for a read-only audit.

## Regression Boundary

The direct folder contract was first introduced for polygon processing in Phase 27D and was Batch-integrated in Phase 27F. Phase 27G introduced the SQLite/RTree catalog fast path, after which ordinary folder selection could become catalog-only. Phase 27Q restores the Phase 27D/27F direct overlap contract as a fallback and diagnostic reference while keeping the Phase 27G+ catalog path for performance.
