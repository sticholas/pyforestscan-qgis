"""Attempt-scoped diagnostics created before polygon launch guards run."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .build_identity import session_identity


_TRACE_LOCK = threading.RLock()


@dataclass(frozen=True)
class LaunchAttempt:
    attempt_id: str
    folder: Path
    trace_path: Path


def read_attempt_status(attempt: LaunchAttempt | None, stall_after_seconds: int = 30) -> dict[str, Any]:
    """Return a compact launch snapshot without mutating durable state."""
    if attempt is None:
        return {"outcome": "UNKNOWN", "stage": "", "elapsed_ms": 0, "stalled": False}
    try:
        with _TRACE_LOCK:
            payload = json.loads(attempt.trace_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"outcome": "UNKNOWN", "stage": "", "elapsed_ms": 0, "stalled": False}
    stages = list(payload.get("stages", ()))
    latest = stages[-1] if stages else {}
    visible_stage = latest.get("active_stage", "") if latest.get("stage") == "HEARTBEAT" else latest.get("stage", "")
    ownership = any(item.get("stage") in {"WORKER_STARTED", "COORDINATOR_PROCESS_CREATED", "COORDINATOR_STARTED", "FIRST_WORKER_STARTED"} for item in stages)
    elapsed = _elapsed_ms(payload.get("clicked_at"))
    return {
        "outcome": payload.get("outcome", "UNKNOWN"),
        "stage": visible_stage,
        "operation": latest.get("operation", ""),
        "elapsed_ms": elapsed,
        "stalled": not ownership and elapsed >= stall_after_seconds * 1000,
    }


def create_launch_attempt(batch_folder: Path, products: tuple[str, ...], plan_signature: str = "") -> LaunchAttempt:
    """Create fresh evidence immediately after Process LiDAR is clicked."""
    attempt_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:8]}"
    folder = Path(batch_folder) / "attempts" / attempt_id
    trace = folder / "launch_attempt.json"
    identity = session_identity()
    payload = {
        "attempt_id": attempt_id,
        "clicked_at": _utc_now(),
        "plugin_session_build_id": identity.build_id,
        "plugin_session_commit": identity.git_commit,
        "plugin_root": str(identity.plugin_root),
        "critical_module_hashes": identity.actual_hashes,
        "requested_products": list(products),
        "plan_signature": plan_signature,
        "stages": [{"stage": "PROCESS_CLICKED", "at": _utc_now()}],
        "outcome": "STARTING",
    }
    _write(trace, payload)
    _write(Path(batch_folder) / "latest_attempt.json", {
        "attempt_id": attempt_id,
        "attempt_path": str(trace),
        "clicked_at": payload["clicked_at"],
        "plugin_build_id": identity.build_id,
        "outcome": "STARTING",
    })
    _write(_global_latest_attempt_path(), {
        "attempt_id": attempt_id,
        "attempt_path": str(trace),
        "clicked_at": payload["clicked_at"],
        "plugin_build_id": identity.build_id,
        "outcome": "STARTING",
    })
    return LaunchAttempt(attempt_id, folder, trace)


def append_attempt_stage(attempt: LaunchAttempt | None, stage: str, **details: Any) -> bool:
    """Append diagnostics without allowing diagnostics to abort processing."""
    if attempt is None:
        return True
    try:
        with _TRACE_LOCK:
            try:
                payload = json.loads(attempt.trace_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                payload = {"attempt_id": attempt.attempt_id, "stages": []}
            entry = {
                "stage": stage, "at": _utc_now(),
                "elapsed_ms": _elapsed_ms(payload.get("clicked_at")),
                "process_id": os.getpid(), "thread_id": threading.get_ident(),
                "qgis_main_thread": threading.current_thread() is threading.main_thread(),
            }
            entry.update(details)
            payload.setdefault("stages", []).append(entry)
            if stage == "FAILED": payload["outcome"] = "FAILED"
            elif stage == "CANCELLED": payload["outcome"] = "CANCELLED"
            elif stage in {"COORDINATOR_PROCESS_CREATED", "COORDINATOR_STARTED", "FIRST_WORKER_STARTED"}: payload["outcome"] = "RUNNING"
            elif stage == "FINALIZING": payload["outcome"] = "FINALIZING"
            elif stage == "COMPLETED": payload["outcome"] = "COMPLETED"
            elif payload.get("outcome") in {None, "STARTING"}: payload["outcome"] = "LAUNCHING"
            _write(attempt.trace_path, payload)
            latest_payload = {
                "attempt_id": attempt.attempt_id, "attempt_path": str(attempt.trace_path),
                "clicked_at": payload.get("clicked_at", ""), "plugin_build_id": payload.get("plugin_session_build_id", ""),
                "outcome": payload.get("outcome", "UNKNOWN"), "latest_stage": stage,
                "updated_at": entry["at"], "elapsed_ms": entry["elapsed_ms"],
            }
            _write(attempt.folder.parents[1] / "latest_attempt.json", latest_payload)
            _write(_global_latest_attempt_path(), latest_payload)
        return True
    except OSError:
        return False


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _elapsed_ms(clicked_at: Any) -> int:
    try:
        clicked = datetime.fromisoformat(str(clicked_at))
        return max(0, int((datetime.now(timezone.utc) - clicked).total_seconds() * 1000))
    except (TypeError, ValueError):
        return int(time.monotonic() * 1000)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _global_latest_attempt_path() -> Path:
    from .backend.paths import resolve_backend_paths
    return resolve_backend_paths().backend_root / "diagnostics" / "latest_processing_attempt.json"
