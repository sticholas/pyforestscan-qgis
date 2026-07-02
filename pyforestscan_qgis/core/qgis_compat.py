"""QGIS compatibility helpers for PyForestScan QGIS.

This module is safe to import outside QGIS. Runtime QGIS imports are guarded so
plain-Python tests can exercise version parsing and graceful failure behavior.
"""

from __future__ import annotations

import platform as platform_module
import sys
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QgisCompatibilityReport:
    """Detected QGIS/Python/Qt compatibility information."""

    qgis_version: str
    major_version: int | None
    python_version: str
    qt_version: str
    platform: str
    plugin_api_available: bool
    processing_provider_compatible: bool
    settings_available: bool
    message_log_available: bool
    supported_target: bool
    warnings: tuple[str, ...] = ()

    def summary(self) -> str:
        """Return a compact user-facing compatibility summary."""
        if self.supported_target and not self.warnings:
            return f"QGIS {self.qgis_version} compatibility checks passed."
        if self.supported_target:
            return f"QGIS {self.qgis_version} is usable with warnings."
        return f"QGIS compatibility could not be fully confirmed for {self.qgis_version}."


@dataclass(frozen=True)
class QgisOperationResult:
    """Result from a guarded QGIS API operation."""

    success: bool
    message: str
    object_ref: Any | None = None


def parse_qgis_major(version: str | None) -> int | None:
    """Parse the major QGIS version from strings such as ``3.44.1`` or ``4.0``."""
    if not version:
        return None
    token = str(version).strip().split()[0]
    if not token:
        return None
    try:
        return int(token.split(".", 1)[0])
    except ValueError:
        return None


def build_qgis_compatibility_report(
    qgis_version: str | None = None,
    python_version: str | None = None,
    qt_version: str | None = None,
    platform_name: str | None = None,
    qgis_core: Any | None = None,
    qt_core: Any | None = None,
) -> QgisCompatibilityReport:
    """Build a defensive QGIS compatibility report without requiring QGIS."""
    core = qgis_core
    qt = qt_core
    qgis_import_error = ""
    qt_import_error = ""

    if core is None:
        try:
            from qgis import core as imported_core  # type: ignore

            core = imported_core
        except Exception as exc:  # noqa: BLE001 - compatibility reports must not crash.
            qgis_import_error = str(exc)

    if qt is None:
        try:
            from qgis.PyQt import QtCore as imported_qt_core  # type: ignore

            qt = imported_qt_core
        except Exception as exc:  # noqa: BLE001 - compatibility reports must not crash.
            qt_import_error = str(exc)

    detected_qgis_version = qgis_version or _detect_qgis_version(core) or "Unavailable"
    detected_qt_version = qt_version or _detect_qt_version(qt) or "Unavailable"
    major = parse_qgis_major(detected_qgis_version)

    plugin_api_available = _has_any(core, ("Qgis", "QgsApplication", "QgsProject"))
    processing_provider_compatible = _has_processing_provider_support(core)
    settings_available = qt is not None and hasattr(qt, "QSettings")
    message_log_available = core is not None and hasattr(core, "QgsMessageLog")

    warnings: list[str] = []
    if core is None:
        detail = f" Import error: {qgis_import_error}" if qgis_import_error else ""
        warnings.append("QGIS Python API is unavailable in this interpreter. Run inside QGIS for full compatibility checks." + detail)
    if qt is None:
        detail = f" Import error: {qt_import_error}" if qt_import_error else ""
        warnings.append("Qt API is unavailable in this interpreter." + detail)
    if major is None:
        warnings.append("QGIS major version could not be parsed.")
    elif major < 3:
        warnings.append("QGIS versions earlier than 3.x are not supported targets.")
    elif major == 4:
        warnings.append("QGIS 4.x is a defensive compatibility target and must be validated when available.")
    elif major > 4:
        warnings.append(f"QGIS {major}.x is outside the tested compatibility target range.")
    if not processing_provider_compatible:
        warnings.append("Processing provider registration APIs were not detected.")
    if not settings_available:
        warnings.append("Qt settings access was not detected.")
    if not message_log_available:
        warnings.append("QGIS message log API was not detected.")

    supported_target = bool(plugin_api_available and processing_provider_compatible and major in (3, 4))
    return QgisCompatibilityReport(
        qgis_version=detected_qgis_version,
        major_version=major,
        python_version=python_version or sys.version.split()[0],
        qt_version=detected_qt_version,
        platform=platform_name or platform_module.platform(),
        plugin_api_available=plugin_api_available,
        processing_provider_compatible=processing_provider_compatible,
        settings_available=settings_available,
        message_log_available=message_log_available,
        supported_target=supported_target,
        warnings=tuple(warnings),
    )


