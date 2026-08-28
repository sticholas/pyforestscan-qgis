# Polygon Cancellation Contract

`Cancel Processing` applies to current work, not only queued datasets.

The request travels from Mission Control to the Qt orchestration worker, the durable coordinator cancel file, and the active preparation child. The coordinator first requests a normal stop; for opaque preparation it terminates only its positively owned child process tree after the request is observed. Partial prepared output is removed, science does not start, terminal state becomes `CANCELLED`, and the coordinator heartbeat stops.

Mid-operation pause is not claimed. `Pause After Current Step` permits the current non-pausable preparation operation to finish, then blocks product execution until Resume. A cancellation request takes precedence over pause.
