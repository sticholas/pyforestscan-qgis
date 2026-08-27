# ADR: Persistent Processing Service

**Status:** Deferred after architectural review.

PyForestScan will retain one hidden coordinator process per durable job for the current release path. This already isolates heavy science, supports checkpoints, and avoids introducing daemon lifecycle, upgrade, security, and stale-service risks before RC validation.

A user-local persistent service remains a future option when measured startup overhead, cross-job prepared-source reuse, task queuing, or cancellation justify it. Any service must remain local-only, capability-checked, lazily started, and managed by the plugin.
