"""Workspace format version metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CURRENT_WORKSPACE_FORMAT_VERSION = "1.0"


@dataclass(frozen=True)
class WorkspaceVersion:
    """Migration-ready workspace format metadata."""

    format_version: str = CURRENT_WORKSPACE_FORMAT_VERSION
    created_by: str = "pyforestscan-qgis"
    plugin_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable version metadata."""
        return {
            "format_version": self.format_version,
            "created_by": self.created_by,
            "plugin_version": self.plugin_version,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkspaceVersion":
        """Build version metadata from JSON data."""
        return cls(
            format_version=str(payload.get("format_version") or CURRENT_WORKSPACE_FORMAT_VERSION),
            created_by=str(payload.get("created_by") or "pyforestscan-qgis"),
            plugin_version=payload.get("plugin_version"),
        )
