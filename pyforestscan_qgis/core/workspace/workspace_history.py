"""Workspace processing history models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WorkspaceHistoryRun:
    """One recorded processing or batch run."""

    run_id: str
    products: tuple[str, ...]
    parameters: dict[str, str]
    success: bool
    output_paths: tuple[Path, ...]
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable history run data."""
        return {
            "run_id": self.run_id,
            "products": list(self.products),
            "parameters": self.parameters,
            "success": self.success,
            "output_paths": [str(path) for path in self.output_paths],
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkspaceHistoryRun":
        """Build a history run from JSON data."""
        return cls(
            run_id=str(payload.get("run_id") or "run"),
            products=tuple(str(item) for item in payload.get("products", [])),
            parameters={str(k): str(v) for k, v in (payload.get("parameters") or {}).items()},
            success=bool(payload.get("success", False)),
            output_paths=tuple(Path(item) for item in payload.get("output_paths", [])),
            started_at=payload.get("started_at"),
            finished_at=payload.get("finished_at"),
            duration_seconds=payload.get("duration_seconds"),
            error_message=payload.get("error_message"),
        )


@dataclass(frozen=True)
class WorkspaceHistory:
    """Processing history for a workspace."""

    runs: tuple[WorkspaceHistoryRun, ...] = ()

    def append(self, run: WorkspaceHistoryRun) -> "WorkspaceHistory":
        """Return history with a run prepended."""
        return WorkspaceHistory((run,) + tuple(existing for existing in self.runs if existing.run_id != run.run_id))

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable history data."""
        return {"runs": [run.to_dict() for run in self.runs]}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkspaceHistory":
        """Build history from JSON data."""
        return cls(tuple(WorkspaceHistoryRun.from_dict(item) for item in payload.get("runs", [])))
