"""Compatibility service for opening and inspecting QGIS Processing Toolbox."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

@dataclass(frozen=True)
class ProcessingProviderStatus:
    available: bool
    algorithm_count: int = 0
    groups: tuple[str, ...] = ()
    message: str = ""

@dataclass(frozen=True)
class ProcessingToolboxOpenResult:
    success: bool
    toolbox_found: bool
    toolbox_visible: bool
    provider_found: bool
    provider_expanded: bool
    focused: bool
    user_message: str
    technical_message: str = ""

class QgisProcessingToolboxService:
    """Use public QGIS APIs first and widget discovery as a guarded fallback."""
    PROVIDER_ID = "pyforestscan"

    def __init__(self, iface: Any, registry: Any = None) -> None:
        self.iface = iface
        self._registry = registry

    def _processing_registry(self) -> Any:
        if self._registry is not None:
            return self._registry
        try:
            from qgis.core import QgsApplication
            return QgsApplication.processingRegistry()
        except Exception:
            return None

    def provider_status(self) -> ProcessingProviderStatus:
        registry = self._processing_registry()
        provider = registry.providerById(self.PROVIDER_ID) if registry is not None else None
        if provider is None:
            return ProcessingProviderStatus(False, message="PyForestScan tools are not registered in QGIS Processing.")
        try:
            algorithms = tuple(provider.algorithms())
        except Exception:
            algorithms = ()
        groups = tuple(sorted({str(a.group()) for a in algorithms if hasattr(a, "group")}))
        return ProcessingProviderStatus(True, len(algorithms), groups,
                                        f"PyForestScan provider is available with {len(algorithms)} tools.")

    def _find_toolbox(self) -> Any:
        main = self.iface.mainWindow() if self.iface is not None and hasattr(self.iface, "mainWindow") else None
        if main is None or not hasattr(main, "findChildren"):
            return None
        try:
            from qgis.PyQt.QtWidgets import QDockWidget
            docks = main.findChildren(QDockWidget)
        except Exception:
            try:
                docks = main.findChildren(object)
            except Exception:
                return None
        for dock in docks:
            title = str(dock.windowTitle()).lower() if hasattr(dock, "windowTitle") else ""
            name = str(dock.objectName()).lower() if hasattr(dock, "objectName") else ""
            if "processing toolbox" in title or "processingtoolbox" in name:
                return dock
        return None

    def open_toolbox(self) -> ProcessingToolboxOpenResult:
        technical: list[str] = []
        opener = getattr(self.iface, "openProcessingToolbox", None)
        if callable(opener):
            try:
                opener()
            except Exception as exc:
                technical.append(f"Public open method failed: {exc}")
        toolbox = self._find_toolbox()
        status = self.provider_status()
        if toolbox is None:
            return ProcessingToolboxOpenResult(False, False, False, status.available, False, False,
                                               "Unable to find the QGIS Processing Toolbox.", "; ".join(technical))
        focused = False
        try:
            toolbox.show(); toolbox.setVisible(True)
            if hasattr(toolbox, "raise_"): toolbox.raise_()
            if hasattr(toolbox, "activateWindow"): toolbox.activateWindow()
            focused = True
        except Exception as exc:
            technical.append(f"Toolbox focus failed: {exc}")
        visible = bool(toolbox.isVisible()) if hasattr(toolbox, "isVisible") else focused
        message = ("PyForestScan tools are available in the Processing Toolbox."
                   if status.available else status.message)
        return ProcessingToolboxOpenResult(visible, True, visible, status.available, False, focused,
                                           message, "; ".join(technical))

    def refresh_provider(self, provider_factory: Callable[[], Any] | None = None) -> ProcessingProviderStatus:
        registry = self._processing_registry()
        if registry is None:
            return ProcessingProviderStatus(False, message="QGIS Processing registry is unavailable.")
        provider = registry.providerById(self.PROVIDER_ID)
        if provider is None and provider_factory is not None:
            registry.addProvider(provider_factory())
        elif provider is not None and hasattr(provider, "refreshAlgorithms"):
            provider.refreshAlgorithms()
        return self.provider_status()
