"""Batch preflight validation and resume planning."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .adapter import PyForestScanAdapter
from .batch import BatchRequest, batch_run_context, create_batch_folder
from .batch_executor import LARGE_FILE_COUNT, LARGE_WORKLOAD_SCORE, BatchExecutor, PARALLEL_SAFE_MODE
from .batch_manifest import MANIFEST_NAME, completed_dataset_paths, failed_dataset_paths, load_manifest

DiskUsageProvider = Callable[[Path], tuple[int, int, int]]


@dataclass(frozen=True)
class BatchPreflightReport:
    """Result of checking whether a batch can start safely."""

    batch_folder: Path
    ready: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    estimated_output_bytes: int
    free_disk_bytes: int
    files_to_process: tuple[Path, ...]
    files_completed: tuple[Path, ...]
    files_to_skip: tuple[Path, ...]
    files_to_retry: tuple[Path, ...]
    manifest_path: Path
    execution_mode: str
    max_workers: int

    @property
    def has_warnings(self) -> bool:
        """Return whether warnings require user acknowledgement."""
        return bool(self.warnings)


def run_batch_preflight(
    request: BatchRequest,
    adapter: PyForestScanAdapter | None = None,
    disk_usage_provider: DiskUsageProvider | None = None,
) -> BatchPreflightReport:
    """Run preflight checks before creating or resuming a batch."""
    adapter = adapter or PyForestScanAdapter()
    disk_usage_provider = disk_usage_provider or _disk_usage
    blockers: list[str] = []
    warnings: list[str] = []
    if not request.datasets:
        blockers.append("Select at least one lidar file.")
    missing = [str(path) for path in request.datasets if not Path(path).exists()]
    if missing:
        blockers.append("Missing input file(s): " + "; ".join(missing[:5]))
    if not request.settings.products:
        blockers.append("Select at least one product.")
    try:
        request.output_folder.mkdir(parents=True, exist_ok=True)
        probe = request.output_folder / ".pyforestscan_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        blockers.append(f"Output folder is not writable: {exc}")
    batch_folder = request.batch_folder or _existing_or_new_batch_folder(request)
    manifest_path = batch_folder / MANIFEST_NAME
    completed: tuple[Path, ...] = ()
    failed: tuple[Path, ...] = ()
    if manifest_path.exists():
        try:
            manifest = load_manifest(manifest_path)
            completed = completed_dataset_paths(manifest)
            failed = failed_dataset_paths(manifest)
        except (OSError, ValueError, KeyError) as exc:
            blockers.append(f"Existing batch manifest could not be read: {exc}")
    files_to_process = tuple(Path(path) for path in request.datasets)
    files_to_skip: tuple[Path, ...] = ()
    files_to_retry: tuple[Path, ...] = ()
    if request.settings.skip_completed and completed:
        files_to_skip = tuple(path for path in files_to_process if path in completed)
        files_to_process = tuple(path for path in files_to_process if path not in completed)
    if request.settings.retry_failed_only:
        files_to_retry = tuple(path for path in files_to_process if path in failed)
        files_to_process = files_to_retry
    conflicts = _output_conflicts(files_to_process, batch_folder, request.settings.overwrite_existing)
    if conflicts:
        blockers.append("Output conflicts detected: " + "; ".join(str(path) for path in conflicts[:5]))
    estimate = estimate_batch_output_bytes(request, len(files_to_process))
    try:
        free_disk = disk_usage_provider(request.output_folder)[2]
        if estimate > 0 and free_disk < int(estimate * 1.2):
            blockers.append("Free disk space is below the estimated output requirement plus safety margin.")
    except OSError as exc:
        free_disk = 0
        warnings.append(f"Free disk space could not be checked: {exc}")
    try:
        readiness = adapter.check_environment().readiness.value
        if readiness != "READY":
            blockers.append(f"Environment is {readiness}; run Environment Check before batch processing.")
    except Exception as exc:  # noqa: BLE001 - preflight reports environment uncertainty.
        warnings.append(f"Environment readiness could not be verified: {exc}")
    workload_score = len(files_to_process) * max(1, len(request.settings.products))
    if len(files_to_process) >= LARGE_FILE_COUNT:
        warnings.append("Large batch: many files selected.")
    if workload_score >= LARGE_WORKLOAD_SCORE:
        warnings.append("Large workload: many file/product combinations selected.")
    if request.settings.execution_mode == PARALLEL_SAFE_MODE:
        warnings.append("Parallel safe mode can increase memory, CPU, and disk pressure.")
    try:
        guardrail = BatchExecutor().guardrails(request)
        warnings.extend(guardrail.warnings)
        if guardrail.blocked:
            warnings.append(guardrail.reason or "Parallel safe mode requires confirmation.")
    except Exception as exc:  # noqa: BLE001 - guardrail validation is a blocker.
        blockers.append(str(exc))
    return BatchPreflightReport(
        batch_folder=batch_folder,
        ready=not blockers,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        estimated_output_bytes=estimate,
        free_disk_bytes=free_disk,
        files_to_process=files_to_process,
        files_completed=completed,
        files_to_skip=files_to_skip,
        files_to_retry=files_to_retry,
        manifest_path=manifest_path,
        execution_mode=request.settings.execution_mode,
        max_workers=request.settings.max_workers,
    )


def estimate_batch_output_bytes(request: BatchRequest, file_count: int | None = None) -> int:
    """Return conservative estimated output storage for preflight."""
    count = len(request.datasets) if file_count is None else file_count
    if count <= 0:
        return 0
    product_count = len(request.settings.products)
    # Preflight does not inspect every file. Use a deliberately conservative
    # per-product placeholder that can be replaced by calibrated estimates later.
    per_product_bytes = 128 * 1024 * 1024
    if any(product.value == "pad" for product in request.settings.products):
        per_product_bytes += 256 * 1024 * 1024
    return count * max(1, product_count) * per_product_bytes


def _existing_or_new_batch_folder(request: BatchRequest) -> Path:
    manifests = sorted(request.output_folder.glob(f"pyforestscan_batch_*/{MANIFEST_NAME}"), reverse=True)
    if manifests:
        return manifests[0].parent
    return create_batch_folder(request.output_folder)


def _output_conflicts(datasets: tuple[Path, ...], batch_folder: Path, overwrite_existing: bool) -> tuple[Path, ...]:
    if overwrite_existing:
        return ()
    conflicts: list[Path] = []
    for dataset in datasets:
        context = batch_run_context(dataset, batch_folder, reuse_existing=True)
        if context.outputs_dir.exists() and any(context.outputs_dir.iterdir()):
            conflicts.append(context.outputs_dir)
    return tuple(conflicts)


def _disk_usage(path: Path) -> tuple[int, int, int]:
    usage = shutil.disk_usage(path)
    return usage.total, usage.used, usage.free
