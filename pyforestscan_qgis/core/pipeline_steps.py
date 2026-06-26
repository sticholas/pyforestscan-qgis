"""Pipeline step definitions for product orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .pipeline_context import PipelineContext
from .pipeline_events import PipelineEvent, PipelineEventLevel, pipeline_utc_now
from .pipeline_results import PipelineStepResult, PipelineStepStatus


class PipelineStage(str, Enum):
    """Known pipeline stages."""

    VALIDATE_DATASET = "validate_dataset"
    VALIDATE_ENVIRONMENT = "validate_environment"
    VALIDATE_CRS = "validate_crs"
    GROUND_CHECK = "ground_check"
    NORMALIZE_HEIGHTS = "normalize_heights"
    CLIP = "clip"
    GENERATE_PRODUCT = "generate_product"
    EXPORT = "export"


class PipelineStepKind(str, Enum):
    """Whether a step is safe validation or future scientific work."""

    VALIDATION = "validation"
    SCIENTIFIC = "scientific"
    EXPORT = "export"


Validator = Callable[[PipelineContext, "PipelineStep"], PipelineStepResult]


@dataclass(frozen=True)
class PipelineStep:
    """One step in a product processing pipeline."""

    step_id: str
    label: str
    stage: PipelineStage
    kind: PipelineStepKind
    validator: Validator | None = None

    def execute(self, context: PipelineContext) -> PipelineStepResult:
        """Execute this step for a context."""
        if self.kind is not PipelineStepKind.VALIDATION:
            raise NotImplementedError(f"Pipeline step is not implemented yet: {self.label}")
        if self.validator is None:
            return self._result(PipelineStepStatus.PASSED, "Validation step has no additional checks.")
        return self.validator(context, self)

    def skipped_result(self) -> PipelineStepResult:
        """Return a skipped result for non-executed future steps."""
        return self._result(PipelineStepStatus.SKIPPED, "Future scientific processing stage; not executed in this phase.")

    def _result(self, status: PipelineStepStatus, message: str) -> PipelineStepResult:
        event = PipelineEvent(
            step_id=self.step_id,
            level=_event_level(status),
            message=message,
            timestamp=pipeline_utc_now(),
        )
        return PipelineStepResult(self.step_id, self.label, status, message, (event,))


def validate_dataset_step(context: PipelineContext, step: PipelineStep) -> PipelineStepResult:
    """Validate that the product plan references a dataset."""
    if not context.source_dataset:
        return step._result(PipelineStepStatus.FAILED, "Product plan does not record a source dataset.")
    plan_status = str(context.product_entry.get("plan_status", ""))
    if plan_status == "Blocked":
        return step._result(PipelineStepStatus.FAILED, f"{context.product_label} is blocked in the product plan.")
    return step._result(PipelineStepStatus.PASSED, f"Dataset recorded for {context.product_label}.")


def validate_environment_step(context: PipelineContext, step: PipelineStep) -> PipelineStepResult:
    """Validate dry-run plan flags without importing scientific dependencies."""
    if context.product_plan.get("processing_executed") is not False:
        return step._result(PipelineStepStatus.FAILED, "Product plan must have processing_executed=false.")
    return step._result(PipelineStepStatus.PASSED, "Execution environment accepted for dry-run validation.")


def validate_crs_step(context: PipelineContext, step: PipelineStep) -> PipelineStepResult:
    """Validate CRS metadata when Dataset Explorer JSON is available."""
    if context.dataset_report is None:
        return step._result(PipelineStepStatus.WARNING, "Dataset Explorer JSON was not available for CRS validation.")
    geometry = context.dataset_report.get("geometry")
    crs = geometry.get("crs") if isinstance(geometry, dict) else None
    if not crs:
        return step._result(PipelineStepStatus.WARNING, "Dataset CRS is unknown; review before scientific processing.")
    return step._result(PipelineStepStatus.PASSED, "Dataset CRS metadata is present.")


def ground_check_step(context: PipelineContext, step: PipelineStep) -> PipelineStepResult:
    """Validate ground/HAG planning evidence when available."""
    status = str(context.product_entry.get("feasibility_status", ""))
    if status == "Unavailable":
        return step._result(PipelineStepStatus.FAILED, "Product feasibility is unavailable in the plan.")
    if status == "Warning" or context.product_entry.get("warnings"):
        return step._result(PipelineStepStatus.WARNING, "Product feasibility needs review before scientific processing.")
    return step._result(PipelineStepStatus.PASSED, "Ground and height prerequisites appear acceptable for planning.")


def default_product_steps(product: str, label: str) -> tuple[PipelineStep, ...]:
    """Return the standard registered pipeline for a product."""
    prefix = product.replace("_", "-")
    return (
        PipelineStep(f"{prefix}-dataset", "Validate Dataset", PipelineStage.VALIDATE_DATASET, PipelineStepKind.VALIDATION, validate_dataset_step),
        PipelineStep(f"{prefix}-environment", "Validate Environment", PipelineStage.VALIDATE_ENVIRONMENT, PipelineStepKind.VALIDATION, validate_environment_step),
        PipelineStep(f"{prefix}-crs", "Validate CRS", PipelineStage.VALIDATE_CRS, PipelineStepKind.VALIDATION, validate_crs_step),
        PipelineStep(f"{prefix}-ground", "Ground Check", PipelineStage.GROUND_CHECK, PipelineStepKind.VALIDATION, ground_check_step),
        PipelineStep(f"{prefix}-normalize", "Normalize Heights", PipelineStage.NORMALIZE_HEIGHTS, PipelineStepKind.SCIENTIFIC),
        PipelineStep(f"{prefix}-clip", "Clip", PipelineStage.CLIP, PipelineStepKind.SCIENTIFIC),
        PipelineStep(f"{prefix}-generate", f"Generate {label}", PipelineStage.GENERATE_PRODUCT, PipelineStepKind.SCIENTIFIC),
        PipelineStep(f"{prefix}-export", "Export", PipelineStage.EXPORT, PipelineStepKind.EXPORT),
    )


def _event_level(status: PipelineStepStatus) -> PipelineEventLevel:
    if status is PipelineStepStatus.FAILED or status is PipelineStepStatus.NOT_IMPLEMENTED:
        return PipelineEventLevel.ERROR
    if status is PipelineStepStatus.WARNING or status is PipelineStepStatus.SKIPPED:
        return PipelineEventLevel.WARNING
    return PipelineEventLevel.INFO
