"""Immutable launch contract for standard Batch execution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .batch import BatchRequest
from .batch_preflight import BatchPreflightReport


@dataclass(frozen=True)
class BatchExecutionReadiness:
    """Validated source disposition and execution policy for one input signature."""

    selected_sources: tuple[Path, ...]
    skipped_sources: tuple[Path, ...]
    products: tuple[str, ...]
    output_root: Path
    processing_mode: str
    profile: str
    requested_concurrency_limit: int
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]
    plan_identity: str
    validated_at: str

    @property
    def ready(self) -> bool:
        return not self.blockers and bool(self.selected_sources)


@dataclass(frozen=True)
class BatchExecutionRequest:
    """Complete standard-Batch launch snapshot, independent of live widgets."""

    request: BatchRequest
    readiness: BatchExecutionReadiness
    logical_inputs: int
    sources_selected: int
    sources_skipped: int


def prepare_batch_execution(
    request: BatchRequest,
    report: BatchPreflightReport,
    *,
    profile: str = "Automatic (Recommended)",
) -> BatchExecutionRequest:
    """Freeze current validation and the exact request that it approved."""
    selected = tuple(Path(path) for path in report.files_to_process)
    skipped = tuple(Path(path) for path in report.files_to_skip)
    payload = {
        "datasets": [str(path) for path in request.datasets],
        "selected": [str(path) for path in selected],
        "skipped": [str(path) for path in skipped],
        "products": [product.value for product in request.settings.products],
        "output": str(request.output_folder),
        "mode": request.settings.execution_mode,
        "workers": request.settings.max_workers,
        "resolution": request.settings.grid_resolution,
        "profile": profile,
        "processing_spatial_contexts": report.processing_spatial_contexts,
    }
    identity = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    readiness = BatchExecutionReadiness(
        selected,
        skipped,
        tuple(product.value for product in request.settings.products),
        request.output_folder,
        request.settings.execution_mode,
        profile,
        request.settings.max_workers,
        tuple(report.warnings),
        tuple(report.blockers),
        identity,
        datetime.now(timezone.utc).isoformat(),
    )
    approved = BatchRequest(
        input_folder=request.input_folder,
        output_folder=request.output_folder,
        recursive=request.recursive,
        datasets=selected,
        settings=request.settings,
        title=request.title,
        batch_folder=report.batch_folder,
        processing_spatial_contexts=report.processing_spatial_contexts,
        runtime_token=report.runtime_token,
    )
    return BatchExecutionRequest(approved, readiness, len(selected), len(selected), len(skipped))


__all__ = ["BatchExecutionReadiness", "BatchExecutionRequest", "prepare_batch_execution"]
