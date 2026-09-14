"""Bounded, metadata-only diagnostics for one spatial work unit.

The diagnostics deliberately record counts, dimensions and ranges rather than
point coordinates.  They are shared by the adapter and tiled coordinator so
an empty result can be classified without turning a scientific condition into
an invented Python exception.
"""
from __future__ import annotations

import json
import math
import threading
import os
import uuid
import inspect
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .exceptions import ProcessingError
from .atomic_state import atomic_write_json

_PATH_LOCKS: dict[str, threading.RLock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


def _path_lock(path: Path) -> threading.RLock:
    key = str(path.absolute()).casefold()
    with _PATH_LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(key, threading.RLock())


EMPTY_EPT_READ = "EMPTY_EPT_READ"
EMPTY_AFTER_POLYGON_CLIP = "EMPTY_AFTER_POLYGON_CLIP"
EMPTY_AFTER_HEIGHT_PREPARATION = "EMPTY_AFTER_HEIGHT_PREPARATION"
EMPTY_CHM_INPUT = "EMPTY_CHM_INPUT"
EMPTY_VOXEL_INPUT = "EMPTY_VOXEL_INPUT"
MISSING_REQUIRED_DIMENSION = "MISSING_REQUIRED_DIMENSION"
CRS_CLIP_MISMATCH = "CRS_CLIP_MISMATCH"

# Required fields are written before a scientific artifact is published;
# optional telemetry is best-effort and must never turn a successful tile into
# a failed tile.
DIAGNOSTICS_REQUIRED = frozenset({"REQUEST", "EPT_READ_COMPLETED", "VOXEL_STAT_INPUT_VALIDATED", "TILE_VALIDATED"})
DIAGNOSTICS_BEST_EFFORT = frozenset({"EPT_READ_STARTED", "POLYGON_CLIP_STARTED", "POLYGON_CLIP_COMPLETED", "HEIGHT_PREPARATION_COMPLETED", "VOXEL_STAT_STARTED", "VOXEL_STAT_COMPLETED", "TILE_RASTER_WRITTEN"})


class ScientificConditionError(ProcessingError):
    """A deterministic scientific condition, not an unexpected exception."""

    failure_kind = "SCIENTIFIC_CONDITION"

    def __init__(self, code: str, message: str, *, stage: str, diagnostics: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.stage = stage
        self.diagnostics = diagnostics or {}
        self.traceback = None


def _finite_range(values: Any) -> list[float] | None:
    try:
        finite = [float(value) for value in values if math.isfinite(float(value))]
    except (TypeError, ValueError):
        return None
    return [min(finite), max(finite)] if finite else None


def point_array_summary(point_array: Any) -> dict[str, Any]:
    """Return bounded metadata for a structured point array."""
    names = list(getattr(getattr(point_array, "dtype", None), "names", ()) or ())
    summary: dict[str, Any] = {"point_count": int(getattr(point_array, "shape", (0,))[0] if hasattr(point_array, "shape") else len(point_array)), "dimensions": names}
    for name in ("X", "Y", "Z", "HeightAboveGround"):
        if name in names:
            try:
                values = point_array[name]
                summary[f"{name}_range"] = _finite_range(values)
                summary[f"{name}_finite_count"] = int(sum(math.isfinite(float(value)) for value in values))
            except (TypeError, ValueError):
                summary[f"{name}_range"] = None
    if "Classification" in names:
        try:
            counts: dict[str, int] = {}
            for value in point_array["Classification"]:
                key = str(int(value))
                counts[key] = counts.get(key, 0) + 1
            summary["classification_counts"] = counts
        except (TypeError, ValueError):
            summary["classification_counts"] = {}
    summary["height_above_ground_present"] = "HeightAboveGround" in names
    return summary


def write_stage_record(path: Path | str | None, *, stage: str, payload: dict[str, Any]) -> None:
    """Append an immutable event and atomically publish the latest summary.

    ``path`` remains accepted for compatibility, but callers should pass an
    attempt-scoped path.  The event log is append-only, so retries/processes
    never compete by rewriting one shared history file.
    """
    if not path:
        return
    target = Path(path)
    # Backend contracts pass a diagnostics directory; normalize that form to
    # the attempt-local summary file.  Never call mkdir on a JSON path.
    if target.exists() and target.is_dir() or target.suffix.lower() != ".json":
        target = target / "tile_diagnostics.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    with _path_lock(target):
        event = {"schema": "pyforestscan-tile-event-v1", "stage": stage,
                 "payload": payload, "timestamp": datetime.now(timezone.utc).isoformat(),
                 "pid": os.getpid(), "thread": threading.get_ident()}
        try:
            events = target.parent / "events.jsonl"
            with events.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, sort_keys=True, default=str) + "\n")
        except OSError as exc:
            _write_filesystem_failure(target, stage, exc)
            return
        try:
            record = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
        except (OSError, ValueError):
            record = {}
        record.setdefault("schema", "pyforestscan-tile-diagnostics-v1")
        record.setdefault("event_count", 0)
        record["event_count"] += 1
        record["last_event"] = event
        record.setdefault("stages", {})[stage] = payload
        # atomic_write_json uses a unique same-directory temporary file and
        # os.replace(), which is safe when the destination already exists on
        # Windows and Linux.  Telemetry failure is intentionally best-effort;
        # it must not invalidate a completed scientific artifact.
        try:
            atomic_write_json(target, record)
        except OSError as exc:
            _write_filesystem_failure(target, stage, exc)
            return


def _write_filesystem_failure(target: Path, stage: str, exc: OSError) -> None:
    """Persist writer failures outside the active work-unit diagnostics path."""
    try:
        run_folder = target.parents[4]
        frame = inspect.currentframe()
        callsite = f"{frame.f_code.co_filename}:{frame.f_lineno}" if frame else ""
        payload = {
            "operation": "atomic_write_json/os.replace",
            "stage": stage,
            "destination": str(target),
            "destination_exists_before": target.exists(),
            "destination_is_file": target.is_file(),
            "destination_is_dir": target.is_dir(),
            "pid": os.getpid(),
            "thread": threading.get_ident(),
            "exception_type": type(exc).__name__,
            "errno": getattr(exc, "errno", None),
            "winerror": getattr(exc, "winerror", None),
            "message": str(exc),
            "callsite": callsite,
        }
        atomic_write_json(run_folder / "diagnostics" / f"filesystem_failure_{uuid.uuid4().hex}.json", payload)
    except OSError:
        return


def classify_empty(*, point_count: int, stage: str, expected_source_coverage: str = "unknown") -> tuple[str, bool]:
    """Classify an empty boundary and whether it is safe to represent as NoData."""
    if point_count > 0:
        return "", False
    if stage == "EPT_READ":
        return EMPTY_EPT_READ, str(expected_source_coverage).lower() not in {"expected", "required"}
    if stage == "POLYGON_CLIP":
        return EMPTY_AFTER_POLYGON_CLIP, True
    if stage == "HEIGHT_PREPARATION":
        return EMPTY_AFTER_HEIGHT_PREPARATION, False
    if stage == "CHM":
        return EMPTY_CHM_INPUT, False
    return EMPTY_VOXEL_INPUT, False
