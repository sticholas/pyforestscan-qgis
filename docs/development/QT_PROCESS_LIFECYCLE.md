# Qt and Process Lifecycle

Source-aware execution uses one safe-mode worker and does not make Batch widgets owners of PBM results. Progress callbacks are observers. PBM execution closes temporary stdout/stderr files through context managers and records terminal state on the scheduler side.

The QGIS access-violation stack is not available, so a precise Qt defect is not claimed. Live validation must inspect signal disconnection, page destruction, plugin unload, timer counts, process handles, and callback targets. The QGIS-free 120-transition soak verifies bounded scheduler state but cannot prove QObject lifecycle behavior.

## Observer rule

Qt observers are optional durable-state readers and do not own scheduler correctness.
