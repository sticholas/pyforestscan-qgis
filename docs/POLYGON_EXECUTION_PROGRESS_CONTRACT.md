# Polygon Execution Progress Contract

Polygon progress distinguishes datasets, products, work units, transitions, and heartbeats.

- Dataset completion is derived from `SUCCEEDED`, `FAILED`, `CANCELLED`, or `SKIPPED` states.
- Product completion is derived independently from product terminal states.
- Work-unit counts are shown only when a planner supplies a measurable total.
- A `*_STARTED` transition is emitted once. Heartbeats carry `event_type=HEARTBEAT` and `active_stage`.
- Consumers ignore stage events whose sequence is not newer. Heartbeats use a separate heartbeat sequence.
- One visible dataset record is keyed by attempt and source identity and updated in place.
- Preparation is indeterminate unless measurable bytes, points, or work units are available. `100%` is terminal only.

Progress snapshots are atomically replaced. Launch history retains transitions in a bounded 256-entry list; its current heartbeat is stored separately.
