"""Core interfaces for PyForestScan QGIS."""

from __future__ import annotations

from .adapter import AdapterProgress, PyForestScanAdapter
from .config import AdapterConfig, DatasetOpenOptions, InspectionOptions
from .dependency_check import (
    CheckStatus,
    EnvironmentCheckResult,
    EnvironmentReport,
    ReadinessStatus,
    collect_environment_report,
    format_environment_report,
)
from .exceptions import AdapterError, DatasetError, EnvironmentError, ProcessingError
from .output_loader import OutputLoadRequest
from .project import PyForestScanProject
from .runner import AlgorithmRunRequest
from .types import (
    AdapterParameter,
    Bounds3D,
    ClassificationCount,
    DatasetFormat,
    DatasetInspection,
    DatasetSource,
    DatasetValidationResult,
    LogContextItem,
    LogLevel,
    LogRecord,
    ProductRequest,
    ProductResult,
    ProductType,
    ProgressSnapshot,
    ProgressState,
)

__all__ = [
    "AdapterConfig",
    "AdapterError",
    "AdapterParameter",
    "AdapterProgress",
    "AlgorithmRunRequest",
    "Bounds3D",
    "CheckStatus",
    "ClassificationCount",
    "DatasetError",
    "DatasetFormat",
    "DatasetInspection",
    "DatasetOpenOptions",
    "DatasetSource",
    "DatasetValidationResult",
    "EnvironmentCheckResult",
    "EnvironmentError",
    "EnvironmentReport",
    "InspectionOptions",
    "LogContextItem",
    "LogLevel",
    "LogRecord",
    "OutputLoadRequest",
    "ProcessingError",
    "ProductRequest",
    "ProductResult",
    "ProductType",
    "ProgressSnapshot",
    "ProgressState",
    "PyForestScanAdapter",
    "PyForestScanProject",
    "ReadinessStatus",
    "collect_environment_report",
    "format_environment_report",
]
