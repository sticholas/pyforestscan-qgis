"""Mission Control dock widget."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path
from typing import Any

from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QDockWidget, QSizePolicy, QWidget

from ..core.adapter import PyForestScanAdapter
from ..core.dataset_report import report_to_dict as dataset_report_to_dict
from ..core.knowledge import KnowledgeEngine
from ..core.jobs import JobRecord
from ..core.workspace import RunContext
from ..resources import plugin_root
from .pages import (
    BatchPage,
    DatasetPage,
    EnvironmentPage,
    HomePage,
    PlanningPage,
    ProcessingPage,
    ResultsPage,
    ScientificAdvisorPage,
    SettingsPage,
)
from .advisor import completed_products_from_job
from .raster_styling import apply_generated_raster_renderer, is_raster_result, layer_display_name
from .state import MissionControlState

FORM_CLASS, _ = uic.loadUiType(str(plugin_root() / "ui" / "forms" / "mission_control.ui"))


class MissionControlDock(QDockWidget):
    """Dockable Mission Control interface for PyForestScan QGIS."""

    PAGE_NAMES = (
        "Home",
        "Environment",
        "Dataset",
        "Scientific Advisor",
        "Planning",
        "Processing",
        "Batch",
        "Results",
        "Settings",
    )

    def __init__(self, iface: Any, parent: QWidget | None = None) -> None:
        """Create the Mission Control dock and wire page navigation."""
        super().__init__("PyForestScan Mission Control", parent)
        self.iface = iface
        self.adapter = PyForestScanAdapter()
        self.knowledge_engine = KnowledgeEngine()
        self.state = MissionControlState()
        self.job_history: tuple[JobRecord, ...] = ()
        self.batch_status = "Not started"
        self.loaded_result_paths: set[Path] = set()
        self.root_widget = QWidget(self)
        self.ui = FORM_CLASS()
        self.ui.setupUi(self.root_widget)
        self.setWidget(self.root_widget)
        self.setObjectName("PyForestScanMissionControlDock")
        self.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.setFeatures(self.features() | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)
        self.setMinimumSize(1150, 760)
        self.root_widget.setMinimumSize(1150, 760)
        self.root_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.ui.navigationList.setFixedWidth(190)
        self.ui.pageStack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.ui.bodyLayout.setStretch(0, 0)
        self.ui.bodyLayout.setStretch(1, 1)
        self.ui.rootLayout.setStretch(0, 0)
        self.ui.rootLayout.setStretch(1, 1)
        self.ui.rootLayout.setStretch(2, 0)
        for label in (
            self.ui.environmentStatusLabel,
            self.ui.datasetStatusLabel,
            self.ui.planningStatusLabel,
            self.ui.readyStatusLabel,
        ):
            label.setWordWrap(True)
            label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.home_page = HomePage(plugin_version=self._plugin_version())
        self.environment_page = EnvironmentPage(self.adapter)
        self.dataset_page = DatasetPage(self.adapter, iface=self.iface)
        self.advisor_page = ScientificAdvisorPage(iface=self.iface)
        self.planning_page = PlanningPage()
        self.processing_page = ProcessingPage()
        self.batch_page = BatchPage(self.adapter)
        self.results_page = ResultsPage()
        self.settings_page = SettingsPage()
        self.pages = (
            self.home_page,
            self.environment_page,
            self.dataset_page,
            self.advisor_page,
            self.planning_page,
            self.processing_page,
            self.batch_page,
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
        self.home_page.startSingleDatasetRequested.connect(lambda: self.ui.navigationList.setCurrentRow(self.PAGE_NAMES.index("Dataset")))
        self.home_page.startBatchRequested.connect(lambda: self.ui.navigationList.setCurrentRow(self.PAGE_NAMES.index("Batch")))
        self.environment_page.environmentChanged.connect(self._set_environment_status)
        self.dataset_page.datasetExplored.connect(self._set_dataset_report)
        self.planning_page.planningChanged.connect(self._set_planning_status)
        self.processing_page.jobUpdated.connect(self._set_job_status)
        self.batch_page.jobUpdated.connect(self._set_job_status)
        self.batch_page.batchCompleted.connect(self._set_batch_status)
        self.settings_page.defaultOutputFolderChanged.connect(self._set_default_output_folder)

    def _configure_style(self) -> None:
        self.root_widget.setStyleSheet(
            """
            QWidget { background: #f7f8f9; color: #23313a; }
            #headerFrame { background: #eef3f4; color: #22323a; border-bottom: 1px solid #d8e1e5; }
            #titleLabel { font-size: 20px; font-weight: 700; }
            #subtitleLabel { color: #5f6f77; }
            #statusFrame { background: #f2f5f6; border-top: 1px solid #dbe3e6; }
            #pageHeading { font-size: 21px; font-weight: 700; margin: 12px 18px; color: #22323a; }
            #pageScroll { border: 0; background: #f7f8f9; }
            #pageContent { background: #f7f8f9; }
            #advisorBody { background: #f7f8f9; }
            #advisorCard { background: #ffffff; border: 1px solid #dfe6e9; border-radius: 7px; }
            #advisorNestedCard { background: #f8fafb; border: 1px solid #e3eaed; border-radius: 6px; }
            #advisorSectionHeading { font-size: 18px; font-weight: 700; color: #22323a; margin-bottom: 4px; }
            #advisorCardTitle { font-size: 15px; font-weight: 700; color: #283840; }
            #advisorBodyText { font-size: 13px; line-height: 1.35; color: #30414a; }
            #advisorDetailsText { font-size: 12px; line-height: 1.35; color: #52656d; background: #fbfcfd; border: 1px solid #edf2f4; border-radius: 5px; padding: 8px; }
            #advisorMetric { font-size: 15px; background: #f8fafb; border: 1px solid #e1e9ec; border-radius: 6px; padding: 12px; color: #22323a; }
            #advisorList { font-size: 13px; border: 1px solid #dfe6e9; background: #ffffff; border-radius: 5px; }
            #advisorWarningList { font-size: 13px; border: 1px solid #e0cda8; background: #fffdf8; border-radius: 5px; }
            QListWidget { border: 1px solid #dfe6e9; background: #ffffff; border-radius: 4px; }
            QListWidget::item { padding: 10px; border-bottom: 1px solid #eef2f3; }
            QListWidget::item:selected { background: #dde8ec; color: #1f2d35; }
            QGroupBox { font-weight: 600; margin-top: 12px; border: 1px solid #dfe6e9; border-radius: 6px; padding: 12px; background: #ffffff; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #32424a; }
            QPushButton { background: #ffffff; border: 1px solid #cfd9dd; border-radius: 4px; padding: 8px 12px; }
            QPushButton:hover { background: #f0f4f5; }
            QLineEdit, QTextEdit, QDoubleSpinBox, QComboBox { background: #ffffff; border: 1px solid #d4dee2; border-radius: 4px; padding: 5px; }
            QProgressBar { border: 1px solid #cfd9dd; border-radius: 4px; background: #ffffff; text-align: center; }
            QProgressBar::chunk { background: #9eacb3; border-radius: 3px; }
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
        self.advisor_page.set_run_context(context)
        try:
            advisor_report = self.knowledge_engine.evaluate_dataset_explorer_report(dataset_report_to_dict(report))  # type: ignore[arg-type]
            self.advisor_page.set_recommendation_report(advisor_report)
            self.planning_page.apply_recommendation_report(advisor_report)
        except Exception:  # noqa: BLE001 - advisor guidance must not break Dataset Explorer.
            pass
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
        self.batch_page.set_default_output_folder(path)
        self._refresh_home()
        self._update_status_bar()

    def _set_job_status(self, job: JobRecord) -> None:
        existing = tuple(item for item in self.job_history if item.job_id != job.job_id)
        self.job_history = (job,) + existing
        state = self.state.with_activity("Processing job", f"{job.title}: {job.status.value}")
        for result in job.results:
            state = state.with_report_path(result.path)
        self._load_job_outputs(job)
        self.advisor_page.set_completed_products(completed_products_from_job(job))
        if self.state.active_run is not None:
            self.results_page.set_run_context(self.state.active_run)
            self.advisor_page.set_run_context(self.state.active_run)
        self.state = state
        self._refresh_home()
        self._update_status_bar()

    def _set_batch_status(self, result: object) -> None:
        """Record a completed batch summary in Mission Control results."""
        summary_json = getattr(result, "summary_json", None)
        summary_csv = getattr(result, "summary_csv", None)
        summary_html = getattr(result, "summary_html", None)
        success_count = getattr(result, "success_count", 0)
        failure_count = getattr(result, "failure_count", 0)
        skipped_count = getattr(result, "skipped_count", 0)
        self.batch_status = f"Completed {success_count}; failed {failure_count}; skipped {skipped_count}"
        state = self.state.with_activity("Batch complete", self.batch_status)
        for path in (summary_html, summary_csv, summary_json):
            if isinstance(path, Path):
                state = state.with_report_path(path)
        self.state = state
        self._refresh_home()
        self._update_status_bar()


    def _load_job_outputs(self, job: JobRecord) -> None:
        """Best-effort load of generated raster outputs into QGIS."""
        for result in job.results:
            if not is_raster_result(result.result_type) or result.path in self.loaded_result_paths:
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
        if path.parent.name == "outputs" and path.parent.parent.name:
            dataset_stem = path.parent.parent.name
        elif self.state.active_run is not None:
            dataset_stem = self.state.active_run.lidar_path.stem
        else:
            dataset_stem = path.stem
        return layer_display_name(result_type, dataset_stem)

    def _polish_raster_layer(self, layer: object, result_type: str) -> None:
        """Best-effort generated raster statistics and styling."""
        try:
            apply_generated_raster_renderer(layer, result_type)
        except Exception:  # noqa: BLE001 - styling should never break layer loading.
            return

    def _refresh_home(self) -> None:
        self.home_page.set_versions(self._pyforestscan_version())
        recent_run = str(self.state.active_run.run_folder) if self.state.active_run is not None else None
        self.home_page.set_summary(
            self.state.environment_status,
            self.state.latest_dataset,
            self.state.latest_project,
            self.batch_status,
            recent_run,
        )
        self.home_page.set_activities(tuple((item.label, item.detail) for item in self.state.activities))
        self.results_page.set_run_context(self.state.active_run)
        self.advisor_page.set_run_context(self.state.active_run)
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
