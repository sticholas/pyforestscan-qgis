"""QGIS plugin lifecycle management for PyForestScan QGIS."""

from __future__ import annotations

from typing import Any

from qgis.core import QgsApplication

from .processing_provider import PyForestScanProvider


class PyForestScanPlugin:
    """Register and unregister the PyForestScan Processing provider."""

    def __init__(self, iface: Any) -> None:
        """Create the plugin lifecycle object.

        Args:
            iface: QGIS interface object supplied by the plugin loader.
        """
        self.iface = iface
        self.provider: PyForestScanProvider | None = None

    def initGui(self) -> None:
        """Register the Processing provider when QGIS enables the plugin."""
        if self.provider is None:
            self.provider = PyForestScanProvider()
            QgsApplication.processingRegistry().addProvider(self.provider)

    def unload(self) -> None:
        """Remove the Processing provider when QGIS disables the plugin."""
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None

