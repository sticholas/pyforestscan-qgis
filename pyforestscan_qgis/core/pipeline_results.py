"""Pipeline result records and serialization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .pipeline_events import PipelineEvent


class PipelineStepStatus(str, Enum):
    """Execution status for one pipeline step."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    WARNING = "warning"
    SKIPPED = "skipped"
    FAILED = "failed"
    NOT_IMPLEMENTED = "not_implemented"


@dataclass(frozen=True)
class PipelineStepResult:
    """Result for one pipeline step."""

    step_id: str
    label: str
    status: PipelineStepStatus
    message: str
    events: tuple[PipelineEvent, ...] = ()


@dataclass(frozen=True)
class PipelineResult:
    """Result for a product pipeline run."""

    pipeline_id: str
    product: str
    label: str
    steps: tuple[PipelineStepResult, ...]

    @property
    def passed(self) -> bool:
        """Return true when every executed validation step passed or warned."""
        blocking = {PipelineStepStatus.FAILED, PipelineStepStatus.NOT_IMPLEMENTED}
        return not any(step.status in blocking for step in self.steps)


def pipeline_result_to_dict(result: PipelineResult) -> dict[str, Any]:
    """Convert a pipeline result to a JSON-serializable dictionary."""
    return {
        "pipeline_id": result.pipeline_id,
        "product": result.product,
        "label": result.label,
        "passed": result.passed,
        "steps": [
            {
                "step_id": step.step_id,
                "label": step.label,
                "status": step.status.value,
                "message": step.message,
                "events": [
                    {
                        "timestamp": event.timestamp,
                        "level": event.level.value,
                        "message": event.message,
                    }
                    for event in step.events
                ],
            }
            for step in result.steps
        ],
    }
