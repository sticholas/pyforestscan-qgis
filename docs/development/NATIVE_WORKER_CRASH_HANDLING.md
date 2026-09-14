# Native Worker Crash Handling

PBM exit status is evaluated independently of stderr. Windows `0xC0000005` is reported as `NATIVE_BACKEND_CRASH`; a preceding GDAL warning remains a warning. The parent writes `process_exit.json`, `terminal_event.json`, `command.json`, bounded stdout/stderr tails, heartbeat, PID, executable, and exception status because a crashed worker cannot be trusted to write diagnostics.

Native crashes are nonretryable in the same runtime. The queue stops and completed checkpoints remain available. Backend repair is not recommended unless backend verification separately fails.
