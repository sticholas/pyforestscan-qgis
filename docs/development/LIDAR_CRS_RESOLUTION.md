# LiDAR CRS Resolution

Phase 27P separates embedded CRS metadata from effective CRS metadata.

LAS/LAZ files may have valid bounds but no embedded CRS. Those records are not comparable with a polygon CRS until either embedded CRS is extracted or a user explicitly assigns a repository CRS override.

## States

- `Healthy`: bounded spatial records have embedded/effective CRS.
- `Healthy with validated repository CRS override`: missing embedded CRS is covered by an explicit catalog metadata override.
- `CRS Assignment Required`: bounded records exist, but none have a comparable effective CRS.
- `Incomplete`, `Needs Repair`, `Unusable`: structural or mixed-readiness states.

The plugin must not infer a repository CRS from the QGIS project or selected polygon. A QGIS CRS selector workflow is required for assignment.
