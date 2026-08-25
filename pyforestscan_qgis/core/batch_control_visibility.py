"""Pure semantic visibility model for Batch specialist controls."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BatchControlVisibility:
    execution_mode: bool
    maximum_workers: bool
    parallel_confirmation: bool
    polygon_finalization: bool
    repository_options: bool


def batch_control_visibility(*, profile: str, execution_mode: str, polygon_mode: bool, repository_selected: bool) -> BatchControlVisibility:
    custom = profile == "custom"
    parallel = custom and execution_mode == "parallel_safe"
    return BatchControlVisibility(custom, parallel, False, polygon_mode, polygon_mode and repository_selected)


__all__ = ["BatchControlVisibility", "batch_control_visibility"]
