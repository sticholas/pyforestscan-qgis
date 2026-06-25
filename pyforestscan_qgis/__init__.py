"""QGIS plugin entry point for PyForestScan QGIS."""

from __future__ import annotations

from typing import Any


def classFactory(iface: Any) -> Any:
    """Return the QGIS plugin instance.

    QGIS calls this function when loading the plugin. The import stays inside
    the function so repository tooling can inspect this package without a QGIS
    Python environment.
    """
    from .plugin import PyForestScanPlugin

    return PyForestScanPlugin(iface)

