"""Batch execution coordinator with sequential and guarded parallel modes."""

from __future__ import annotations

import subprocess
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .adapter import PyForestScanAdapter
from .batch import BatchItemResult, BatchRequest, BatchResult, batch_run_context, create_batch_folder
from .batch_results import write_batch_summaries
from .output_registry import generated_output_for_path, write_output_registry
from .batch_manifest import MANIFEST_NAME, create_manifest, load_manifest, update_manifest_item, write_manifest
from .batch_runner import BatchControlCallback, BatchExecutionError, BatchJobCallback, BatchProgressCallback, BatchRunner
from .external_worker import (
    EXTERNAL_WORKER_DISABLED_MESSAGE,
    EXTERNAL_WORKER_MODE,
    MAX_EXTERNAL_WORKERS,
    build_worker_job_spec,
    external_workers_enabled,
    load_worker_result,
    worker_result_to_batch_item,
    worker_run_command,
    write_worker_job_spec,
)

SEQUENTIAL_MODE = "sequential"
PARALLEL_SAFE_MODE = "parallel_safe"
MAX_SAFE_WORKERS = 6
DEFAULT_PARALLEL_WORKERS = 2
LARGE_FILE_COUNT = 10
LARGE_WORKLOAD_SCORE = 30

AdapterFactory = Callable[[], PyForestScanAdapter]


@dataclass(frozen=True)
class BatchGuardrailReport:
    """Safety assessment for a batch execution request."""

    requested_mode: str
    effective_mode: str
    max_workers: int
    workload_score: int
    warnings: tuple[str, ...]
    blocked: bool = False
    reason: str | None = None

    @property
    def is_parallel(self) -> bool:
        """Return whether execution will use parallel safe mode."""
        return self.effective_mode == PARALLEL_SAFE_MODE and not self.blocked

    @property
    def is_external(self) -> bool:
        """Return whether execution will use external worker mode."""
        return self.effective_mode == EXTERNAL_WORKER_MODE and not self.blocked


