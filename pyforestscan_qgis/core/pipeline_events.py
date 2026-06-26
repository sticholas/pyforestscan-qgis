"""Pipeline event records for processing orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class PipelineEventLevel(str, Enum):
    """Severity levels for pipeline events."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class PipelineEvent:
    """Structured event emitted while a pipeline stage runs."""

    step_id: str
    level: PipelineEventLevel
    message: str
    timestamp: str


def pipeline_utc_now() -> str:
    """Return an ISO-8601 UTC timestamp for pipeline records."""
    return datetime.now(timezone.utc).isoformat()
