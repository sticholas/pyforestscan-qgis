"""Structured backend logging helpers."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .config import utc_now_iso
from .models import BackendLogEntry


def backend_log_path(operation: str, logs_dir: Path) -> Path:
    """Return the standard log path for a backend operation."""
    return logs_dir / f"backend_{operation}.log"


def write_backend_log_entry(
    log_path: Path,
    operation: str,
    message: str,
    level: str = "INFO",
    details: dict[str, Any] | None = None,
    stage: str = "",
) -> BackendLogEntry:
    """Append one compact structured JSON log line and return the entry."""
    entry = BackendLogEntry(
        timestamp=utc_now_iso(),
        level=level,
        operation=operation,
        stage=stage,
        message=message,
        details={str(key): str(value) for key, value in (details or {}).items()},
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(entry), sort_keys=True) + "\n")
    return entry


def read_backend_log(log_path: Path, limit: int = 200) -> tuple[str, ...]:
    """Read recent backend log lines if the log exists."""
    if not log_path.exists():
        return ()
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return tuple(lines[-limit:])


class BackendStructuredLogger:
    """Small operation logger used by transactions and service methods."""

    def __init__(self, log_path: Path, operation: str) -> None:
        self.log_path = log_path
        self.operation = operation

    def write(self, message: str, level: str = "INFO", stage: str = "", details: dict[str, Any] | None = None) -> BackendLogEntry:
        """Write one structured log entry."""
        return write_backend_log_entry(self.log_path, self.operation, message, level=level, details=details, stage=stage)
