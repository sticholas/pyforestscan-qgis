"""QGIS-free performance diagnostics for adaptive source-aware plans."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from time import perf_counter

@dataclass(frozen=True)
class PlanPerformanceSummary:
    planning_seconds: float
    strategy: str
    workload_category: str
    output_cells: int
    native_partitions: int
    candidate_units: int
    required_units: int
    skipped_units: int
    concurrency: int
    core_area: float
    buffered_read_area: float
    read_amplification: float
    maximum_unit_memory: int
    estimated_peak_memory: int
    startup_count: int
    execution_path: str
    limiting_factor: str

    def to_dict(self):
        return asdict(self)

def summarize_plan(plan, planning_seconds=0.0):
    maximum = max((unit.estimated_memory for unit in plan.work_units), default=0)
    if plan.required_count <= 1:
        path = "direct_single_request"
    else:
        path = "durable_adaptive"
    startups = 1
    if plan.concurrency_limit == 1 and plan.repository_kind == "ept":
        limiting = "network/native-worker stability"
    elif maximum * max(1, plan.concurrency_limit) == plan.estimated_peak_memory:
        limiting = "memory and CPU budget"
    else:
        limiting = "native source partitioning"
    return PlanPerformanceSummary(
        float(planning_seconds), plan.adaptive_strategy, plan.workload_category,
        plan.grid.rows * plan.grid.columns, plan.native_partitions_reused,
        plan.candidate_count, plan.required_count, plan.skipped_count,
        plan.concurrency_limit, plan.core_area,
        plan.core_area if path == "direct_single_request" else plan.buffered_read_area,
        1.0 if path == "direct_single_request" else plan.read_amplification,
        maximum, plan.estimated_peak_memory,
        startups, path, limiting,
    )

def measure_plan(planner, **kwargs):
    started = perf_counter()
    plan = planner.plan(**kwargs)
    return plan, summarize_plan(plan, perf_counter() - started)
