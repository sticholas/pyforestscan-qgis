# Terminal UI State Machine

`ProcessingUiState` is the authoritative Mission Control processing projection: `IDLE`, `VALIDATING`, `STARTING`, `RUNNING`, `PAUSED`, `FINALIZING`, `COMPLETE`, `FAILED`, `CANCELLED`, `INTERRUPTED`, or `RECOVERABLE`.

Only active states disable repository, polygon, product, output, and profile controls. Every terminal state enables normal new-run controls and hides/disables pause and cancel. Durable backend state is authoritative; Qt state is only its projection.

Worker completion and failure handlers restore the terminal projection in `finally`, before post-job convenience failures can strand the UI. Summary rendering, signal consumers, QGIS layer loading, and renderer refresh do not define scientific completion.

A lightweight watchdog reconciles an active-looking UI when no current worker exists. `Refresh Status` performs the same non-destructive projection repair and appears only for interrupted or recoverable states. It never deletes data or cancels a worker.

Terminal pathways covered by the policy include success, warnings, primary failure, secondary failure, mask failure, registration recovery, visualization failure, coordinator/worker failure, cancellation, interruption, stale callback, and observer exceptions.
