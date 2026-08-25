# Automatic Execution Policy

Mission Control owns source scheduling. One logical source uses one source worker. Multiple independent LAS/LAZ sources are eligible for bounded parallel execution with a default ceiling of five. The planner may reduce concurrency for memory, workload, storage, network, or source safety.

One EPT repository remains one logical source at this layer; its durable internal work-unit scheduler remains independent and adaptive. External Worker mode remains disabled. A Custom profile may expose only a maximum-worker ceiling, never a sequential/parallel mode selector.
