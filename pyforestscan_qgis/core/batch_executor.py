"""Batch execution coordinator with sequential and guarded parallel modes."""

from __future__ import annotations

import uuid
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .adapter import PyForestScanAdapter
from .batch import BatchItemResult, BatchRequest, BatchResult, batch_run_context, create_batch_folder
from .batch_results import write_batch_summaries
from .batch_runner import BatchControlCallback, BatchExecutionError, BatchJobCallback, BatchProgressCallback, BatchRunner

SEQUENTIAL_MODE = "sequential"
PARALLEL_SAFE_MODE = "parallel_safe"
MAX_SAFE_WORKERS = 4
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


class BatchExecutor:
    """Execute batch requests with sequential fallback and guarded parallelism."""

    def __init__(self, adapter_factory: AdapterFactory | None = None) -> None:
        """Create an executor with a per-worker adapter factory."""
        self.adapter_factory = adapter_factory or PyForestScanAdapter

    def guardrails(self, request: BatchRequest) -> BatchGuardrailReport:
        """Validate worker limits and return conservative execution guardrails."""
        mode = request.settings.execution_mode
        workers = request.settings.max_workers
        if workers < 1 or workers > MAX_SAFE_WORKERS:
            raise BatchExecutionError(f"Max workers must be between 1 and {MAX_SAFE_WORKERS}.")
        if mode not in {SEQUENTIAL_MODE, PARALLEL_SAFE_MODE}:
            raise BatchExecutionError("Batch execution mode must be Sequential or Parallel safe mode.")
        workload_score = len(request.datasets) * max(1, len(request.settings.products))
        warnings: list[str] = []
        if workers > DEFAULT_PARALLEL_WORKERS:
            warnings.append("More than 2 workers can increase memory, PDAL, and disk pressure.")
        if len(request.datasets) >= LARGE_FILE_COUNT:
            warnings.append("Large batch: many input files selected.")
        if workload_score >= LARGE_WORKLOAD_SCORE:
            warnings.append("Large workload: many file/product combinations selected.")
        if mode == SEQUENTIAL_MODE or workers == 1:
            return BatchGuardrailReport(mode, SEQUENTIAL_MODE, 1, workload_score, tuple(warnings))
        if warnings and not request.settings.confirm_large_parallel:
            return BatchGuardrailReport(
                requested_mode=mode,
                effective_mode=SEQUENTIAL_MODE,
                max_workers=workers,
                workload_score=workload_score,
                warnings=tuple(warnings),
                blocked=True,
                reason="Parallel safe mode requires confirmation for this workload.",
            )
        return BatchGuardrailReport(mode, PARALLEL_SAFE_MODE, workers, workload_score, tuple(warnings))

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
        if not guardrail.is_parallel:
            return BatchRunner(
                adapter=self.adapter_factory(),
                item_callback=item_callback,
                job_callback=job_callback,
                control_callback=control_callback,
            ).run(request)
        return self._run_parallel(request, guardrail, item_callback, job_callback, control_callback)

    def _run_parallel(
        self,
        request: BatchRequest,
        guardrail: BatchGuardrailReport,
        item_callback: BatchProgressCallback | None,
        job_callback: BatchJobCallback | None,
        control_callback: BatchControlCallback | None,
    ) -> BatchResult:
        started_at = datetime.now(timezone.utc).isoformat()
        batch_folder = create_batch_folder(request.output_folder)
        batch_id = f"pfs-batch-{uuid.uuid4().hex[:10]}"
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
                    if item_callback is not None:
                        item_callback(item)
                    if item.status == "failed" and request.settings.stop_on_error:
                        stop_queue = True
                        for queued_dataset in queued:
                            skipped = self._skipped_item(Path(queued_dataset), batch_folder, "Skipped after stop-on-error.")
                            items.append(skipped)
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
        )
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

    def _skipped_item(self, dataset: Path, batch_folder: Path, message: str) -> BatchItemResult:
        context = batch_run_context(dataset, batch_folder).ensure_directories()
        return BatchItemResult(dataset, context, "skipped", message, (), "Not inspected")

    def _failed_item(self, dataset: Path, batch_folder: Path, message: str) -> BatchItemResult:
        context = batch_run_context(dataset, batch_folder).ensure_directories()
        return BatchItemResult(dataset, context, "failed", message, (), "Unavailable")
