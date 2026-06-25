"""Mission Control dock widget."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path
from typing import Any

from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QDockWidget, QWidget

from ..core.adapter import PyForestScanAdapter
from ..resources import plugin_root
from .pages import (
    DatasetPage,
    EnvironmentPage,
    HomePage,
    PlanningPage,
    ProcessingPage,
    ResultsPage,
    SettingsPage,
)
from .state import MissionControlState

FORM_CLASS, _ = uic.loadUiType(str(plugin_root() / "ui" / "forms" / "mission_control.ui"))


class MissionControlDock(QDockWidget):
    """Dockable Mission Control interface for PyForestScan QGIS."""

    PAGE_NAMES = (
        "Home",
        "Environment",
        "Dataset",
        "Planning",
        "Processing",
        "Results",
        "Settings",
    )

    def __init__(self, iface: Any, parent: QWidget | None = None) -> None:
        """Create the Mission Control dock and wire page navigation."""
        super().__init__("PyForestScan Mission Control", parent)
        self.iface = iface
        self.adapter = PyForestScanAdapter()
        self.state = MissionControlState()
        self.root_widget = QWidget(self)
        self.ui = FORM_CLASS()
        self.ui.setupUi(self.root_widget)
        self.setWidget(self.root_widget)
        self.setObjectName("PyForestScanMissionControlDock")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.home_page = HomePage(plugin_version=self._plugin_version())
        self.environment_page = EnvironmentPage(self.adapter)
        self.dataset_page = DatasetPage(self.adapter)
        self.planning_page = PlanningPage()
        self.processing_page = ProcessingPage()
        self.results_page = ResultsPage()
        self.settings_page = SettingsPage()
        self.pages = (
            self.home_page,
            self.environment_page,
            self.dataset_page,
            self.planning_page,
            self.processing_page,
            self.results_page,
            self.settings_page,
        )

        self._configure_style()
        self._populate_navigation()
        self._wire_signals()
        self._refresh_home()
        self._update_status_bar()

    def show_home(self) -> None:
        """Show the home page."""
        self.ui.navigationList.setCurrentRow(0)

    def _populate_navigation(self) -> None:
        for name, page in zip(self.PAGE_NAMES, self.pages):
            self.ui.navigationList.addItem(name)
            self.ui.pageStack.addWidget(page)
        self.ui.navigationList.setCurrentRow(0)

    def _wire_signals(self) -> None:
        self.ui.navigationList.currentRowChanged.connect(self.ui.pageStack.setCurrentIndex)
        self.home_page.openDocumentationRequested.connect(self._open_documentation)
        self.environment_page.environmentChanged.connect(self._set_environment_status)
        self.dataset_page.datasetExplored.connect(self._set_dataset_report)
        self.planning_page.planningChanged.connect(self._set_planning_status)

    def _configure_style(self) -> None:
        self.root_widget.setStyleSheet(
            """
            #headerFrame { background: #163b3d; color: white; }
            #titleLabel { font-size: 20px; font-weight: 700; }
            #subtitleLabel { color: #dbe8e7; }
            #statusFrame { background: #edf3f5; border-top: 1px solid #cbd7dc; }
            #pageHeading { font-size: 18px; font-weight: 700; margin: 8px; }
            QListWidget { border: 0; background: #f3f6f7; }
            QListWidget::item { padding: 9px; }
            QListWidget::item:selected { background: #2d7c83; color: white; }
            QGroupBox { font-weight: 600; margin-top: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
            """
        )

    def _set_environment_status(self, status: str) -> None:
        self.state = self.state.with_environment(status).with_activity("Environment refreshed", status)
        self._refresh_home()
        self._update_status_bar()

    def _set_dataset_report(self, report: object, dataset_path: str) -> None:
        self.planning_page.set_dataset_report(report)  # type: ignore[arg-type]
        self.state = self.state.with_dataset(dataset_path).with_activity("Dataset explored", Path(dataset_path).name)
        self._refresh_home()
        self._update_status_bar()

    def _set_planning_status(self, status: str) -> None:
        self.state = self.state.with_planning(status).with_activity("Planning updated", status)
        self._refresh_home()
        self._update_status_bar()

    def _refresh_home(self) -> None:
        self.home_page.set_versions(self._pyforestscan_version())
        self.home_page.set_summary(
            self.state.environment_status,
            self.state.latest_dataset,
            self.state.latest_project,
        )
        self.home_page.set_activities(tuple((item.label, item.detail) for item in self.state.activities))
        self.results_page.set_report_paths(self.state.latest_report_paths)

    def _update_status_bar(self) -> None:
        self.ui.environmentStatusLabel.setText(f"Environment: {self.state.environment_status}")
        self.ui.datasetStatusLabel.setText(f"Dataset: {Path(self.state.latest_dataset).name if self.state.latest_dataset else 'None'}")
        self.ui.planningStatusLabel.setText(f"Planning: {self.state.planning_status}")
        ready = "Ready" if self.state.environment_status != "NOT READY" else "Needs attention"
        self.ui.readyStatusLabel.setText(ready)

    def _open_documentation(self) -> None:
        docs = plugin_root().parent / "docs" / "USER_GUIDE.md"
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(docs)))

    def _plugin_version(self) -> str:
        metadata_path = plugin_root() / "metadata.txt"
        try:
            for line in metadata_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("version="):
                    return line.split("=", 1)[1].strip()
        except OSError:
            return "Unknown"
        return "Unknown"

    def _pyforestscan_version(self) -> str | None:
        try:
            return metadata.version("pyforestscan")
        except metadata.PackageNotFoundError:
            return None
