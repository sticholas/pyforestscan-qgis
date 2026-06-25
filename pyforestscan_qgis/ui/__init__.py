"""Mission Control user-interface package for PyForestScan QGIS."""

from __future__ import annotations

from typing import Any

__all__ = ["MissionControlDock"]


def __getattr__(name: str) -> Any:
    """Lazily import QGIS UI classes so pure state tests do not require QGIS."""
    if name == "MissionControlDock":
        from .mission_control import MissionControlDock

        return MissionControlDock
    raise AttributeError(name)
