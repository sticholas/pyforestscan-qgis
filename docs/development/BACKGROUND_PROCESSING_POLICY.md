# Background Processing Policy

Heavy LiDAR science runs outside QGIS through the managed Processing Engine. QGIS owns interaction and main-thread layer loading; PBM coordinators own preparation, workers, checkpoints, and terminal results.

All production subprocess calls use direct argument arrays, captured or inherited streams as appropriate, and the centralized `hidden_subprocess_kwargs()` policy. On Windows this applies `CREATE_NO_WINDOW`, `STARTF_USESHOWWINDOW`, and `SW_HIDE` where available. `shell=True` is prohibited.

Terminal snapshots close heartbeat state with `active: false` and `stopped_at`. No writer may publish liveness after `complete`, `complete_with_warning`, `failed`, `scientific_blocker`, or `cancelled`.
