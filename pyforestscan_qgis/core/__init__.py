"""Core interfaces for PyForestScan QGIS."""

from __future__ import annotations

from .dependency_check import DependencyCheckResult, DependencyStatus
from .output_loader import OutputLoadRequest
from .runner import AlgorithmRunRequest

__all__ = [
    "AlgorithmRunRequest",
    "DependencyCheckResult",
    "DependencyStatus",
    "OutputLoadRequest",
]

