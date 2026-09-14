# QGIS Spatial Actions

Phase 27P adds live-QGIS service boundaries for repository coverage and zoom actions.

Success requires the final QGIS side effect: a layer is added to `QgsProject`, or the map canvas receives `setExtent` and `refresh`.

Coverage and repository zoom actions are blocked when the repository effective CRS is unknown. Text-only model preparation is not reported as map success.
