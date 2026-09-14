# Output identity and isolation

Every run has a job ID and every retry has a fresh attempt ID, plus project/session, repository hash, polygon hash/source/features, plan signature, products, output root, and creation time. Automatic loading consumes only valid, complete, final registry records emitted for that exact attempt. It never scans an output tree for TIFF files.

Outputs require an identity sidecar (and raster tags where supported) before reuse. Existing files are reusable only when identity and plan metadata match. A failed attempt with zero registered outputs loads nothing; older layers may remain in QGIS but are not presented as current-run results.
## Work-unit outputs
Buffered and core tiles are attempt-scoped intermediates. Only the verified, complete, exactly masked final mosaic may be registered or loaded.

## Scientific identity

Core identity includes HAG method and grid signatures. Existing-HAG and Delaunay outputs cannot be mixed silently.


## Phase 28G Exact Polygon Completion

Sparse core files are internal checkpoints. Results and QGIS loading continue to expose only the verified final current-job raster.
