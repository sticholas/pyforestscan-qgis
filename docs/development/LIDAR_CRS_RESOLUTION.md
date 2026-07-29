# LiDAR CRS Resolution

Phase 27P separates embedded CRS metadata from effective CRS metadata.

LAS/LAZ files may have valid bounds but no embedded CRS. Those records are not comparable with a polygon CRS until either embedded CRS is extracted or a user explicitly assigns a repository CRS override.

## States

- `Healthy`: bounded spatial records have embedded/effective CRS.
- `Healthy with validated repository CRS override`: missing embedded CRS is covered by an explicit catalog metadata override.
- `CRS Assignment Required`: bounded records exist, but none have a comparable effective CRS.
- `Incomplete`, `Needs Repair`, `Unusable`: structural or mixed-readiness states.

The plugin must not infer a repository CRS from the QGIS project or selected polygon. A QGIS CRS selector workflow is required for assignment.

## Phase 27Q Notes

Polygon Area Processing can now compare the catalog path with Direct Header Scan for ordinary local LAS/LAZ/COPC repositories. Catalogs remain the performance path, but Direct Header Scan is the correctness fallback when catalog selection is missing or inconclusive. EPT keeps native logical-source handling. See [Polygon LiDAR Selection Contract](POLYGON_LIDAR_SELECTION_CONTRACT.md) for the developer contract and [Process LiDAR Folder by Polygon](../user-guide/polygon-folder-processing.md) for user-facing guidance.
