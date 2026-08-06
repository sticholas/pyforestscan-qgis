# Crash-Safe Work Scheduler

Each work unit is transactionally persisted as `Pending`, `Starting`, `Running`, then terminal. Terminal state is written before another unit is launched. The checkpoint contains the plan signature, work-unit definition, attempt, timestamps, output checksum, and error details.

Restart reconciliation marks `Starting` without a PID as interrupted-before-launch and `Running` with a dead or mismatched worker as interrupted. Completed outputs are adopted only when signature, file, and checksum agree. Empty directories are not evidence of a valid attempt. Full reattachment and command-line PID identity validation remain follow-up work.

## Atomic state

State uses unique temporary names, flush and fsync, parse validation, atomic replacement, and bounded retry.
