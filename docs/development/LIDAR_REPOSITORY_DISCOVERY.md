# LiDAR Repository Discovery

Phase 27O introduces one authoritative discovery service for Polygon Area Processing: `LidarRepositoryDiscoveryService`.

Discovery is intentionally separate from header scanning. It answers whether the selected folder contains supported logical LiDAR sources before a catalog build, update, repair, or polygon preflight is attempted.

## Supported Sources

- `.las`
- `.laz`
- `.copc`
- `.copc.laz`
- logical EPT roots represented by `ept.json`

EPT internals such as `ept-data` node files are ignored. A repository should not be reported as usable unless discovery finds at least one supported logical source or an existing catalog passes integrity validation with usable spatial records.

## Discovery Report

`RepositoryDiscoveryReport` records selected and normalized roots, readability, recursive scan mode, folders scanned, files examined, extension counts, unsupported files, ignored files, inaccessible files, duplicate logical paths, discovered paths, elapsed time, warnings, and errors.

The guided Polygon workflow uses this report to recommend one next action: choose a readable folder, build a catalog, repair a catalog, or continue when the repository is ready.

## Phase 27P Notes

Catalog health now separates embedded CRS from effective CRS. A bounded LAS/LAZ catalog with all source CRS values missing is `CRS Assignment Required`, not healthy, and polygon preflight does not report true no coverage until comparable CRS metadata exists. Repository CRS override metadata is explicit and reversible. Live QGIS coverage/zoom services now require actual layer insertion or canvas extent changes before reporting success.
