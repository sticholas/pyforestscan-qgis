"""Reusable backend installation progress model."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BackendProgressStage(str, Enum):
    """User-facing progress stages for backend operations."""

    QUEUED = "Queued"
    PREPARING = "Preparing"
    DOWNLOADING = "Downloading Micromamba"
    VERIFYING_DOWNLOAD = "Verifying Download"
    EXTRACTING = "Extracting"
    CREATING_ENVIRONMENT = "Creating Environment"
    INSTALLING_PACKAGES = "Installing Packages"
    VERIFYING_BACKEND = "Verifying Backend"
    FINALIZING = "Finalizing"
    READY = "Ready"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


STAGED_PROGRESS_PERCENTAGES = {
    BackendProgressStage.PREPARING: 5,
    BackendProgressStage.DOWNLOADING: 15,
    BackendProgressStage.VERIFYING_DOWNLOAD: 25,
    BackendProgressStage.EXTRACTING: 35,
    BackendProgressStage.CREATING_ENVIRONMENT: 50,
    BackendProgressStage.INSTALLING_PACKAGES: 70,
    BackendProgressStage.VERIFYING_BACKEND: 85,
    BackendProgressStage.FINALIZING: 95,
    BackendProgressStage.READY: 100,
}

STAGED_PROGRESS_ORDER = tuple(STAGED_PROGRESS_PERCENTAGES)


def backend_progress_percentage(stage: BackendProgressStage) -> int | None:
    """Return the intentionally estimated staged progress percentage."""
    return STAGED_PROGRESS_PERCENTAGES.get(stage)


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
