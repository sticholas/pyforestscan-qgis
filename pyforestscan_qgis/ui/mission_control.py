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
from ..core.jobs import JobRecord
from ..core.workspace import RunContext
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
        self.job_history: tuple[JobRecord, ...] = ()
        self.loaded_result_paths: set[Path] = set()
        self.root_widget = QWidget(self)
        self.ui = FORM_CLASS()
        self.ui.setupUi(self.root_widget)
        self.setWidget(self.root_widget)
        self.setObjectName("PyForestScanMissionControlDock")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.home_page = HomePage(plugin_version=self._plugin_version())
        self.environment_page = EnvironmentPage(self.adapter)
        self.dataset_page = DatasetPage(self.adapter, iface=self.iface)
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
        self.processing_page.jobUpdated.connect(self._set_job_status)
        self.settings_page.defaultOutputFolderChanged.connect(self._set_default_output_folder)

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

    def _set_dataset_report(self, report: object, dataset_path: str, context: RunContext) -> None:
        self.planning_page.set_dataset_report(report, context)  # type: ignore[arg-type]
        self.processing_page.set_run_context(context)
        self.results_page.set_run_context(context)
        state = self.state.with_active_run(context).with_report_path(context.dataset_report_html)
        state = state.with_report_path(context.dataset_summary_csv).with_activity("Dataset explored", Path(dataset_path).name)
        self.state = state
        self._refresh_home()
        self._update_status_bar()

    def _set_planning_status(self, status: str, plan: object | None = None) -> None:
        state = self.state.with_planning(status).with_activity("Planning updated", status)
        if self.state.active_run is not None and plan is not None:
            self.processing_page.set_run_context(self.state.active_run)
            self.results_page.set_run_context(self.state.active_run)
            state = state.with_report_path(self.state.active_run.product_plan_html)
            state = state.with_report_path(self.state.active_run.product_plan_csv)
        self.state = state
        self._refresh_home()
        self._update_status_bar()

    def _set_default_output_folder(self, folder: object) -> None:
        path = folder if isinstance(folder, Path) else None
        self.state = self.state.with_default_output_folder(path).with_activity("Default output folder", str(path) if path else "Cleared")
        self.dataset_page.set_default_output_folder(path)
        self._refresh_home()
        self._update_status_bar()

    def _set_job_status(self, job: JobRecord) -> None:
        existing = tuple(item for item in self.job_history if item.job_id != job.job_id)
        self.job_history = (job,) + existing
        state = self.state.with_activity("Processing job", f"{job.title}: {job.status.value}")
        for result in job.results:
            state = state.with_report_path(result.path)
        self._load_job_outputs(job)
        if self.state.active_run is not None:
            self.results_page.set_run_context(self.state.active_run)
        self.state = state
        self._refresh_home()
        self._update_status_bar()


    def _load_job_outputs(self, job: JobRecord) -> None:
        """Best-effort load of generated raster outputs into QGIS."""
        for result in job.results:
            if result.result_type not in {"chm_geotiff", "canopy_cover_geotiff", "pad_geotiff", "pai_geotiff", "fhd_geotiff"} or result.path in self.loaded_result_paths:
                continue
            if not result.path.exists():
                continue
            layer_name = self._layer_name(result.path, result.result_type)
            try:
                layer = self.iface.addRasterLayer(str(result.path), layer_name)
            except Exception:  # noqa: BLE001 - UI layer loading must not break job completion.
                layer = None
            if layer is not None:
                self._polish_raster_layer(layer, result.result_type)
                self.loaded_result_paths.add(result.path)

    def _layer_name(self, path: Path, result_type: str) -> str:
        """Return a friendly layer name for generated rasters."""
        product = {
            "canopy_cover_geotiff": "Canopy Cover",
            "pad_geotiff": "PAD",
            "pai_geotiff": "PAI",
            "fhd_geotiff": "FHD",
        }.get(result_type, "CHM")
        if self.state.active_run is not None:
            return f"{product} - {self.state.active_run.lidar_path.stem} - {self.state.active_run.run_folder.name}"
        return f"{product} - {path.stem}"

    def _polish_raster_layer(self, layer: object, result_type: str) -> None:
        """Best-effort generated raster statistics and styling."""
        try:
            provider = layer.dataProvider()
            provider.bandStatistics(1)
        except Exception:  # noqa: BLE001 - statistics are helpful but optional.
            return
        try:
            from qgis.PyQt.QtGui import QColor
            from qgis.core import QgsColorRampShader, QgsRasterShader, QgsSingleBandPseudoColorRenderer

            shader = QgsRasterShader()
            ramp = QgsColorRampShader()
            ramp.setColorRampType(QgsColorRampShader.Interpolated)
            ramp.setColorRampItemList(
                [
                    *self._raster_ramp_items(result_type, QColor, QgsColorRampShader),
                ]
            )
            shader.setRasterShaderFunction(ramp)
            renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
            layer.setRenderer(renderer)
            layer.triggerRepaint()
        except Exception:  # noqa: BLE001 - styling should never break layer loading.
            return


    def _raster_ramp_items(self, result_type: str, qcolor: object, shader_class: object) -> list[object]:
        """Return simple color ramp items for generated raster products."""
        if result_type == "canopy_cover_geotiff":
            return [
                shader_class.ColorRampItem(0.0, qcolor("#f7fbff"), "Low"),
                shader_class.ColorRampItem(0.5, qcolor("#6baed6"), "Medium"),
                shader_class.ColorRampItem(1.0, qcolor("#08306b"), "High"),
            ]
        if result_type == "pai_geotiff":
            return [
                shader_class.ColorRampItem(0.0, qcolor("#fef3c7"), "Low"),
                shader_class.ColorRampItem(2.0, qcolor("#65a30d"), "Medium"),
                shader_class.ColorRampItem(6.0, qcolor("#14532d"), "High"),
            ]
        if result_type == "pad_geotiff":
            return [
                shader_class.ColorRampItem(0.0, qcolor("#f8fafc"), "Low"),
                shader_class.ColorRampItem(0.5, qcolor("#22c55e"), "Medium"),
                shader_class.ColorRampItem(2.0, qcolor("#166534"), "High"),
            ]
        if result_type == "fhd_geotiff":
            return [
                shader_class.ColorRampItem(0.0, qcolor("#fff7ed"), "Low"),
                shader_class.ColorRampItem(1.0, qcolor("#fb923c"), "Medium"),
                shader_class.ColorRampItem(3.0, qcolor("#7c2d12"), "High"),
            ]
        return [
            shader_class.ColorRampItem(0.0, qcolor("#f7fcf0"), "Low"),
            shader_class.ColorRampItem(10.0, qcolor("#74c476"), "Medium"),
            shader_class.ColorRampItem(30.0, qcolor("#00441b"), "High"),
        ]

    def _refresh_home(self) -> None:
        self.home_page.set_versions(self._pyforestscan_version())
        self.home_page.set_summary(
            self.state.environment_status,
            self.state.latest_dataset,
            self.state.latest_project,
        )
        self.home_page.set_activities(tuple((item.label, item.detail) for item in self.state.activities))
        self.results_page.set_run_context(self.state.active_run)
        self.results_page.set_report_paths(self.state.latest_report_paths)
        self.results_page.set_jobs(self.job_history)

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
