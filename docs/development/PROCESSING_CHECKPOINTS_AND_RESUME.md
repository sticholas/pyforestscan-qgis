# Processing checkpoints and resume

Each work unit stores status, output path, checksum, attempt count, runtime, metrics, and plan signature beneath `work_units/<id>/`. Reuse requires matching signature plus an existing file with the recorded checksum.

Completed units survive transient failure and restart. Resume skips valid units; retry executes failed or invalid units. A product with missing required units remains failed.
