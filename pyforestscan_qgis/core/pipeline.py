"""Processing pipeline registry and executor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .pipeline_context import PipelineContext
from .pipeline_results import PipelineResult, PipelineStepResult, PipelineStepStatus
from .pipeline_steps import PipelineStep, default_product_steps
from .product_plan import PRODUCT_LABELS


@dataclass(frozen=True)
class Pipeline:
    """Registered processing pipeline for one future product."""

    pipeline_id: str
    product: str
    label: str
    steps: tuple[PipelineStep, ...]

    def run_validation(self, context: PipelineContext) -> PipelineResult:
        """Execute validation steps and skip future scientific/export stages."""
        results: list[PipelineStepResult] = []
        for step in self.steps:
            if step.validator is None:
                results.append(step.skipped_result())
                continue
            try:
                results.append(step.execute(context))
            except Exception as exc:
                results.append(
                    PipelineStepResult(
                        step.step_id,
                        step.label,
                        PipelineStepStatus.FAILED,
                        f"Pipeline validation failed: {exc}",
                        (),
                    )
                )
        return PipelineResult(self.pipeline_id, self.product, self.label, tuple(results))


class PipelineRegistry:
    """Registry of product identifiers to pipeline definitions."""

    def __init__(self, pipelines: Mapping[str, Pipeline] | None = None) -> None:
        """Create a pipeline registry."""
        self._pipelines = dict(pipelines or {})

    def register(self, pipeline: Pipeline) -> None:
        """Register or replace a product pipeline."""
        self._pipelines[pipeline.product] = pipeline

    def get(self, product: str) -> Pipeline:
        """Return a registered pipeline by product identifier."""
        try:
            return self._pipelines[product]
        except KeyError as exc:
            raise KeyError(f"No pipeline is registered for product: {product}") from exc

    def all(self) -> tuple[Pipeline, ...]:
        """Return all registered pipelines."""
        return tuple(self._pipelines.values())


def build_default_pipeline_registry() -> PipelineRegistry:
    """Build the default registry for all planned product families."""
    registry = PipelineRegistry()
    for product_type, label in PRODUCT_LABELS.items():
        product = product_type.value
        registry.register(Pipeline(f"{product}-pipeline", product, label, default_product_steps(product, label)))
    return registry


def registered_product_ids() -> tuple[str, ...]:
    """Return product identifiers with registered placeholder pipelines."""
    return tuple(product.value for product in PRODUCT_LABELS)
