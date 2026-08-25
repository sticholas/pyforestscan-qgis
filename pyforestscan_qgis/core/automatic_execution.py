"""Automatic source-level scheduling policy for Batch."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_WORKER_CEILING = 5


@dataclass(frozen=True)
class AutomaticExecutionDecision:
    strategy: str
    effective_workers: int
    worker_ceiling: int
    reason: str


def choose_automatic_execution(
    source_count: int,
    *,
    source_type: str = "file",
    worker_ceiling: int = DEFAULT_WORKER_CEILING,
    memory_worker_limit: int | None = None,
) -> AutomaticExecutionDecision:
    """Choose safe source concurrency; EPT work-unit scheduling stays separate."""
    ceiling = max(1, min(DEFAULT_WORKER_CEILING, int(worker_ceiling)))
    if source_count <= 1:
        reason = "One logical source uses one source worker; internal EPT work units remain adaptive."
        return AutomaticExecutionDecision("sequential", 1, ceiling, reason)
    safe = min(source_count, ceiling)
    if source_type.lower() == "ept":
        safe = 1
    if memory_worker_limit is not None:
        safe = min(safe, max(1, int(memory_worker_limit)))
    strategy = "parallel_safe" if safe > 1 else "sequential"
    return AutomaticExecutionDecision(strategy, safe, ceiling, "Concurrency selected automatically within the safety ceiling.")


__all__ = ["AutomaticExecutionDecision", "DEFAULT_WORKER_CEILING", "choose_automatic_execution"]
