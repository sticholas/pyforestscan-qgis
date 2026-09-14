"""Typed ownership and terminal-state contracts for managed coordinators."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


TERMINAL_STATUSES = frozenset({"SUCCEEDED", "PARTIAL_SUCCESS", "FAILED", "CANCELLED"})


@dataclass(frozen=True)
class CoordinatorHandle:
    """Attempt-scoped paths and live process ownership for one coordinator."""

    attempt_id: str
    pid: int
    process: subprocess.Popen[Any] | None
    started_at: str
    request_path: Path
    progress_path: Path
    terminal_result_path: Path
    cancel_path: Path
    pause_path: Path
    identity_path: Path
    stdout_path: Path
    stderr_path: Path

    def poll(self) -> int | None:
        return None if self.process is None else self.process.poll()


@dataclass(frozen=True)
class CoordinatorLaunchResult:
    """Successful process creation, explicitly distinct from job success."""

    spawn_succeeded: bool
    pid: int
    command: tuple[str, ...]
    handle: CoordinatorHandle

    def __iter__(self) -> Iterator[object]:
        """Preserve legacy tuple unpacking while callers migrate to the handle."""
        yield self.pid
        yield list(self.command)


@dataclass(frozen=True)
class CoordinatorTerminalResult:
    """Validated durable terminal result emitted by a coordinator."""

    attempt_id: str
    status: str
    result_path: Path | None
    datasets: dict[str, str]
    products: dict[str, str]
    outputs: tuple[str, ...]
    finished_at: str
    exit_code: int | None
    error: str = ""

    @classmethod
    def read(cls, path: Path, expected_attempt_id: str) -> "CoordinatorTerminalResult":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"COORDINATOR_RESULT_INVALID: {exc}") from exc
        attempt_id = str(payload.get("attempt_id", ""))
        if attempt_id != expected_attempt_id:
            raise RuntimeError(
                f"COORDINATOR_RESULT_ATTEMPT_MISMATCH: expected {expected_attempt_id}, found {attempt_id or 'missing'}"
            )
        status = str(payload.get("status", "")).upper()
        if status not in TERMINAL_STATUSES:
            raise RuntimeError(f"COORDINATOR_RESULT_INVALID: unsupported status {status or 'missing'}")
        result_path = Path(payload["result_path"]) if payload.get("result_path") else None
        return cls(
            attempt_id=attempt_id, status=status, result_path=result_path,
            datasets={str(k): str(v) for k, v in dict(payload.get("datasets", {})).items()},
            products={str(k): str(v) for k, v in dict(payload.get("products", {})).items()},
            outputs=tuple(str(item) for item in payload.get("outputs", ())),
            finished_at=str(payload.get("finished_at", "")),
            exit_code=payload.get("exit_code"), error=str(payload.get("error", "")),
        )


def build_coordinator_handle(attempt_id: str, process, request_path: Path, job_dir: Path, stdout_path: Path, stderr_path: Path) -> CoordinatorHandle:
    """Build a handle only after the OS process has been created."""
    return CoordinatorHandle(
        attempt_id=attempt_id, pid=int(process.pid), process=process,
        started_at=datetime.now(timezone.utc).isoformat(), request_path=Path(request_path),
        progress_path=job_dir / "progress_snapshot.json",
        terminal_result_path=job_dir / "coordinator_result.json",
        cancel_path=job_dir / "cancel_requested.json", pause_path=job_dir / "pause_requested.json",
        identity_path=job_dir / "coordinator_identity.json",
        stdout_path=stdout_path, stderr_path=stderr_path,
    )


def bounded_process_output(path: Path, max_lines: int = 6) -> str:
    """Read bounded first/last process diagnostics without pipe buffering."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    if len(lines) <= max_lines * 2:
        return "\n".join(lines)
    return "\n".join([*lines[:max_lines], "...", *lines[-max_lines:]])
