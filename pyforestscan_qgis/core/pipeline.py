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
from .types import CanopyCoverRequest, ChmRequest, FhdRequest, PadRequest, PaiRequest, RumpleRequest


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
            if self.product == "canopy_cover" and step.stage is PipelineStage.GENERATE_PRODUCT:
                result = _execute_canopy_cover_step(context, step, adapter)
                generated_outputs = result.artifacts
                results.append(result)
                continue
            if self.product == "pad" and step.stage is PipelineStage.GENERATE_PRODUCT:
                result = _execute_pad_step(context, step, adapter)
                generated_outputs = result.artifacts
                results.append(result)
                continue
            if self.product == "pai" and step.stage is PipelineStage.GENERATE_PRODUCT:
                result = _execute_pai_step(context, step, adapter)
                generated_outputs = result.artifacts
                results.append(result)
                continue
            if self.product == "fhd" and step.stage is PipelineStage.GENERATE_PRODUCT:
                result = _execute_fhd_step(context, step, adapter)
                generated_outputs = result.artifacts
                results.append(result)
                continue
            if self.product == "rumple" and step.stage is PipelineStage.GENERATE_PRODUCT:
                result = _execute_rumple_step(context, step, adapter)
                generated_outputs = result.artifacts
                results.append(result)
                continue
            if self.product in {"chm", "canopy_cover", "pad", "pai", "fhd", "rumple"} and step.stage is PipelineStage.EXPORT and generated_outputs:
                output_label = "CSV table" if self.product == "rumple" else "GeoTIFF"
                results.append(_step_result(step, PipelineStepStatus.PASSED, f"{self.label} {output_label} export is available.", generated_outputs))
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
    try:
        output_path = _chm_output_path(context)
        result = adapter.create_chm(
            ChmRequest(
                input_path=context.source_dataset,
                output_path=output_path,
                grid_resolution=context.grid_resolution,
                crs=context.crs,
                interpolation=context.chm_interpolation,
                interp_valid_region=context.chm_interpolate_valid_region,
                interp_clean_edges=context.chm_clean_edges,
            )
        )
    except Exception as exc:  # noqa: BLE001 - pipeline captures adapter boundary errors.
        return _step_result(step, PipelineStepStatus.FAILED, f"CHM generation failed: {exc}")
    if not result.output_path.exists():
        return _step_result(step, PipelineStepStatus.FAILED, f"CHM generation did not produce a GeoTIFF: {result.output_path}")
    return _step_result(step, PipelineStepStatus.PASSED, f"CHM GeoTIFF created: {result.output_path}", (result.output_path,))


def _execute_pad_step(context: PipelineContext, step: PipelineStep, adapter: Any | None) -> PipelineStepResult:
    if adapter is None:
        return _step_result(step, PipelineStepStatus.FAILED, "PAD execution requires an adapter.")
    if not context.source_dataset:
        return _step_result(step, PipelineStepStatus.FAILED, "PAD execution requires a source dataset.")
    if not context.crs:
        return _step_result(step, PipelineStepStatus.FAILED, "PAD execution requires dataset CRS metadata.")
    try:
        output_path = _pad_output_path(context)
        result = adapter.create_pad(
            PadRequest(
                input_path=context.source_dataset,
                output_path=output_path,
                grid_resolution=context.grid_resolution,
                voxel_height=context.voxel_height,
                crs=context.crs,
            )
        )
    except Exception as exc:  # noqa: BLE001 - pipeline captures adapter boundary errors.
        return _step_result(step, PipelineStepStatus.FAILED, f"PAD generation failed: {exc}")
    if not result.output_path.exists():
        return _step_result(step, PipelineStepStatus.FAILED, f"PAD generation did not produce a GeoTIFF: {result.output_path}")
    return _step_result(step, PipelineStepStatus.PASSED, f"PAD multi-band GeoTIFF created: {result.output_path}", (result.output_path,))


