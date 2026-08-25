"""Sequential batch runner built on existing single-file services."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .adapter import PyForestScanAdapter
from .batch import BatchItemResult, BatchRequest, BatchResult, batch_run_context, create_batch_folder
from .batch_results import write_batch_summaries
from .output_registry import generated_output_for_path, write_output_registry
from .batch_manifest import MANIFEST_NAME, create_manifest, load_manifest, update_manifest_item, write_manifest
from .dataset_report import build_dataset_explorer_report, report_to_dict, write_csv_summary, write_html_report, write_json_report
from .job_manager import JobManager
from .jobs import JobRecord
from .product_plan import ProductPlannerRequest, build_product_plan, write_plan_csv, write_plan_html, write_plan_json

BatchProgressCallback = Callable[[BatchItemResult], None]
BatchJobCallback = Callable[[JobRecord], None]
BatchControlCallback = Callable[[], str | None]


class BatchExecutionError(ValueError):
    """Raised when a batch request cannot be executed."""


class BatchRunner:
    """Run selected lidar datasets sequentially through existing workflows."""

    def __init__(
        self,
        adapter: PyForestScanAdapter | None = None,
        job_manager_factory: Callable[[BatchJobCallback | None], JobManager] | None = None,
        item_callback: BatchProgressCallback | None = None,
        job_callback: BatchJobCallback | None = None,
        control_callback: BatchControlCallback | None = None,
    ) -> None:
        """Create a batch runner with injectable adapter and job manager factory."""
        self.adapter = adapter or PyForestScanAdapter()
        self.job_manager_factory = job_manager_factory or (lambda callback: JobManager(event_sink=callback, adapter=self.adapter))
        self.item_callback = item_callback
        self.job_callback = job_callback
        self.control_callback = control_callback

    def run(self, request: BatchRequest) -> BatchResult:
        """Run a sequential batch and write JSON, CSV, and HTML summaries."""
        if not request.datasets:
            raise BatchExecutionError("Select at least one lidar dataset for batch processing.")
        if not request.settings.products:
            raise BatchExecutionError("Select at least one product for batch processing.")
        started_at = datetime.now(timezone.utc).isoformat()
        batch_folder = request.batch_folder or create_batch_folder(request.output_folder)
        manifest_path = batch_folder / MANIFEST_NAME
        manifest = load_manifest(manifest_path) if manifest_path.exists() else create_manifest(request, batch_folder)
        write_manifest(manifest)
        batch_id = manifest.batch_id or f"pfs-batch-{uuid.uuid4().hex[:10]}"
        items: list[BatchItemResult] = []
        for index, dataset in enumerate(request.datasets):
            control = self._control_state()
            while control == "pause":
                time.sleep(0.05)
                control = self._control_state()
            if control == "cancel":
                skipped = self._skipped_items(request.datasets[index:], batch_folder, "Cancelled before processing.")
                items.extend(skipped)
                for skipped_item in skipped:
                    manifest = update_manifest_item(manifest, skipped_item)
                    write_manifest(manifest)
                    self._write_partial_summary(batch_id, request, batch_folder, started_at, items)
                break
            item = self.run_dataset(Path(dataset), batch_folder, request)
            items.append(item)
            manifest = update_manifest_item(manifest, item)
            write_manifest(manifest)
            self._write_partial_summary(batch_id, request, batch_folder, started_at, items)
            if self.item_callback is not None:
                self.item_callback(item)
            if item.status == "failed" and request.settings.stop_on_error:
                skipped = self._skipped_items(request.datasets[index + 1 :], batch_folder, "Skipped after stop-on-error.")
                items.extend(skipped)
                for skipped_item in skipped:
                    manifest = update_manifest_item(manifest, skipped_item)
                    write_manifest(manifest)
                    self._write_partial_summary(batch_id, request, batch_folder, started_at, items)
                break
        finished_at = datetime.now(timezone.utc).isoformat()
        result = BatchResult(
            batch_id=batch_id,
            title=request.title,
            started_at=started_at,
            finished_at=finished_at,
            batch_folder=batch_folder,
            items=tuple(items),
            summary_json=batch_folder / "batch_summary.json",
            summary_csv=batch_folder / "batch_summary.csv",
            summary_html=batch_folder / "batch_summary.html",
            load_outputs_after_completion=request.settings.load_outputs_into_qgis,
        )
        result = _with_output_registry(result, source_mode="standard_file_batch")
        return write_batch_summaries(result)

    def _write_partial_summary(self, batch_id: str, request: BatchRequest, batch_folder: Path, started_at: str, items: list[BatchItemResult]) -> None:
        """Write summaries after each file so progress survives interruption."""
        partial = BatchResult(
            batch_id=batch_id,
            title=request.title,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
            batch_folder=batch_folder,
            items=tuple(items),
            summary_json=batch_folder / "batch_summary.json",
            summary_csv=batch_folder / "batch_summary.csv",
            summary_html=batch_folder / "batch_summary.html",
            load_outputs_after_completion=request.settings.load_outputs_into_qgis,
        )
        partial = _with_output_registry(partial, source_mode="standard_file_batch")
        write_batch_summaries(partial)

    def run_dataset(self, dataset: Path, batch_folder: Path, request: BatchRequest) -> BatchItemResult:
        """Run one dataset inside an existing batch folder."""
        context = batch_run_context(dataset, batch_folder, reuse_existing=True).ensure_directories()
        try:
            inspection = self.adapter.inspect_dataset(dataset)
            report = build_dataset_explorer_report(inspection)
            write_json_report(report, context.dataset_report_json)
            write_csv_summary(report, context.dataset_summary_csv)
            write_html_report(report, context.dataset_report_html)
            product_request = ProductPlannerRequest(
                explorer_report_path=context.dataset_report_json,
                requested_products=request.settings.products,
                output_folder=context.outputs_dir,
                grid_resolution=request.settings.grid_resolution,
                height_bin_size=request.settings.height_bin_size,
                chm_interpolation=request.settings.chm_interpolation,
                chm_interpolate_valid_region=request.settings.chm_interpolate_valid_region,
                chm_clean_edges=request.settings.chm_clean_edges,
                canopy_cover_height_threshold=request.settings.canopy_cover_height_threshold,
                title=f"Product Plan - {dataset.name}",
            )
            plan = build_product_plan(report_to_dict(report), product_request)
            write_plan_json(plan, context.product_plan_json)
            write_plan_csv(plan, context.product_plan_csv)
            write_plan_html(plan, context.product_plan_html)
            manager = self.job_manager_factory(self.job_callback)
            job = manager.run_pipeline(
                context.product_plan_json,
                context.logs_dir,
                title=f"PyForestScan Batch - {dataset.name}",
                summary_path=context.job_summary_json,
            )
            status = "completed" if job.status.value == "completed" else "failed"
            message = job.error_message or job.status.value
            return BatchItemResult(
                dataset_path=dataset,
                run_context=context,
                status=status,
                message=message,
                outputs=tuple(result.path for result in job.results if _is_product_output(result.result_type)),
                bounds_summary=_bounds_summary(report.bounds),
                requested_products=tuple(product.value for product in request.settings.products),
            )
        except Exception as exc:  # noqa: BLE001 - batch records per-file failures and continues.
            return BatchItemResult(
                dataset_path=dataset,
                run_context=context,
                status="failed",
                message=str(exc),
                outputs=(),
                bounds_summary="Unavailable",
                requested_products=tuple(product.value for product in request.settings.products),
            )

    def _control_state(self) -> str | None:
        """Return the current batch control state from the UI, if any."""
        if self.control_callback is None:
            return None
        state = self.control_callback()
        return state if state in {"pause", "cancel"} else None

    def _skipped_items(self, datasets: tuple[Path, ...], batch_folder: Path, message: str) -> list[BatchItemResult]:
        """Create skipped records for datasets that were not processed."""
        skipped: list[BatchItemResult] = []
        for dataset in datasets:
            context = batch_run_context(dataset, batch_folder, reuse_existing=True).ensure_directories()
            item = BatchItemResult(
                dataset_path=Path(dataset),
                run_context=context,
                status="skipped",
                message=message,
                outputs=(),
                bounds_summary="Not inspected",
                requested_products=(),
            )
            skipped.append(item)
            if self.item_callback is not None:
                self.item_callback(item)
        return skipped


def _bounds_summary(bounds: object) -> str:
    min_x = getattr(bounds, "min_x", None)
    max_x = getattr(bounds, "max_x", None)
    min_y = getattr(bounds, "min_y", None)
    max_y = getattr(bounds, "max_y", None)
    if None in (min_x, max_x, min_y, max_y):
        return "Unavailable"
    return f"X {float(min_x):.3f} to {float(max_x):.3f}; Y {float(min_y):.3f} to {float(max_y):.3f}"


def _is_product_output(result_type: str) -> bool:
    """Exclude plans, reports, and diagnostics from scientific output counts."""
    return result_type.endswith(("_geotiff", "_csv")) and not result_type.startswith(("job_summary", "dataset_", "product_plan"))



def _with_output_registry(result: BatchResult, *, source_mode: str) -> BatchResult:
    outputs = [
        generated_output_for_path(output, job_id=result.batch_id, source_mode=source_mode)
        for item in result.items
        if item.status == "completed"
        for output in item.outputs
        if Path(output).exists()
    ]
    if not outputs:
        return result
    registry_path = write_output_registry(outputs, result.batch_folder)
    from dataclasses import replace

    return replace(result, output_registry_path=registry_path)
