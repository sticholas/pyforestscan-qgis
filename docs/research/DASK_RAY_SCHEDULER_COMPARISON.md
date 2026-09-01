# Dask and Ray Scheduler Comparison

| Capability | Current custom coordinator | Dask Distributed | Ray Core |
|---|---|---|---|
| Durable domain checkpoints | Native plugin contract | Application-defined | Application-defined |
| Resource admission | Basic | Worker resources and memory thresholds | Task/actor resources |
| Retry/worker death | Domain-aware | Futures retry; nanny restart | Task/actor fault tolerance |
| Locality | Manual ordering | Data-aware scheduling/work stealing | Locality-aware scheduling |
| Dashboard/state | Plugin artifacts/UI | Mature dashboard | Dashboard and State API |
| Worker recycling | Fresh child today | Worker lifetime/restart | Actor/task lifecycle |
| Windows packaging | Already proven | Additional scheduler stack | Windows support carries broader runtime footprint |
| Scientific integration | Direct, explicit | Wrapper tasks required | Wrapper tasks/actors required |

Dask provides configurable memory spill/pause/terminate behavior and worker lifetimes; its documentation also warns that work stealing can backfire when communication dominates. See [worker memory](https://distributed.dask.org/en/stable/worker-memory.html), [worker lifecycle/resources](https://distributed.dask.org/en/latest/worker.html), and [work stealing](https://distributed.dask.org/en/latest/work-stealing.html).

Ray provides resource-aware task/actor scheduling, tracing, dashboards, and fault tolerance; see [actors](https://docs.ray.io/en/latest/ray-core/actors.html) and [fault tolerance](https://docs.ray.io/en/latest/ray-core/fault-tolerance.html).

## Decision

**KEEP_CUSTOM** for 32O/32P. The measured bottlenecks are false stall semantics, process startup, sparse-envelope planning, and UNC locality. Replacing the scheduler would not remove those costs and would add a large packaging/runtime surface before data-locality primitives exist. Revisit a **HYBRID** adapter only after ReadBlock/ScienceBlock contracts and cache keys are stable and single-machine benchmarks show scheduling itself is limiting throughput.
