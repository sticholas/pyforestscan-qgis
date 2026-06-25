"""Backward-compatible provider import location.

The canonical provider implementation lives in `processing_provider.py`.
This module keeps the short `provider.py` import path available for QGIS plugin
conventions and future maintainers.
"""

from __future__ import annotations

from .processing_provider import PyForestScanProvider

__all__ = ["PyForestScanProvider"]

