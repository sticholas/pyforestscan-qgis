# Phase 31K Finalization Recovery

The real Olaa run contained eight required `Complete` statuses, one `SkippedOutsidePolygon`, and final CHM/Rumple artifacts. Its coordinator failed only while rebuilding the manifest because the QGIS-profile plugin copy lacked `core.adaptive_processing`.

Regression coverage recreates that exact state and requires recovery to produce `SCIENCE_COMPLETE_FINALIZATION_REPAIRED`, a terminal heartbeat with `active: false`, and an output registry without calling science.

Managed-runtime validation found:

- `chm.tif`: 737,376 bytes, EPSG:6635, 744 x 699, NoData -9999
- `rumple.tif`: 873,412 bytes, EPSG:6635, 743 x 698, NoData -9999
