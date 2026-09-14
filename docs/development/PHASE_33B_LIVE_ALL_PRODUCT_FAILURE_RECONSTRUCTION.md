# Phase 33B Live All-Product Failure Reconstruction

## Scope

This reconstruction uses the durable files for attempt
`20260904T162216975004Z-f07e9594`; it does not infer missing events.
The request covered about 64.3 ha of the `ept-full/ept.json` source in
`EPSG:6635` and requested CHM, DTM, PAD, PAI, FHD, Canopy Cover,
Rumple, and Point Density.

## Timeline

| UTC | Durable event |
| --- | --- |
| 16:22:16.975 | Process was clicked and the attempt was created. Runtime-token and dispatch validation passed. |
| 16:22:17 | PBM began the bounded CHM request. |
| 16:23:04 | `outputs/chm.tif` became durable (19,204,234 bytes). |
| 16:23:05 | CHM returned successfully and DTM started. |
| 16:23:22 | DTM wrote its traceback and failed result. |
| 16:23:23 | The DTM backend process returned exit code 1. Remaining products were never submitted. |
| 16:23:23 | The Qt worker returned a `BatchResult`, then incorrectly wrote attempt stage/outcome `COMPLETED`. The batch summary simultaneously recorded zero completed datasets, one failed dataset, and one output. |

The successful CHM was present, but `output_registry_path` was null because
registration required the containing item to be wholly completed.

## DTM Root Cause

The installed PyForestScan 0.4.1 implementation of
`calculate.generate_dtm(ground_points, resolution)` iterates a **list of
structured arrays**:

`for array in ground_points for pt in array`

`filters.filter_select_ground()` correctly returned that list. The plugin
then called `_merge_point_cloud_arrays()` and passed one structured NumPy
array instead. PyForestScan consequently treated each structured scalar as an
array and eventually evaluated `pt['X']` on a numeric scalar, raising:

`IndexError: invalid index to scalar variable`

The exact throw site was installed
`pyforestscan/calculate.py:26`, reached from
`pyforestscan_qgis/core/adapter.py:919`. The Processing Engine contract was
valid throughout. This is `PRODUCT_EXECUTION_FAILED`, not an engine repair
condition.

Existing unit coverage used a fake `generate_dtm` that accepted any object
and never asserted the list-of-arrays contract. Phase 33B now asserts it.

## Corrective Replay

The captured request was replayed with the managed Windows Python, the same
EPT source, bounds, polygon, CRS, and 1 m resolution. The corrected adapter
completed successfully:

- output: `dtm-phase33b.tif`
- CRS: EPSG:6635
- grid: 2074 by 1156
- terrain range: 417.81 to 519.31
- finite coverage: 26.53 percent
- extent: X 211775.31–213849.31; Y 2207749.13–2208904.94

This validates the DTM contract repair against the actual bounded source.

## State And Recovery Repair

Logical polygon execution now records one terminal result per requested
product: `SUCCEEDED`, `FAILED`, `NO_DATA`, `CANCELLED`, or
`SKIPPED_DEPENDENCY_FAILED`. The eight release products currently execute as
independent public PyForestScan requests; shared calculations do not create
durable output dependencies. With continue-on-error enabled, a DTM failure
therefore does not prevent later products.

Attempt outcome is derived from `BatchResult.scientific_outcome`, not normal
worker return:

- all products succeeded: `SUCCEEDED`
- some succeeded: `PARTIAL_SUCCESS`
- none succeeded and failures exist: `FAILED`
- cancelled: `CANCELLED`

Successful partial outputs are registered and may be loaded. Product failures
write bounded diagnostics (types, parameters, function, exception, traceback;
never arrays), a human `error_report.html`, and
`technical_diagnostics.zip`.

## Remaining Live Gate

The exact DTM replay passed outside QGIS. A fresh installed-ZIP QGIS run of all
eight products, partial-failure injection, automatic loading, and screenshots
remains required before the Phase 33A all-product RC blocker can be closed.
This document does not claim those unperformed checks.
