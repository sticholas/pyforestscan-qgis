"""Reusable backend installation progress model."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BackendProgressStage(str, Enum):
    """User-facing progress stages for backend operations."""

    QUEUED = "Queued"
    DOWNLOADING = "Downloading"
    VERIFYING = "Verifying"
    EXTRACTING = "Extracting"
    INSTALLING = "Installing"
    CHECKING = "Checking"
    FINALIZING = "Finalizing"
    READY = "Ready"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


@dataclass(frozen=True)
class BackendProgressUpdate:
    """One progress update emitted by installer transactions."""

    stage: BackendProgressStage
    percentage: float | None = None
    estimated_remaining_step: str = ""
    current_package: str = ""
    message: str = ""
    warnings: tuple[str, ...] = ()
    logs: tuple[str, ...] = ()


@dataclass
class BackendProgressModel:
    """Append-only progress history for UI and tests."""

    updates: list[BackendProgressUpdate] = field(default_factory=list)

    def emit(self, update: BackendProgressUpdate) -> BackendProgressUpdate:
        """Record and return a progress update."""
        self.updates.append(update)
        return update

    def latest(self) -> BackendProgressUpdate | None:
        """Return the most recent progress update."""
        return self.updates[-1] if self.updates else None
