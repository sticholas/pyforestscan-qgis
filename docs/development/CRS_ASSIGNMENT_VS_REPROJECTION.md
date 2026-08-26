# CRS Assignment vs Reprojection

**Assign CRS** attaches the meaning of existing coordinates; coordinate values do not change. PyForestScan stores assignments in plugin/repository metadata and passes them into processing. Source files are not rewritten.

**Reproject** transforms coordinate values from a known source CRS to a known target CRS. Reprojection cannot begin until source identification is authoritative or explicitly confirmed.

For an untagged LAS whose coordinates are already in the correct system, assignment is the appropriate recovery. Polygon geometry is then transformed automatically into the LiDAR read CRS when needed.