def format_qgis_compatibility_report(report: QgisCompatibilityReport) -> str:
    """Format compatibility details for Mission Control."""
    lines = [
        "QGIS Compatibility",
        f"Status: {report.summary()}",
        f"QGIS version: {report.qgis_version}",
        f"Major version: {report.major_version if report.major_version is not None else 'Unknown'}",
        f"Python version: {report.python_version}",
        f"Qt version: {report.qt_version}",
        f"Platform: {report.platform}",
        f"Plugin API available: {_yes_no(report.plugin_api_available)}",
        f"Processing provider compatible: {_yes_no(report.processing_provider_compatible)}",
        f"Settings API available: {_yes_no(report.settings_available)}",
        f"Message log available: {_yes_no(report.message_log_available)}",
    ]
    if report.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in report.warnings)
    return "\n".join(lines)


def add_raster_layer(path: str, name: str, project: Any | None = None) -> QgisOperationResult:
    """Safely add a raster layer to the current QGIS project."""
    try:
        from qgis.core import QgsProject, QgsRasterLayer  # type: ignore
    except Exception as exc:  # noqa: BLE001
        return QgisOperationResult(False, f"QGIS raster APIs are unavailable: {exc}")
    layer = QgsRasterLayer(str(path), name)
    if hasattr(layer, "isValid") and not layer.isValid():
        return QgisOperationResult(False, f"Raster layer is not valid: {path}", layer)
    target_project = project or QgsProject.instance()
    if not hasattr(target_project, "addMapLayer"):
        return QgisOperationResult(False, "QGIS project cannot add map layers in this runtime.", layer)
    target_project.addMapLayer(layer)
    return QgisOperationResult(True, f"Raster layer added: {name}", layer)


def add_vector_or_table_layer(path: str, name: str, provider_name: str = "ogr", project: Any | None = None) -> QgisOperationResult:
    """Safely add a vector or table layer to the current QGIS project."""
    try:
        from qgis.core import QgsProject, QgsVectorLayer  # type: ignore
    except Exception as exc:  # noqa: BLE001
        return QgisOperationResult(False, f"QGIS vector/table APIs are unavailable: {exc}")
    layer = QgsVectorLayer(str(path), name, provider_name)
    if hasattr(layer, "isValid") and not layer.isValid():
        return QgisOperationResult(False, f"Vector/table layer is not valid: {path}", layer)
    target_project = project or QgsProject.instance()
    if not hasattr(target_project, "addMapLayer"):
        return QgisOperationResult(False, "QGIS project cannot add map layers in this runtime.", layer)
    target_project.addMapLayer(layer)
    return QgisOperationResult(True, f"Vector/table layer added: {name}", layer)


def open_or_raise_mission_control(widget: Any) -> QgisOperationResult:
    """Show and raise a Mission Control widget when the available Qt API supports it."""
    if widget is None:
        return QgisOperationResult(False, "Mission Control widget is not available.")
    called: list[str] = []
    for method_name in ("show", "raise_", "activateWindow"):
        method = getattr(widget, method_name, None)
        if callable(method):
            try:
                method()
                called.append(method_name)
            except Exception as exc:  # noqa: BLE001
                return QgisOperationResult(False, f"Mission Control {method_name} failed: {exc}", widget)
    if not called:
        return QgisOperationResult(False, "Mission Control widget has no show/raise API.", widget)
    return QgisOperationResult(True, "Mission Control opened.", widget)


def register_processing_provider(provider: Any, registry: Any | None = None) -> QgisOperationResult:
    """Safely register a QGIS Processing provider."""
    target_registry = registry or _processing_registry()
    if target_registry is None or not hasattr(target_registry, "addProvider"):
        return QgisOperationResult(False, "QGIS Processing registry is unavailable.", provider)
    try:
        target_registry.addProvider(provider)
    except Exception as exc:  # noqa: BLE001
        return QgisOperationResult(False, f"Processing provider registration failed: {exc}", provider)
    return QgisOperationResult(True, "Processing provider registered.", provider)


