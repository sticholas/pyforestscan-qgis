# Phase 30D Pipeline Validation Audit

## Real LAS diagnosis

The `ohia_01_5m_norm.las` pattern reached all validation stages but never reached valid completion. `UNKNOWN_CRS` and `NO_VEGETATION_CLASSES` were warnings. Separate CHM and Rumple execution functions then converted the missing CRS into `FAILED`, and `JobManager` collapsed both failures into `One or more pipeline validation stages failed.`

| Stage | Input | Output | Blocking rule | Override | Caller |
|---|---|---|---|---|---|
| Dataset | source path | pass/fail | unreadable source blocks | none | Pipeline |
| Environment | immutable plan | pass/fail | malformed/executed plan blocks | none | Pipeline |
| CRS | report CRS | warning or pass | standalone science does not block | none | `validate_crs_step` |
| Ground/feasibility | report and product plan | warning/pass/fail | only missing required height data blocks | none | `ground_check_step` |
| Science | product request | output/failure | adapter or output failure blocks | none | product execution step |
| Export | artifact | pass/fail | missing requested artifact blocks | none | Pipeline |

CHM and Rumple do not require ASPRS vegetation classes 3/4/5 when usable height-above-ground data is present. Classification absence remains informative. A standalone source with unknown CRS may be processed in source XY coordinates and the output remains undefined; polygon alignment or reprojection still requires an authoritative CRS. No EPSG is guessed.

Pipeline serialization now records stage status plus product-level severity, blockers, warnings, information, and required actions. Blocking summaries name the product, reason, and recovery action.
