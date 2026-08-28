# Polygon Input Preparation Observability

For ordinary LAS/LAZ polygon jobs, the preparation call chain is:

`generic_polygon_coordinator` -> `_prepare_polygon_input` -> `polygon_preparation_worker` -> `PyForestScanAdapter.normalize_heights` -> `pyforestscan.handlers.read_lidar(hag=True)` -> `pyforestscan.handlers.write_las`.

PyForestScan 0.1.x does not provide byte-level read progress for this operation. The UI therefore reports indeterminate progress, elapsed time, source size, child liveness, and output-size changes without inventing a percentage. `preparation_timing.json` records source and output bytes, bounds, polygon use, timestamps, elapsed time, reader/method, retained points, and child PID. Points or bytes that cannot be measured are recorded as null.

Successful preparation writes a product-independent `*.prepared.json` checkpoint. Reuse requires the same source path, size and modification time, polygon hash, bounds, CRS, method, and an artifact whose current size matches the checkpoint. PAI and FHD therefore share one prepared point-cloud artifact.
