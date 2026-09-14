"""Product-neutral bounded tile execution and mosaic coordination.

The scientific adapter remains responsible for one bounded read.  This module
owns the lifecycle around that read so every raster product gets the same
checkpoint, retry, pause/cancel, and progress semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .work_unit_scheduler import CheckpointStore, PolygonProductWorkScheduler, WorkUnitResult


@dataclass(frozen=True)
class TiledExecutionResult:
    product: str
    status: str
    tile_results: tuple[WorkUnitResult, ...]
    output_path: Path | None = None
    message: str = ""


def execute_tiled_product(
    *,
    product: str,
    work_units: Iterable,
    checkpoint: CheckpointStore,
    execute_tile: Callable[[object, int], WorkUnitResult],
    mosaic_tiles: Callable[[tuple[WorkUnitResult, ...]], Path],
    concurrency: int = 1,
    retry_count: int = 2,
    transient: Callable[[Exception], bool] | None = None,
    progress_callback: Callable[[object], None] | None = None,
    control_callback: Callable[[], str | None] | None = None,
    event_callback: Callable[[dict], None] | None = None,
) -> TiledExecutionResult:
    """Execute bounded tiles and publish one terminal result for the product."""
    units = tuple(work_units)
    if not units:
        return TiledExecutionResult(product, "failed", (), message="No required tiles were planned.")
    transient_policy = transient or (lambda exc: isinstance(exc, (OSError, TimeoutError, ConnectionError)))
    scheduler = PolygonProductWorkScheduler(
        units, execute_tile, checkpoint, concurrency=max(1, int(concurrency)),
        retry_count=max(0, int(retry_count)), transient=transient_policy,
        progress_callback=progress_callback, control_callback=control_callback, event_callback=event_callback,
    )
    results = tuple(scheduler.run())
    failed = tuple(item for item in results if item.status == "Failed")
    cancelled = tuple(item for item in results if item.status == "Cancelled")
    pending = tuple(item for item in results if item.status == "Pending")
    if cancelled:
        return TiledExecutionResult(product, "cancelled", results, message="Cancelled; completed tiles remain checkpointed.")
    if pending and getattr(scheduler, "_pause", None) is not None and scheduler._pause.is_set():
        return TiledExecutionResult(product, "paused", results, message="Paused after active tiles completed.")
    if failed or pending:
        first = failed[0] if failed else pending[0]
        return TiledExecutionResult(product, "failed", results, message=f"Tile {first.work_unit_id} did not complete: {first.message}")
    output = mosaic_tiles(results)
    return TiledExecutionResult(product, "completed", results, output_path=Path(output), message=f"{len(results)} tiles mosaicked.")
