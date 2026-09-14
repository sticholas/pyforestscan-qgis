# Unified Spatial Processing Policy

Folder and Polygon Selection consume one `EffectiveSpatialContext`. Its modes are authoritative, user assigned, repository assigned, source-local assumed units, assumed matching coordinate space, unresolved, and conflict.

Precedence is embedded metadata, sidecar, file assignment, repository assignment, repository consensus, exact QGIS datasource assignment, polygon-coordinate fallback, source-local unit fallback, then unresolved.

Folder-only standalone CHM/Rumple may remain source-local with assumed metres. Polygon processing requires either trusted map-coordinate meaning or the controlled matching-coordinate-space assumption. Authoritative conflict always blocks.

Raw geometric overlap is independent from spatial permission. Reports distinguish raw coordinate overlap, alignment status, and final selection.
