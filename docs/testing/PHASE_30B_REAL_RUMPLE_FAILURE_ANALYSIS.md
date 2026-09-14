# Phase 30B Real Rumple Failure Analysis

## Evidence

The surviving 2026-08-25 EPT job was inspected in place. Paths and repository identity are redacted here. The job covered about 130 ha in EPSG:6635 and requested Rumple only.

Durable records show:

- PBM result: `success`, with no stderr, warnings, or error code.
- Primary raster write: succeeded.
- Exact polygon mask: succeeded; registry marks the raster masked and valid.
- Scalar CSV write: succeeded.
- Batch summary: one completed item, zero failures.
- Output registration: succeeded for the primary raster.
- Durable coordinator state: not applicable; the small Phase 30A path was monolithic.
- QGIS auto-load: not requested by the batch record.

The exact dialog error was not retained and cannot be reconstructed. No durable evidence supports describing this as a scientific or batch-processing failure. The most defensible diagnosis is a post-job UI/finalization exception: the old completion handler rendered summaries and emitted convenience signals before restoring controls. Any exception there could leave the workflow sections disabled even though the worker had terminated successfully.

## Raster Evidence

The one-band Float32 GeoTIFF opens successfully. It is 1324 by 1032 pixels in EPSG:6635 at 1 m resolution, with bounds `(197779.46, 2235468.97, 199103.46, 2236500.97)`, transform `(1, 0, 197779.46, 0, -1, 2236500.97)`, and NoData `-9999`.

Valid pixels: 1,299,973. NoData pixels: 66,395. Minimum: 1.0. Maximum: 10.6840973. Mean: 1.32838488. Median: 1.02955925. Percentiles 1/5/25/75/95/99: 1.0, 1.0, 1.01011801, 1.15568757, 3.13566170, 4.72016123. No values were below 1 within `1e-6`; one value exceeded 10.

The raster has the expected Rumple description and method metadata. The job result reported the pre-mask scalar `1.33045444095` over 1,364,567 patches. The final masked raster mean is `1.32838487625`, absolute difference `0.00206956470`, relative difference about `0.001558`. Phase 30A proved equality before masking; this live difference comes from using different support areas. Phase 30B now derives the published scalar from the final exact-mask support.

## Conclusions

Scientific calculation, raster writing, masking, scalar writing, and registration all succeeded. The final raster is structurally and numerically plausible. The original dialog is unrecoverable. The UI lock was enabled by non-guaranteed cleanup ordering, now replaced by finally-guarded terminal projection and watchdog reconciliation.
