# Assumed Coordinate-Space Alignment

Polygon processing may interpret unreferenced LiDAR as already expressed in the polygon CRS when all of these conditions hold:

- the polygon/project CRS is known;
- no embedded, sidecar, assignment, or repository evidence conflicts;
- raw source and polygon envelopes overlap strongly;
- coordinate scales and magnitudes are compatible;
- the centralized preference is `Automatic when coordinates are compatible`.

This is an assignment assumption, not CRS discovery and not reprojection. Coordinates remain unchanged. The effective CRS and units come from the polygon CRS, confidence is `ASSUMED`, and provenance is `polygon_coordinate_space_fallback`.

Outputs record embedded/effective CRS, basis, confidence, transformation status, polygon CRS, and whether fallback was used. Users can later promote the interpretation to a trusted repository assignment without changing source coordinates.
