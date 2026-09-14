# Phase 28G Live Completion Validation

## Artifact

- Starting implementation commit: `d58717c`
- Automated sanitized fixture: Passed
- Interactive QGIS 3.44.9 completion run: Not tested live

## Stage A: Planning

Status: **Not tested live**. Confirm the real irregular polygon reports 120 candidates, 116 required areas, and four geometry-excluded areas including the previously observed bounds for units 76 and 91-93.

## Stage B: Reconciliation

Status: **Not tested live**. Confirm 89 checksum-compatible completed cores are adopted, outside-polygon failures are reclassified from geometry, and no starting-unit prompt appears.

## Stage C: Continuation

Status: **Not tested live**. Confirm only remaining required areas launch, durable progress never resets completed counts, and skipped/valid-NoData states do not trigger the breaker.

## Stage D: Finalization

Status: **Not tested live**. Confirm sparse aligned mosaic creation, exact mask including holes, raster verification, and one final registered CHM.

## Stage E: QGIS Loading

Status: **Not tested live**. Confirm Results identifies only the current final CHM and Load into QGIS loads that raster with current styling.

Do not promote the live completion gate until all five stages have recorded machine, QGIS version, artifact SHA256, evidence, and pass/fail results.
