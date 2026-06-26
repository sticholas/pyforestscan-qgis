"""Processing pipeline registry and executor."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .pipeline_context import PipelineContext
from .pipeline_events import PipelineEvent, PipelineEventLevel, pipeline_utc_now
from .pipeline_results import PipelineResult, PipelineStepResult, PipelineStepStatus
from .pipeline_steps import PipelineStage, PipelineStep, default_product_steps
from .product_plan import PRODUCT_LABELS
from .types import ChmRequest


@dataclass(frozen=True)
class Pipeline:
    """Registered processing pipeline for one future product."""

    pipeline_id: str
    product: str
    label: str
    steps: tuple[PipelineStep, ...]

    def run_validation(self, context: PipelineContext) -> PipelineResult:
        """Execute validation steps and skip future scientific/export stages."""
        return self.run(context, adapter=None, execute_products=False)

    def run(self, context: PipelineContext, adapter: Any | None = None, execute_products: bool = False) -> PipelineResult:
        """Run the pipeline, optionally executing implemented product stages."""
        results: list[PipelineStepResult] = []
        generated_outputs: tuple[Path, ...] = ()
        for step in self.steps:
            if step.validator is not None:
                try:
                    results.append(step.execute(context))
                except Exception as exc:
                    results.append(_step_result(step, PipelineStepStatus.FAILED, f"Pipeline validation failed: {exc}"))
                continue
            if not execute_products:
                results.append(step.skipped_result())
                continue
            if self.product == "chm" and step.stage is PipelineStage.GENERATE_PRODUCT:
                result = _execute_chm_step(context, step, adapter)
                generated_outputs = result.artifacts
                results.append(result)
                continue
            if self.product == "chm" and step.stage is PipelineStage.EXPORT and generated_outputs:
                results.append(_step_result(step, PipelineStepStatus.PASSED, "CHM GeoTIFF export is available.", generated_outputs))
                continue
            results.append(step.skipped_result())
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


def _execute_chm_step(context: PipelineContext, step: PipelineStep, adapter: Any | None) -> PipelineStepResult:
    if adapter is None:
        return _step_result(step, PipelineStepStatus.FAILED, "CHM execution requires an adapter.")
    if not context.source_dataset:
        return _step_result(step, PipelineStepStatus.FAILED, "CHM execution requires a source dataset.")
    if not context.crs:
        return _step_result(step, PipelineStepStatus.FAILED, "CHM execution requires dataset CRS metadata.")
    output_path = context.output_folder / "chm.tif"
    try:
        result = adapter.create_chm(
            ChmRequest(
                input_path=context.source_dataset,
                output_path=output_path,
                grid_resolution=context.grid_resolution,
                crs=context.crs,
            )
        )
    except Exception as exc:  # noqa: BLE001 - pipeline captures adapter boundary errors.
        return _step_result(step, PipelineStepStatus.FAILED, f"CHM generation failed: {exc}")
    return _step_result(step, PipelineStepStatus.PASSED, f"CHM GeoTIFF created: {result.output_path}", (result.output_path,))


def _step_result(
    step: PipelineStep,
    status: PipelineStepStatus,
    message: str,
    artifacts: tuple[Path, ...] = (),
) -> PipelineStepResult:
    level = PipelineEventLevel.ERROR if status is PipelineStepStatus.FAILED else PipelineEventLevel.INFO
    event = PipelineEvent(step.step_id, level, message, pipeline_utc_now())
    return PipelineStepResult(step.step_id, step.label, status, message, (event,), artifacts)
