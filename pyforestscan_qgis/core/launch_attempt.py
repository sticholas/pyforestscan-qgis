"""Attempt-scoped diagnostics created before polygon launch guards run."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .build_identity import session_identity


@dataclass(frozen=True)
class LaunchAttempt:
    attempt_id: str
    folder: Path
    trace_path: Path


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


def append_attempt_stage(attempt: LaunchAttempt | None, stage: str, **details: Any) -> None:
    if attempt is None:
        return
    try:
        payload = json.loads(attempt.trace_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {"attempt_id": attempt.attempt_id, "stages": []}
    entry = {"stage": stage, "at": _utc_now()}
    entry.update(details)
    payload.setdefault("stages", []).append(entry)
    if stage == "FAILED":
        payload["outcome"] = "FAILED"
    elif stage in {"COORDINATOR_STARTED", "WORKER_STARTED", "DISPATCH_STARTED"}:
        payload["outcome"] = "RUNNING"
    elif stage == "COMPLETED":
        payload["outcome"] = "COMPLETED"
    _write(attempt.trace_path, payload)
    latest = attempt.folder.parents[1] / "latest_attempt.json"
    latest_payload = {
        "attempt_id": attempt.attempt_id,
        "attempt_path": str(attempt.trace_path),
        "clicked_at": payload.get("clicked_at", ""),
        "plugin_build_id": payload.get("plugin_session_build_id", ""),
        "outcome": payload.get("outcome", "UNKNOWN"),
        "latest_stage": stage,
        "updated_at": entry["at"],
    }
    _write(latest, latest_payload)
    _write(_global_latest_attempt_path(), latest_payload)


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _global_latest_attempt_path() -> Path:
    from .backend.paths import resolve_backend_paths
    return resolve_backend_paths().backend_root / "diagnostics" / "latest_processing_attempt.json"
