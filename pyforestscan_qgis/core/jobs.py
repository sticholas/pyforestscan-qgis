"""Typed job records for PyForestScan execution workflows.

The job model is intentionally independent from QGIS and PyForestScan internals.
Phase 8A supports dry-run execution only; future scientific processing should
reuse these records and status transitions through ``JobManager``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from .pipeline_results import PipelineResult


class JobStatus(str, Enum):
    """Lifecycle states for a PyForestScan job."""

    PENDING = "pending"
    VALIDATING = "validating"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    FAILED = "failed"
    COMPLETED = "completed"


class JobMode(str, Enum):
    """Supported execution modes."""

    DRY_RUN = "dry_run"


@dataclass(frozen=True)
class JobLogRecord:
    """Structured log event emitted during a job lifecycle."""

    timestamp: str
    level: str
    message: str


@dataclass(frozen=True)
class JobResultRecord:
    """File or artifact produced by a job."""

    path: Path
    result_type: str
    description: str


@dataclass(frozen=True)
class JobProgress:
    """Progress snapshot for a running job."""

    percent: float = 0.0
    message: str = "Not started"


@dataclass(frozen=True)
class JobRequest:
    """Normalized request to start a dry-run execution job."""

    product_plan_path: Path
    output_folder: Path
    title: str = "PyForestScan Dry-Run Job"
    mode: JobMode = JobMode.DRY_RUN
    summary_path: Path | None = None


@dataclass(frozen=True)
class JobRecord:
    """Immutable job state snapshot."""

    job_id: str
    title: str
    status: JobStatus
    mode: JobMode
    product_plan_path: Path
    output_folder: Path
    summary_path: Path | None
    created_at: str
    updated_at: str
    progress: JobProgress = field(default_factory=JobProgress)
    requested_products: tuple[str, ...] = ()
    logs: tuple[JobLogRecord, ...] = ()
    results: tuple[JobResultRecord, ...] = ()
    pipeline_results: tuple[PipelineResult, ...] = ()
    error_message: str | None = None

    def with_status(self, status: JobStatus, message: str | None = None) -> "JobRecord":
        """Return a copy with an updated status and optional log message."""
        record = replace(self, status=status, updated_at=utc_now())
        if message:
            record = record.with_log("INFO", message)
        return record

    def with_progress(self, percent: float, message: str) -> "JobRecord":
        """Return a copy with progress clamped to the 0-100 range."""
        bounded = max(0.0, min(100.0, float(percent)))
        return replace(
            self,
            progress=JobProgress(percent=bounded, message=message),
            updated_at=utc_now(),
        )

    def with_log(self, level: str, message: str) -> "JobRecord":
        """Return a copy with a structured log record appended."""
        entry = JobLogRecord(timestamp=utc_now(), level=level.upper(), message=message)
        return replace(self, logs=self.logs + (entry,), updated_at=entry.timestamp)

    def with_result(self, result: JobResultRecord) -> "JobRecord":
        """Return a copy with a result artifact appended."""
        return replace(self, results=self.results + (result,), updated_at=utc_now())

    def with_pipeline_results(self, results: tuple[PipelineResult, ...]) -> "JobRecord":
        """Return a copy with pipeline results replaced."""
        return replace(self, pipeline_results=results, updated_at=utc_now())

    def with_error(self, message: str) -> "JobRecord":
        """Return a failed copy with an error message and log entry."""
        record = replace(
            self,
            status=JobStatus.FAILED,
            error_message=message,
            updated_at=utc_now(),
        )
        return record.with_log("ERROR", message)


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()
