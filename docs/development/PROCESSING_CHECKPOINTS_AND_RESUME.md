# Processing checkpoints and resume

Restart reconciliation distinguishes interrupted-before-launch, dead running workers, verified completed outputs, and pending work. A completed tile is reused only when job signature, file, and checksum agree.

Each work unit stores status, output path, checksum, attempt count, runtime, metrics, and plan signature beneath `work_units/<id>/`. Reuse requires matching signature plus an existing file with the recorded checksum.

Completed units survive transient failure and restart. Resume skips valid units; retry executes failed or invalid units. A product with missing required units remains failed.

## One logical job

Reuse is automatic and signature-based. Users are not asked for a starting unit.
