"""Recover scientifically complete polygon jobs without rerunning LiDAR work."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from .atomic_state import atomic_write_json
from .output_registry import generated_output_for_path, write_output_registry


@dataclass(frozen=True)
class FinalizationRecoveryResult:
    recovered: bool
    state: str
    message: str
    completed_work_units: int
    skipped_work_units: int
    outputs: tuple[Path, ...] = ()
    registry_path: Path | None = None


def validate_raster(path: Path) -> tuple[bool, dict[str, object]]:
    """Validate a final raster using the managed runtime's rasterio stack."""
    if not path.is_file() or path.stat().st_size <= 0:
        return False, {"path": str(path), "error": "missing or empty"}
    try:
        import rasterio

        with rasterio.open(path) as dataset:
            valid = bool(dataset.count and dataset.width and dataset.height and dataset.crs)
            details = {
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "openable": True,
                "width": dataset.width,
                "height": dataset.height,
                "bands": dataset.count,
                "crs": str(dataset.crs),
                "bounds": tuple(dataset.bounds),
                "nodata": dataset.nodata,
                "transform": tuple(dataset.transform),
            }
            return valid, details
    except Exception as exc:  # noqa: BLE001 - recovery must preserve diagnostics.
        return False, {"path": str(path), "openable": False, "error": str(exc)}


def recover_completed_polygon_job(
    run_folder: Path | str,
    *,
    batch_folder: Path | str,
    job_id: str,
    attempt_id: str,
    required_work_unit_ids: Iterable[str],
    requested_products: Iterable[str],
    plan_signature: str = "",
    raster_validator: Callable[[Path], tuple[bool, dict[str, object]]] = validate_raster,
) -> FinalizationRecoveryResult:
    """Repair presentation state only when every required scientific unit is complete."""
    run_root = Path(run_folder)
    required = tuple(dict.fromkeys(str(value) for value in required_work_unit_ids))
    completed: set[str] = set()
    skipped = 0
    statuses: list[dict[str, object]] = []
    for status_path in sorted((run_root / "work_units").glob("wu-*/status.json")):
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        unit_id = str(status.get("work_unit_id") or status_path.parent.name)
        state = str(status.get("status", ""))
        statuses.append({"work_unit_id": unit_id, "status": state, "path": str(status_path)})
        if state in {"Complete", "CompleteNoData"}:
            completed.add(unit_id)
        elif state == "SkippedOutsidePolygon":
            skipped += 1
    missing = tuple(unit_id for unit_id in required if unit_id not in completed)
    if missing:
        return FinalizationRecoveryResult(False, "FAILED", f"Scientific work is incomplete: {', '.join(missing)}", len(completed), skipped)

    products = tuple(dict.fromkeys(str(value).lower() for value in requested_products))
    output_paths = tuple(run_root / "outputs" / f"{product}.tif" for product in products if product in {"chm", "rumple"})
    validation = []
    for output in output_paths:
        valid, details = raster_validator(output)
        validation.append({"product": output.stem, "valid": valid, **details})
    if not output_paths or not all(item["valid"] for item in validation):
        atomic_write_json(run_root / "diagnostics" / "finalization_recovery.json", {"recovered": False, "statuses": statuses, "validation": validation})
        return FinalizationRecoveryResult(False, "FAILED", "Final scientific outputs did not pass recovery validation.", len(completed), skipped)

    summary = run_root / "outputs" / "rumple_summary.csv"
    all_outputs = (*output_paths, *((summary,) if summary.is_file() else ()))
    registry = write_output_registry(
        (
            generated_output_for_path(
                path,
                job_id=job_id,
                attempt_id=attempt_id,
                source_mode="polygon_area_processing",
                masked=True,
                plan_signature=plan_signature,
            )
            for path in all_outputs
        ),
        Path(batch_folder),
    )
    recovered_at = datetime.now(timezone.utc).isoformat()
    terminal = {
        "job_id": job_id,
        "attempt_id": attempt_id,
        "state": "complete_with_warning",
        "completion_code": "SCIENCE_COMPLETE_FINALIZATION_REPAIRED",
        "completed": len(completed),
        "skipped_outside_polygon": skipped,
        "outputs": [str(path) for path in all_outputs],
        "registry_path": str(registry),
        "finished_at": recovered_at,
        "warning": "Scientific outputs were complete; presentation state was repaired without recalculation.",
    }
    coordinator = run_root / "coordinator"
    atomic_write_json(coordinator / "terminal_result.json", terminal)
    atomic_write_json(coordinator / "heartbeat.json", {"job_id": job_id, "attempt_id": attempt_id, "state": "complete_with_warning", "active": False, "stopped_at": recovered_at, "timestamp": recovered_at})
    atomic_write_json(run_root / "diagnostics" / "finalization_recovery.json", {"recovered": True, "statuses": statuses, "validation": validation, "terminal": terminal})
    return FinalizationRecoveryResult(True, "SCIENCE_COMPLETE_FINALIZATION_REPAIRED", terminal["warning"], len(completed), skipped, tuple(all_outputs), registry)


__all__ = ["FinalizationRecoveryResult", "recover_completed_polygon_job", "validate_raster"]
