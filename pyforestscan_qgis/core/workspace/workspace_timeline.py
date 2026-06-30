"""Workspace timeline event models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def utc_timestamp() -> str:
    """Return a UTC ISO timestamp."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class WorkspaceTimelineEvent:
    """One timestamped workspace timeline event."""

    event_type: str
    message: str
    timestamp: str
    details: dict[str, str] | None = None

    @classmethod
    def create(cls, event_type: str, message: str, details: dict[str, str] | None = None) -> "WorkspaceTimelineEvent":
        """Create a timestamped timeline event."""
        return cls(event_type=event_type, message=message, timestamp=utc_timestamp(), details=details)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable event data."""
        return {
            "event_type": self.event_type,
            "message": self.message,
            "timestamp": self.timestamp,
            "details": self.details or {},
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkspaceTimelineEvent":
        """Build a timeline event from JSON data."""
        raw_details = payload.get("details") or {}
        return cls(
            event_type=str(payload.get("event_type") or "event"),
            message=str(payload.get("message") or ""),
            timestamp=str(payload.get("timestamp") or utc_timestamp()),
            details={str(k): str(v) for k, v in raw_details.items()} if isinstance(raw_details, dict) else {},
        )
