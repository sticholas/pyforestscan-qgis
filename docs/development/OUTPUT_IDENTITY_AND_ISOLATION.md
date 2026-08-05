# Output identity and isolation

Every run has a job ID and every retry has a fresh attempt ID, plus project/session, repository hash, polygon hash/source/features, plan signature, products, output root, and creation time. Automatic loading consumes only valid, complete, final registry records emitted for that exact attempt. It never scans an output tree for TIFF files.

Outputs require an identity sidecar (and raster tags where supported) before reuse. Existing files are reusable only when identity and plan metadata match. A failed attempt with zero registered outputs loads nothing; older layers may remain in QGIS but are not presented as current-run results.