class BatchExecutor:
    """Execute batch requests with sequential fallback and guarded parallelism."""

    def __init__(self, adapter_factory: AdapterFactory | None = None) -> None:
        """Create an executor with a per-worker adapter factory."""
        self.adapter_factory = adapter_factory or PyForestScanAdapter

    def guardrails(self, request: BatchRequest) -> BatchGuardrailReport:
        """Validate worker limits and return conservative execution guardrails."""
        mode = request.settings.execution_mode
        workers = request.settings.max_workers
        if mode not in {SEQUENTIAL_MODE, PARALLEL_SAFE_MODE, EXTERNAL_WORKER_MODE}:
            raise BatchExecutionError("Batch execution mode must be Sequential, Parallel safe mode, or External worker mode.")
        max_allowed = MAX_EXTERNAL_WORKERS if mode == EXTERNAL_WORKER_MODE else MAX_SAFE_WORKERS
        if workers < 1 or workers > max_allowed:
            raise BatchExecutionError(f"Max workers must be between 1 and {max_allowed} for this execution mode.")
        workload_score = len(request.datasets) * max(1, len(request.settings.products))
        warnings: list[str] = []
        if mode == EXTERNAL_WORKER_MODE and not external_workers_enabled():
            return BatchGuardrailReport(
                requested_mode=mode,
                effective_mode=SEQUENTIAL_MODE,
                max_workers=workers,
                workload_score=workload_score,
                warnings=(EXTERNAL_WORKER_DISABLED_MESSAGE,),
                blocked=True,
                reason=EXTERNAL_WORKER_DISABLED_MESSAGE,
            )
        if workers > DEFAULT_PARALLEL_WORKERS:
            warnings.append("More than 2 workers can increase memory, PDAL, and disk pressure.")
        if mode == EXTERNAL_WORKER_MODE:
            warnings.append("External worker mode starts separate Python processes and needs extra RAM, CPU, and disk bandwidth.")
        if len(request.datasets) >= LARGE_FILE_COUNT:
            warnings.append("Large batch: many input files selected.")
        if workload_score >= LARGE_WORKLOAD_SCORE:
            warnings.append("Large workload: many file/product combinations selected.")
        if mode == SEQUENTIAL_MODE or (workers == 1 and mode != EXTERNAL_WORKER_MODE):
            return BatchGuardrailReport(mode, SEQUENTIAL_MODE, 1, workload_score, tuple(warnings))
        if warnings and not request.settings.confirm_large_parallel:
            return BatchGuardrailReport(
                requested_mode=mode,
                effective_mode=SEQUENTIAL_MODE,
                max_workers=workers,
                workload_score=workload_score,
                warnings=tuple(warnings),
                blocked=True,
                reason="Selected non-sequential mode requires confirmation for this workload.",
            )
        return BatchGuardrailReport(mode, EXTERNAL_WORKER_MODE if mode == EXTERNAL_WORKER_MODE else PARALLEL_SAFE_MODE, workers, workload_score, tuple(warnings))

    def run(
        self,
        request: BatchRequest,
        item_callback: BatchProgressCallback | None = None,
        job_callback: BatchJobCallback | None = None,
        control_callback: BatchControlCallback | None = None,
    ) -> BatchResult:
        """Execute a batch using sequential fallback or guarded parallel safe mode."""
        if not request.datasets:
            raise BatchExecutionError("Select at least one lidar dataset for batch processing.")
        if not request.settings.products:
            raise BatchExecutionError("Select at least one product for batch processing.")
        guardrail = self.guardrails(request)
        if guardrail.blocked:
            raise BatchExecutionError(guardrail.reason or "Parallel safe mode is blocked by guardrails.")
        if guardrail.is_external:
            if not external_workers_enabled():
                raise BatchExecutionError(EXTERNAL_WORKER_DISABLED_MESSAGE)
            return self._run_external(request, guardrail, item_callback, control_callback)
        if not guardrail.is_parallel:
            return BatchRunner(
                adapter=self.adapter_factory(),
                item_callback=item_callback,
                job_callback=job_callback,
                control_callback=control_callback,
            ).run(request)
        return self._run_parallel(request, guardrail, item_callback, job_callback, control_callback)

    def _run_external(
        self,
        request: BatchRequest,
        guardrail: BatchGuardrailReport,
        item_callback: BatchProgressCallback | None,
        control_callback: BatchControlCallback | None,
    ) -> BatchResult:
        """Run batch datasets through external worker subprocesses."""
        if not external_workers_enabled():
            raise BatchExecutionError(EXTERNAL_WORKER_DISABLED_MESSAGE)
        started_at = datetime.now(timezone.utc).isoformat()
        batch_folder = request.batch_folder or create_batch_folder(request.output_folder)
        manifest_path = batch_folder / MANIFEST_NAME
        manifest = load_manifest(manifest_path) if manifest_path.exists() else create_manifest(request, batch_folder)
        write_manifest(manifest)
        batch_id = manifest.batch_id or f"pfs-batch-{uuid.uuid4().hex[:10]}"
        items: list[BatchItemResult] = []
        queued = list(request.datasets)
        running: dict[subprocess.Popen[str], tuple[Path, Path]] = {}
        stop_queue = False
        while queued or running:
            control = control_callback() if control_callback is not None else None
            if control == "cancel":
                stop_queue = True
                for process, (_dataset, _result_path) in list(running.items()):
                    if process.poll() is None:
                        process.terminate()
                for dataset in queued:
                    item = self._skipped_item(Path(dataset), batch_folder, "Cancelled before processing.")
                    items.append(item)
                    manifest = update_manifest_item(manifest, item)
                    write_manifest(manifest)
                    self._write_partial_summary(batch_id, request, batch_folder, started_at, items)
                    if item_callback is not None:
                        item_callback(item)
                queued = []
            while queued and not stop_queue and len(running) < guardrail.max_workers:
                dataset = Path(queued.pop(0))
                manifest_item = next((item for item in manifest.items if item.dataset_path == dataset), None)
                job_id = manifest_item.job_id if manifest_item is not None and manifest_item.job_id else f"pfs-file-{uuid.uuid4().hex[:10]}"
                spec = build_worker_job_spec(job_id, dataset, batch_folder, request.settings)
                spec_path = write_worker_job_spec(spec)
                process = subprocess.Popen(worker_run_command(spec_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                running[process] = (dataset, spec.result_path)
            if not running:
                break
            time.sleep(0.1)
            for process, (dataset, result_path) in list(running.items()):
                if process.poll() is None:
                    continue
                running.pop(process)
                item = self._item_from_worker_process(process, dataset, batch_folder, result_path)
                items.append(item)
                manifest = update_manifest_item(manifest, item)
                write_manifest(manifest)
                self._write_partial_summary(batch_id, request, batch_folder, started_at, items)
                if item_callback is not None:
                    item_callback(item)
                if item.status == "failed" and request.settings.stop_on_error:
                    stop_queue = True
                    for queued_dataset in queued:
                        skipped = self._skipped_item(Path(queued_dataset), batch_folder, "Skipped after stop-on-error.")
                        items.append(skipped)
                        manifest = update_manifest_item(manifest, skipped)
                        write_manifest(manifest)
                        self._write_partial_summary(batch_id, request, batch_folder, started_at, items)
                        if item_callback is not None:
                            item_callback(skipped)
                    queued = []
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

    def _item_from_worker_process(self, process: subprocess.Popen[str], dataset: Path, batch_folder: Path, result_path: Path) -> BatchItemResult:
        """Convert a completed worker process into a batch item."""
        stdout, stderr = process.communicate(timeout=1)
        if result_path.exists():
            try:
                return worker_result_to_batch_item(load_worker_result(result_path), batch_folder)
            except Exception as exc:  # noqa: BLE001 - bad worker JSON should become file failure.
                return self._failed_item(dataset, batch_folder, f"Worker result could not be read: {exc}")
        message = (stderr or stdout or f"Worker exited with code {process.returncode}").strip()
        return self._failed_item(dataset, batch_folder, message)

    def _run_parallel(
        self,
        request: BatchRequest,
        guardrail: BatchGuardrailReport,
        item_callback: BatchProgressCallback | None,
        job_callback: BatchJobCallback | None,
        control_callback: BatchControlCallback | None,
    ) -> BatchResult:
        started_at = datetime.now(timezone.utc).isoformat()
        batch_folder = request.batch_folder or create_batch_folder(request.output_folder)
        manifest_path = batch_folder / MANIFEST_NAME
        manifest = load_manifest(manifest_path) if manifest_path.exists() else create_manifest(request, batch_folder)
        write_manifest(manifest)
        batch_id = manifest.batch_id or f"pfs-batch-{uuid.uuid4().hex[:10]}"
        items: list[BatchItemResult] = []
        queued = list(request.datasets)
        running: dict[Future[BatchItemResult], Path] = {}
        stop_queue = False
        with ThreadPoolExecutor(max_workers=guardrail.max_workers, thread_name_prefix="pfs-batch") as pool:
            while queued or running:
                control = control_callback() if control_callback is not None else None
                if control == "cancel":
                    stop_queue = True
                    for dataset in queued:
                        item = self._skipped_item(Path(dataset), batch_folder, "Cancelled before processing.")
                        items.append(item)
                        manifest = update_manifest_item(manifest, item)
                        write_manifest(manifest)
                        self._write_partial_summary(batch_id, request, batch_folder, started_at, items)
                        if item_callback is not None:
                            item_callback(item)
                    queued = []
                while queued and not stop_queue and len(running) < guardrail.max_workers:
                    dataset = Path(queued.pop(0))
                    future = pool.submit(self._run_one_dataset, dataset, batch_folder, request, job_callback)
                    running[future] = dataset
                if not running:
                    break
                done, _pending = wait(tuple(running.keys()), return_when=FIRST_COMPLETED)
                for future in done:
                    dataset = running.pop(future)
                    try:
                        item = future.result()
                    except Exception as exc:  # noqa: BLE001 - per-file batch failure should be recorded.
                        item = self._failed_item(dataset, batch_folder, str(exc))
                    items.append(item)
                    manifest = update_manifest_item(manifest, item)
                    write_manifest(manifest)
                    self._write_partial_summary(batch_id, request, batch_folder, started_at, items)
                    if item_callback is not None:
                        item_callback(item)
                    if item.status == "failed" and request.settings.stop_on_error:
                        stop_queue = True
                        for queued_dataset in queued:
                            skipped = self._skipped_item(Path(queued_dataset), batch_folder, "Skipped after stop-on-error.")
                            items.append(skipped)
                            manifest = update_manifest_item(manifest, skipped)
                            write_manifest(manifest)
                            self._write_partial_summary(batch_id, request, batch_folder, started_at, items)
                            if item_callback is not None:
                                item_callback(skipped)
                        queued = []
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

    def _run_one_dataset(
        self,
        dataset: Path,
        batch_folder: Path,
        request: BatchRequest,
        job_callback: BatchJobCallback | None,
    ) -> BatchItemResult:
        runner = BatchRunner(adapter=self.adapter_factory(), job_callback=job_callback)
        return runner.run_dataset(dataset, batch_folder, request)

    def _write_partial_summary(self, batch_id: str, request: BatchRequest, batch_folder: Path, started_at: str, items: list[BatchItemResult]) -> None:
        """Write summaries after each completed, failed, or skipped file."""
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

    def _skipped_item(self, dataset: Path, batch_folder: Path, message: str) -> BatchItemResult:
        context = batch_run_context(dataset, batch_folder, reuse_existing=True).ensure_directories()
        return BatchItemResult(dataset, context, "skipped", message, (), "Not inspected")

    def _failed_item(self, dataset: Path, batch_folder: Path, message: str) -> BatchItemResult:
        context = batch_run_context(dataset, batch_folder, reuse_existing=True).ensure_directories()
        return BatchItemResult(dataset, context, "failed", message, (), "Unavailable")



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
