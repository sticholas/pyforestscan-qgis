"""Core interfaces for PyForestScan QGIS."""

from __future__ import annotations

from .adapter import AdapterProgress, PyForestScanAdapter
from .config import AdapterConfig, DatasetOpenOptions, InspectionOptions
from .dataset_report import (
    DatasetExplorerReport,
    DatasetWarning,
    ProductFeasibility,
    build_dataset_explorer_report,
    format_count_for_display,
    format_crs_for_display,
    format_density_for_display,
    render_html_report,
    render_json_report,
    report_to_dict,
    write_csv_summary,
    write_html_report,
    write_json_report,
)
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
    "DatasetExplorerReport",
    "DatasetWarning",
    "ProductFeasibility",
    "build_dataset_explorer_report",
    "render_html_report",
    "render_json_report",
    "report_to_dict",
    "write_csv_summary",
    "write_html_report",
    "write_json_report",
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
    "format_count_for_display",
    "format_crs_for_display",
    "format_density_for_display",
    "format_environment_report",
]
