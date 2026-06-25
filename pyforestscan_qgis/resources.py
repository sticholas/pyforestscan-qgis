"""Resource helpers for PyForestScan QGIS."""

from __future__ import annotations

from pathlib import Path

from qgis.PyQt.QtGui import QIcon


def plugin_root() -> Path:
    """Return the plugin package directory."""
    return Path(__file__).resolve().parent


def icon_path(name: str = "pyforestscan.svg") -> Path:
    """Return an icon path inside the plugin package."""
    return plugin_root() / "icons" / name


def plugin_icon() -> QIcon:
    """Return the plugin icon without relying on hardcoded absolute paths."""
    return QIcon(str(icon_path()))

