"""Pipeline result records and serialization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
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


class ProductValidationSeverity(str, Enum):
    """Authoritative product readiness severity."""

    READY = "READY"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class ProductValidationResult:
    """Product-specific readiness derived from executed pipeline stages."""

    product: str
    ready: bool
    severity: ProductValidationSeverity
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    information: tuple[str, ...]
    required_actions: tuple[str, ...]


@dataclass(frozen=True)
class PipelineStepResult:
    """Result for one pipeline step."""

    step_id: str
    label: str
    status: PipelineStepStatus
    message: str
    events: tuple[PipelineEvent, ...] = ()
    artifacts: tuple[Path, ...] = ()


@dataclass(frozen=True)
class PipelineResult:
    """Result for a product pipeline run."""

    pipeline_id: str
    product: str
    label: str
    steps: tuple[PipelineStepResult, ...]

    @property
    def output_paths(self) -> tuple[Path, ...]:
        """Return output artifacts produced by this pipeline."""
        paths: list[Path] = []
        seen: set[Path] = set()
        for step in self.steps:
            for path in step.artifacts:
                if path not in seen:
                    paths.append(path)
                    seen.add(path)
        return tuple(paths)

    @property
    def passed(self) -> bool:
        """Return true when every executed validation step passed or warned."""
        blocking = {PipelineStepStatus.FAILED, PipelineStepStatus.NOT_IMPLEMENTED}
        return not any(step.status in blocking for step in self.steps)

    @property
    def validation(self) -> ProductValidationResult:
        """Return one product-specific readiness result; warnings never block."""
        blockers = tuple(step.message for step in self.steps if step.status in {PipelineStepStatus.FAILED, PipelineStepStatus.NOT_IMPLEMENTED})
        warnings = tuple(step.message for step in self.steps if step.status == PipelineStepStatus.WARNING)
        information = tuple(step.message for step in self.steps if step.status in {PipelineStepStatus.PASSED, PipelineStepStatus.SKIPPED})
        severity = ProductValidationSeverity.BLOCKED if blockers else (ProductValidationSeverity.NEEDS_ATTENTION if warnings else ProductValidationSeverity.READY)
        actions = tuple(_required_action(step) for step in self.steps if step.status in {PipelineStepStatus.FAILED, PipelineStepStatus.NOT_IMPLEMENTED})
        return ProductValidationResult(self.product, not blockers, severity, blockers, warnings, information, actions)


def _required_action(step: PipelineStepResult) -> str:
    message = step.message.lower()
    if "height" in message:
        return "Provide ground-normalized LiDAR or enable a supported height-above-ground method."
    if "crs" in message:
        return "Assign or resolve the source CRS before a spatial transform or polygon alignment."
    if "source" in message or "dataset" in message:
        return "Select a readable LiDAR source and run Prerun Check again."
    return f"Resolve the {step.label} requirement and run Prerun Check again."


def pipeline_result_to_dict(result: PipelineResult) -> dict[str, Any]:
    """Convert a pipeline result to a JSON-serializable dictionary."""
    return {
        "pipeline_id": result.pipeline_id,
        "product": result.product,
        "label": result.label,
        "passed": result.passed,
        "validation": {
            "ready": result.validation.ready,
            "severity": result.validation.severity.value,
            "blockers": list(result.validation.blockers),
            "warnings": list(result.validation.warnings),
            "information": list(result.validation.information),
            "required_actions": list(result.validation.required_actions),
        },
        "steps": [
            {
                "step_id": step.step_id,
                "label": step.label,
                "status": step.status.value,
                "message": step.message,
                "artifacts": [str(path) for path in step.artifacts],
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
