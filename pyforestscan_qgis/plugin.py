"""QGIS plugin lifecycle management for PyForestScan QGIS."""

from __future__ import annotations

from typing import Any

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QAction

from .core.qgis_compat import open_or_raise_mission_control, register_processing_provider, report_message, unregister_processing_provider
from .processing_provider import PyForestScanProvider
from .resources import plugin_icon
from .ui.mission_control import MissionControlDock
from .core.workspace import WorkspaceManager


class PyForestScanPlugin:
    """Register Processing provider and Mission Control dock UI."""

    MENU_NAME = "PyForestScan"

    def __init__(self, iface: Any) -> None:
        """Create the plugin lifecycle object.

        Args:
            iface: QGIS interface object supplied by the plugin loader.
        """
        self.iface = iface
        self.provider: PyForestScanProvider | None = None
        self.mission_control: MissionControlDock | None = None
        self.mission_control_action: QAction | None = None

    def initGui(self) -> None:
        """Register Processing provider and open Mission Control."""
        if self.provider is None:
            provider = PyForestScanProvider()
            result = register_processing_provider(provider)
            if result.success:
                self.provider = provider
            else:
                report_message(result.message, level="WARNING")
        self._create_mission_control_action()
        try:
            auto_open = WorkspaceManager().load_global_session().open_mission_control_on_startup
        except Exception:  # noqa: BLE001 - startup preference must never block plugin loading.
            auto_open = False
        if auto_open:
            self._show_mission_control()

    def unload(self) -> None:
        """Remove Processing provider, actions, and Mission Control dock."""
        if self.provider is not None:
            result = unregister_processing_provider(self.provider)
            if not result.success:
                report_message(result.message, level="WARNING")
            self.provider = None
        if self.mission_control_action is not None:
            remove_menu = getattr(self.iface, "removePluginMenu", None)
            if callable(remove_menu):
                remove_menu(self.MENU_NAME, self.mission_control_action)
            remove_toolbar_icon = getattr(self.iface, "removeToolBarIcon", None)
            if callable(remove_toolbar_icon):
                remove_toolbar_icon(self.mission_control_action)
            self.mission_control_action = None
        if self.mission_control is not None:
            save_session = getattr(self.mission_control, "_save_workspace_session", None)
            if callable(save_session):
                save_session()
            remove_dock = getattr(self.iface, "removeDockWidget", None)
            if callable(remove_dock):
                remove_dock(self.mission_control)
            self.mission_control.deleteLater()
            self.mission_control = None

    def _create_mission_control_action(self) -> None:
        """Create the toolbar/menu action used to show Mission Control."""
        if self.mission_control_action is not None:
            return
        self.mission_control_action = QAction(plugin_icon(), "Mission Control", self.iface.mainWindow())
        self.mission_control_action.setObjectName("PyForestScanMissionControlAction")
        self.mission_control_action.triggered.connect(self._show_mission_control)
        add_menu = getattr(self.iface, "addPluginToMenu", None)
        if callable(add_menu):
            add_menu(self.MENU_NAME, self.mission_control_action)
        add_toolbar_icon = getattr(self.iface, "addToolBarIcon", None)
        if callable(add_toolbar_icon):
            add_toolbar_icon(self.mission_control_action)

    def _show_mission_control(self) -> None:
        """Create, show, and raise the floating Mission Control window."""
        if self.mission_control is None:
            self.mission_control = MissionControlDock(self.iface, self.iface.mainWindow())
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.mission_control)
            self.mission_control.setFloating(True)
            self.mission_control.resize(1400, 900)
        result = open_or_raise_mission_control(self.mission_control)
        if not result.success:
            report_message(result.message, level="WARNING")
