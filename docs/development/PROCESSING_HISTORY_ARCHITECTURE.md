# Processing History Architecture

Processing history is a small local registry, never an output-directory scan. Each entry records job and attempt identity, date, source, mode, products, terminal status, elapsed time, and final outputs.

`core.processing_history` provides bounded append/read operations and deduplicates only the same job/attempt pair. A future Re-run action must create a new attempt identity from stored settings rather than revive stale output state.
