# Adaptive Processing Planner Audit

## Removed job-sensitive behavior

- Fixed 1,000 m EPT core width: replaced by point/memory/raster-derived width.
- Network/conservative 750 m and dense-source 500 m widths: replaced by derived scale and storage-aware concurrency.
- Hard-coded 8 GiB polygon planner input: replaced by detected available memory with an 8 GiB fallback.
- Exact large-case count assertion: replaced by scale and boundedness invariants.

No production constant targeted 88, 116, or 120 units. The number 88 in catalog progress is a progress percentage, not work planning.

## Retained and classified constants

| Constant | Classification | Reason |
| --- | --- | --- |
| 50-unit CHM read buffer | Scientific/implementation default | Preserves neighborhood context before core extraction. |
| 22% available RAM per unit | Safety heuristic | Leaves room for QGIS, native libraries, and copies. |
| 55% RAM across concurrent units | Safety bound | Prevents aggregate worker oversubscription. |
| 3M points / 2.5M cells fast path | Performance heuristic | Avoids coordinator/mosaic overhead for demonstrably small requests. |
| 250-5,000 unit calibration bounds | Safety bounds | Prevents pathological pilot resizing. |
| max concurrency 4 | Native-runtime safety bound | Avoids unsafe “more workers is faster” assumptions. |
| network concurrency max 2 | Storage heuristic | Limits competing remote reads. |
| EPT concurrency 1 by default | Validated safety policy | Parallel EPT remains developer-gated. |
| two transient retries | Reliability default | Existing scheduler policy. |
| 180 second pilot target | Calibration heuristic | Balances restart granularity and setup overhead. |
| default densities 8/12/20 points per m2 | Low-confidence defaults | Used only when metadata/history is absent; pilot may replace them. |
| 1/2 GiB native grouping thresholds | Implementation defaults | Native source footprints still take precedence; oversized sources subdivide. |

These are safety/default inputs, not desired unit counts. Exact polygon filtering runs after candidate generation and removes zero-area cores.