def _execute_pai_step(context: PipelineContext, step: PipelineStep, adapter: Any | None) -> PipelineStepResult:
    if adapter is None:
        return _step_result(step, PipelineStepStatus.FAILED, "PAI execution requires an adapter.")
    if not context.source_dataset:
        return _step_result(step, PipelineStepStatus.FAILED, "PAI execution requires a source dataset.")
    if not context.crs:
        return _step_result(step, PipelineStepStatus.FAILED, "PAI execution requires dataset CRS metadata.")
    try:
        output_path = _pai_output_path(context)
        result = adapter.create_pai(
            PaiRequest(
                input_path=context.source_dataset,
                output_path=output_path,
                grid_resolution=context.grid_resolution,
                voxel_height=context.voxel_height,
                crs=context.crs,
            )
        )
    except Exception as exc:  # noqa: BLE001 - pipeline captures adapter boundary errors.
        return _step_result(step, PipelineStepStatus.FAILED, f"PAI generation failed: {exc}")
    if not result.output_path.exists():
        return _step_result(step, PipelineStepStatus.FAILED, f"PAI generation did not produce a GeoTIFF: {result.output_path}")
    return _step_result(step, PipelineStepStatus.PASSED, f"PAI GeoTIFF created: {result.output_path}", (result.output_path,))




def _execute_fhd_step(context: PipelineContext, step: PipelineStep, adapter: Any | None) -> PipelineStepResult:
    if adapter is None:
        return _step_result(step, PipelineStepStatus.FAILED, "FHD execution requires an adapter.")
    if not context.source_dataset:
        return _step_result(step, PipelineStepStatus.FAILED, "FHD execution requires a source dataset.")
    if not context.crs:
        return _step_result(step, PipelineStepStatus.FAILED, "FHD execution requires dataset CRS metadata.")
    try:
        output_path = _fhd_output_path(context)
        result = adapter.create_fhd(
            FhdRequest(
                input_path=context.source_dataset,
                output_path=output_path,
                grid_resolution=context.grid_resolution,
                voxel_height=context.voxel_height,
                crs=context.crs,
            )
        )
    except Exception as exc:  # noqa: BLE001 - pipeline captures adapter boundary errors.
        return _step_result(step, PipelineStepStatus.FAILED, f"FHD generation failed: {exc}")
    if not result.output_path.exists():
        return _step_result(step, PipelineStepStatus.FAILED, f"FHD generation did not produce a GeoTIFF: {result.output_path}")
    return _step_result(step, PipelineStepStatus.PASSED, f"FHD GeoTIFF created: {result.output_path}", (result.output_path,))


def _execute_rumple_step(context: PipelineContext, step: PipelineStep, adapter: Any | None) -> PipelineStepResult:
    if adapter is None:
        return _step_result(step, PipelineStepStatus.FAILED, "Rumple execution requires an adapter.")
    if not context.source_dataset:
        return _step_result(step, PipelineStepStatus.FAILED, "Rumple execution requires a source dataset.")
    try:
        output_path = _rumple_output_path(context)
        result = adapter.create_rumple(
            RumpleRequest(
                input_path=context.source_dataset,
                output_path=output_path,
                grid_resolution=context.grid_resolution,
                crs=context.crs,
                interpolation=context.chm_interpolation,
                interp_valid_region=context.chm_interpolate_valid_region,
                interp_clean_edges=context.chm_clean_edges,
            )
        )
    except Exception as exc:  # noqa: BLE001 - pipeline captures adapter boundary errors.
        return _step_result(step, PipelineStepStatus.FAILED, f"Rumple generation failed: {exc}")
    if not result.output_path.exists():
        return _step_result(step, PipelineStepStatus.FAILED, f"Rumple generation did not produce its requested output: {result.output_path}")
    label="legacy scalar CSV" if result.output_path.suffix.lower()==".csv" else "spatial GeoTIFF"
    return _step_result(step, PipelineStepStatus.PASSED, f"Rumple {label} created: {result.output_path}", (result.output_path,))