def unregister_processing_provider(provider: Any, registry: Any | None = None) -> QgisOperationResult:
    """Safely unregister a QGIS Processing provider."""
    target_registry = registry or _processing_registry()
    if target_registry is None or not hasattr(target_registry, "removeProvider"):
        return QgisOperationResult(False, "QGIS Processing registry is unavailable.", provider)
    try:
        target_registry.removeProvider(provider)
    except Exception as exc:  # noqa: BLE001
        return QgisOperationResult(False, f"Processing provider removal failed: {exc}", provider)
    return QgisOperationResult(True, "Processing provider removed.", provider)


def qgis_settings() -> QgisOperationResult:
    """Return a guarded QSettings object for plugin settings access."""
    try:
        from qgis.PyQt.QtCore import QSettings  # type: ignore
    except Exception as exc:  # noqa: BLE001
        return QgisOperationResult(False, f"QGIS Qt settings API is unavailable: {exc}")
    try:
        return QgisOperationResult(True, "QGIS settings available.", QSettings())
    except Exception as exc:  # noqa: BLE001
        return QgisOperationResult(False, f"QGIS settings could not be opened: {exc}")


def report_message(message: str, level: str = "INFO", tag: str = "PyForestScan") -> QgisOperationResult:
    """Report a message through QGIS logging when available."""
    try:
        from qgis.core import Qgis, QgsMessageLog  # type: ignore
    except Exception as exc:  # noqa: BLE001
        return QgisOperationResult(False, f"QGIS message log is unavailable: {exc}")
    qgis_level = _qgis_message_level(Qgis, level)
    try:
        QgsMessageLog.logMessage(message, tag, qgis_level)
    except Exception as exc:  # noqa: BLE001
        return QgisOperationResult(False, f"QGIS message logging failed: {exc}")
    return QgisOperationResult(True, "Message written to QGIS log.")


def _qgis_message_level(qgis_class: Any, level: str) -> Any:
    normalized = level.strip().lower()
    candidates = {
        "critical": ("Critical", "CRITICAL"),
        "warning": ("Warning", "WARNING"),
        "warn": ("Warning", "WARNING"),
        "info": ("Info", "INFO"),
        "success": ("Success", "SUCCESS"),
    }.get(normalized, ("Info", "INFO"))
    for candidate in candidates:
        if hasattr(qgis_class, candidate):
            return getattr(qgis_class, candidate)
    return getattr(qgis_class, "Info", 0)


def _detect_qgis_version(core: Any | None) -> str | None:
    if core is None:
        return None
    qgis_class = getattr(core, "Qgis", None)
    version = getattr(qgis_class, "QGIS_VERSION", None)
    if version:
        return str(version)
    app = getattr(core, "QgsApplication", None)
    version_method = getattr(app, "qgisVersion", None)
    if callable(version_method):
        try:
            return str(version_method())
        except Exception:  # noqa: BLE001
            return None
    return None


def _detect_qt_version(qt_core: Any | None) -> str | None:
    if qt_core is None:
        return None
    value = getattr(qt_core, "QT_VERSION_STR", "")
    if value:
        return str(value)
    qversion = getattr(qt_core, "qVersion", None)
    if callable(qversion):
        try:
            return str(qversion())
        except Exception:  # noqa: BLE001
            return None
    return None


def _has_any(obj: Any | None, names: tuple[str, ...]) -> bool:
    return obj is not None and any(hasattr(obj, name) for name in names)


def _has_processing_provider_support(core: Any | None) -> bool:
    if core is None:
        return False
    provider_class = getattr(core, "QgsProcessingProvider", None)
    app = getattr(core, "QgsApplication", None)
    registry = getattr(app, "processingRegistry", None)
    return bool(provider_class is not None and callable(registry))


def _processing_registry() -> Any | None:
    try:
        from qgis.core import QgsApplication  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    registry_method = getattr(QgsApplication, "processingRegistry", None)
    if not callable(registry_method):
        return None
    try:
        return registry_method()
    except Exception:  # noqa: BLE001
        return None


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
