# Guided Processing Workflow

Phase 27N introduces a reusable guided workflow model for Polygon Area Processing.

## Steps

1. Data: choose LiDAR data and resolve repository identity.
2. Area: choose or normalize a polygon area.
3. Outputs: choose products.
4. Settings: choose output folder and common quality settings.
5. Review: validate the execution plan.
6. Results: run, monitor progress, and load outputs.

The Batch page now shows a compact step indicator and a structured Polygon Processing Review before the raw technical report.

## Processing Profiles

Guided mode uses profiles instead of making users reason about worker topology:

- Conservative: lower concurrency for network storage and memory-sensitive work.
- Recommended: balanced default.
- Performance: higher concurrency for tested fast local storage.
- Custom: exposes detailed worker settings.

Specialist controls remain under Advanced Batch Options and Polygon Finalization.