def _fhd_output_path(context: PipelineContext) -> Path:
    """Return the validated FHD output path for a pipeline context."""
    return _simple_geotiff_output_path(context.output_folder, context.fhd_output_filename, "FHD")


def _rumple_output_path(context: PipelineContext) -> Path:
    """Return the validated rumple output path for a pipeline context."""
    if Path(context.rumple_output_filename).suffix.lower()==".csv":
        return _simple_csv_output_path(context.output_folder, context.rumple_output_filename, "Rumple")
    return _simple_geotiff_output_path(context.output_folder, context.rumple_output_filename, "Rumple")

def _pad_output_path(context: PipelineContext) -> Path:
    """Return the validated PAD output path for a pipeline context."""
    return _simple_geotiff_output_path(context.output_folder, context.pad_output_filename, "PAD")


def _pai_output_path(context: PipelineContext) -> Path:
    """Return the validated PAI output path for a pipeline context."""
    return _simple_geotiff_output_path(context.output_folder, context.pai_output_filename, "PAI")



def _execute_canopy_cover_step(context: PipelineContext, step: PipelineStep, adapter: Any | None) -> PipelineStepResult:
    if adapter is None:
        return _step_result(step, PipelineStepStatus.FAILED, "Canopy cover execution requires an adapter.")
    if not context.source_dataset:
        return _step_result(step, PipelineStepStatus.FAILED, "Canopy cover execution requires a source dataset.")
    if not context.crs:
        return _step_result(step, PipelineStepStatus.FAILED, "Canopy cover execution requires dataset CRS metadata.")
    try:
        output_path = _canopy_cover_output_path(context)
        result = adapter.create_canopy_cover(
            CanopyCoverRequest(
                input_path=context.source_dataset,
                output_path=output_path,
                grid_resolution=context.grid_resolution,
                canopy_height_threshold=context.canopy_cover_height_threshold,
                crs=context.crs,
            )
        )
    except Exception as exc:  # noqa: BLE001 - pipeline captures adapter boundary errors.
        return _step_result(step, PipelineStepStatus.FAILED, f"Canopy cover generation failed: {exc}")
    if not result.output_path.exists():
        return _step_result(step, PipelineStepStatus.FAILED, f"Canopy cover generation did not produce a GeoTIFF: {result.output_path}")
    return _step_result(step, PipelineStepStatus.PASSED, f"Canopy cover GeoTIFF created: {result.output_path}", (result.output_path,))


def _canopy_cover_output_path(context: PipelineContext) -> Path:
    """Return the validated canopy cover output path for a pipeline context."""
    name = context.canopy_cover_output_filename
    return _simple_geotiff_output_path(context.output_folder, context.canopy_cover_output_filename, "Canopy cover")


def _chm_output_path(context: PipelineContext) -> Path:
    """Return the validated CHM output path for a pipeline context."""
    return _simple_geotiff_output_path(context.output_folder, context.chm_output_filename, "CHM")


def _simple_geotiff_output_path(output_folder: Path, name: str, label: str) -> Path:
    candidate = Path(name)
    if candidate.name != name or candidate.suffix.lower() not in {".tif", ".tiff"}:
        raise ValueError(f"{label} output filename must be a simple .tif or .tiff filename.")
    return output_folder / candidate.name


def _simple_csv_output_path(output_folder: Path, name: str, label: str) -> Path:
    candidate = Path(name)
    if candidate.name != name or candidate.suffix.lower() != ".csv":
        raise ValueError(f"{label} output filename must be a simple .csv filename.")
    return output_folder / candidate.name


def _step_result(
    step: PipelineStep,
    status: PipelineStepStatus,
    message: str,
    artifacts: tuple[Path, ...] = (),
) -> PipelineStepResult:
    level = PipelineEventLevel.ERROR if status is PipelineStepStatus.FAILED else PipelineEventLevel.INFO
    event = PipelineEvent(step.step_id, level, message, pipeline_utc_now())
    return PipelineStepResult(step.step_id, step.label, status, message, (event,), artifacts)
