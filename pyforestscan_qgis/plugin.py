"""QGIS plugin lifecycle management for PyForestScan QGIS."""

from __future__ import annotations

from typing import Any

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsApplication

from .processing_provider import PyForestScanProvider
from .resources import plugin_icon
from .ui.mission_control import MissionControlDock


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
            self.provider = PyForestScanProvider()
            QgsApplication.processingRegistry().addProvider(self.provider)
        self._create_mission_control_action()
        self._show_mission_control()

    def unload(self) -> None:
        """Remove Processing provider, actions, and Mission Control dock."""
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
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
        """Create and show the dockable Mission Control panel."""
        if self.mission_control is None:
            self.mission_control = MissionControlDock(self.iface, self.iface.mainWindow())
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.mission_control)
        self.mission_control.show()
        self.mission_control.raise_()
