# Automatic CRS Resolution

Automatic preparation does not weaken CRS policy. A standalone source may remain CRS-undefined, but distance-based preparation requires separate trusted unit evidence. Polygon/reprojection still requires a resolved CRS.

Missing CRS is serialized as explicit `source_local` mode with JSON `null`, never the string `"None"`. Source-local mode is not a CRS assignment and remains invalid for polygon alignment.

`SpatialReferenceResolver` applies evidence in strict order: embedded LAS/LAZ/COPC/EPT metadata, exact file sidecar, persisted file assignment, persisted repository assignment, high-confidence repository consensus, repository sidecar, and exact loaded-QGIS datasource assignment. Project/polygon context can suggest a CRS but cannot prove one by itself. Coordinate magnitudes never generate candidates.

Statuses are `RESOLVED_AUTHORITATIVE`, `RESOLVED_REPOSITORY_INHERITANCE`, `RESOLVED_USER_ASSIGNMENT`, `SOURCE_LOCAL_ONLY`, `AMBIGUOUS`, `CONFLICT`, and `INVALID`. Confidence is `AUTHORITATIVE`, `HIGH`, `MEDIUM`, `LOW`, or `NONE`.

Supported sidecars are exact-name `.prj` and `.wkt`, plus explicit `repository.prj`. Higher-confidence conflicts return `CONFLICT`; no majority is silently selected. Equivalent EPSG, WKT/WKT2, compound-horizontal, and PROJ representations normalize through `pyproj` where available.

QGIS evidence must match the canonical datasource path. Project CRS is only a confirmable suggestion unless reinforced by authoritative repository/source evidence. Once source and polygon CRS are known, existing exact-geometry transformation produces read-CRS bounds automatically.

Phase 31B adds typed units-only/file/repository assignments. Exact user assignments follow embedded/sidecar evidence and conflicts are surfaced. **Use Project CRS** is an explicit assignment confirmation, never an automatic inference.
