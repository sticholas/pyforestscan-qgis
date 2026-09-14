"""Shared Batch execution and polygon finalization options."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BatchExecutionOptions:
    """Shared Batch options consumed by Standard and Polygon execution."""

    maximum_parallel_jobs: int = 1
    worker_count: int = 1
    file_reader_workers: int = 1
    product_workers: int = 1
    run_sequentially: bool = True
    continue_on_error: bool = True
    retry_failed_jobs: bool = False
    maximum_retry_attempts: int = 1
    overwrite_existing: bool = False
    skip_existing: bool = True
    reuse_existing_outputs: bool = True
    load_outputs_after_completion: bool = False
    load_only_successful_outputs: bool = True
    add_outputs_to_group: bool = True
    output_group_name: str = "PyForestScan"
    preserve_directory_structure: bool = False
    naming_template: str = "{source}_{product}"
    temporary_workspace_root: Path | None = None
    retain_temporary_inputs: bool = False
    retain_diagnostics: bool = True
    diagnostics_detail: str = "standard"
    cleanup_successful_jobs: bool = False
    maximum_memory: str = ""
    chunk_size: int | None = None
    timeout: int | None = None
    cancellation_behavior: str = "finish_current_stage"
    raster_compression: str = "deflate"
    raster_nodata: float | None = None
    raster_data_type: str = "preserve"
    metadata_sidecar: bool = True
    write_checksums: bool = False
    output_conflict_policy: str = "overwrite"

    @classmethod
    def from_batch_settings(cls, settings: Any) -> "BatchExecutionOptions":
        mode = str(getattr(settings, "execution_mode", "sequential"))
        workers = int(getattr(settings, "max_workers", 1) or 1)
        overwrite = bool(getattr(settings, "overwrite_existing", False))
        skip = bool(getattr(settings, "skip_completed", True))
        retry = bool(getattr(settings, "retry_failed_only", False))
        return cls(
            maximum_parallel_jobs=workers,
            worker_count=workers,
            run_sequentially=mode == "sequential" or workers == 1,
            continue_on_error=not bool(getattr(settings, "stop_on_error", False)),
            retry_failed_jobs=retry,
            maximum_retry_attempts=2 if retry else 1,
            overwrite_existing=overwrite,
            skip_existing=skip,
            reuse_existing_outputs=skip and not overwrite,
            load_outputs_after_completion=bool(getattr(settings, "load_outputs_into_qgis", False)),
            output_conflict_policy="overwrite" if overwrite else ("skip" if skip else "fail"),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.__dict__)
        if self.temporary_workspace_root is not None:
            payload["temporary_workspace_root"] = str(self.temporary_workspace_root)
        return payload


@dataclass(frozen=True)
class PolygonBatchOptions:
    """Polygon-specific finalization options."""

    exact_raster_mask: bool = True
    mask_engine: str = "automatic"
    all_touched: bool = False
    crop_to_polygon_extent: bool = False
    preserve_input_resolution: bool = True
    preserve_input_crs: bool = True
    target_resolution: float | None = None
    mask_nodata: float | None = None
    repair_invalid_polygon: bool = True
    dissolve_selected_features: bool = True
    multipart_behavior: str = "preserve"
    retain_unmasked_intermediate: bool = False
    mask_failure_policy: str = "fail_product"

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class BatchOptionApplicability:
    """Explain whether an option affects a source/mode combination."""

    option_key: str
    standard_file_batch: bool
    polygon_local_tiles: bool
    polygon_ept: bool
    polygon_copc: bool
    scalar_products: bool
    raster_products: bool
    supported: bool
    reason: str
    effective_value: object

    def to_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


def polygon_option_applicability(options: BatchExecutionOptions, *, source_types: set[str], product_count: int, polygon_count: int = 1) -> tuple[BatchOptionApplicability, ...]:
    """Return shared Batch option applicability for Polygon Area Processing."""
    logical_ept = bool(source_types & {"ept", "copc"})
    effective_jobs = min(options.maximum_parallel_jobs, max(1, product_count * polygon_count))
    if logical_ept and product_count == 1 and polygon_count == 1:
        effective_jobs = 1
        reason = "This repository is processed as one logical EPT/COPC source. Concurrency applies across polygons or products, not internal hierarchy nodes."
    else:
        reason = "Concurrency applies to independent logical jobs and never splits EPT hierarchy nodes."
    return (
        BatchOptionApplicability("maximum_parallel_jobs", True, True, True, True, True, True, True, reason, effective_jobs),
        BatchOptionApplicability("worker_count", True, True, True, True, True, True, True, reason, options.worker_count),
        BatchOptionApplicability("overwrite_existing", True, True, True, True, True, True, True, "Output conflict policy is applied before final registration.", options.overwrite_existing),
        BatchOptionApplicability("skip_existing", True, True, True, True, True, True, True, "Existing outputs can be reused or skipped according to the shared Batch setting.", options.skip_existing),
        BatchOptionApplicability("retry_failed_jobs", True, True, True, True, True, True, True, "Retries create a new logical attempt; mask/load retries do not require product regeneration when valid outputs exist.", options.retry_failed_jobs),
        BatchOptionApplicability("load_outputs_after_completion", True, True, True, True, True, True, True, "Loading occurs after final masked output registration on the QGIS main thread.", options.load_outputs_after_completion),
        BatchOptionApplicability("retain_diagnostics", True, True, True, True, True, True, True, "Failure diagnostics are always retained; success retention follows this shared option.", options.retain_diagnostics),
    )


def requested_effective_concurrency(options: BatchExecutionOptions, *, source_types: set[str], product_count: int, polygon_count: int = 1) -> dict[str, object]:
    applicability = polygon_option_applicability(options, source_types=source_types, product_count=product_count, polygon_count=polygon_count)
    concurrent = next(item for item in applicability if item.option_key == "maximum_parallel_jobs")
    return {
        "requested_concurrent_jobs": options.maximum_parallel_jobs,
        "effective_concurrent_jobs": concurrent.effective_value,
        "worker_count": options.worker_count,
        "source_types": sorted(source_types),
        "reason": concurrent.reason,
    }
