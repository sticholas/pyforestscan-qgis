"""Mission Control dock widget."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path
from typing import Any

from qgis.PyQt import uic
from qgis.PyQt.QtCore import QByteArray, Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QDockWidget, QFileDialog, QSizePolicy, QWidget

from ..core.adapter import PyForestScanAdapter
from ..core.dataset_report import report_to_dict as dataset_report_to_dict
from ..core.knowledge import KnowledgeEngine
from ..core.jobs import JobRecord, JobStatus
from ..core.workspace import RunContext, WorkspaceHistoryRun, WorkspaceManager, WorkspaceSession, WorkspaceStatus, summarize_recent_workspaces
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
    WorkspacePage,
)
from .advisor import completed_products_from_job
from .raster_styling import apply_generated_raster_renderer, is_raster_result, layer_display_name
from .state import MissionControlState, ProjectSummary, build_project_summary
from .ux_summary import environment_is_ready, guided_next_step, guided_workflow_indicator, guided_workflow_status_lines, guided_workflow_pages, readiness_marker_label

FORM_CLASS, _ = uic.loadUiType(str(plugin_root() / "ui" / "forms" / "mission_control.ui"))


class MissionControlDock(QDockWidget):
    """Dockable Mission Control interface for PyForestScan QGIS."""

    PAGE_NAMES = (
        "Home",
        "Workspace",
        "Dataset",
        "Planning",
        "Processing",
        "Batch",
        "Results",
        "Scientific Advisor",
        "Environment",
        "Settings",
    )

    def __init__(self, iface: Any, parent: QWidget | None = None) -> None:
        """Create the Mission Control dock and wire page navigation."""
        super().__init__("PyForestScan Mission Control", parent)
        self.iface = iface
        self.adapter = PyForestScanAdapter()
        self.knowledge_engine = KnowledgeEngine()
        self.workspace_manager = WorkspaceManager()
        self.workspace_session = self._load_workspace_session()
        self.workspace = None
        self._workspace_recorded_jobs: set[str] = set()
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
        self.workspace_page = WorkspacePage()
        self.environment_page = EnvironmentPage(self.adapter)
        self.dataset_page = DatasetPage(self.adapter, iface=self.iface)
        self.advisor_page = ScientificAdvisorPage(iface=self.iface)
        self.planning_page = PlanningPage()
        self.processing_page = ProcessingPage()
        self.batch_page = BatchPage(self.adapter)
        self.results_page = ResultsPage(iface=self.iface)
        self.settings_page = SettingsPage()
        self.settings_page.set_workspace_session(self.workspace_session)
        self.pages = (
            self.home_page,
            self.workspace_page,
            self.dataset_page,
            self.planning_page,
            self.processing_page,
            self.batch_page,
            self.results_page,
            self.advisor_page,
            self.environment_page,
            self.settings_page,
        )

        self._configure_style()
        self._populate_navigation()
        self._wire_signals()
        self._restore_workspace_session()
        self._refresh_home()
        self._update_status_bar()

    def show_home(self) -> None:
        """Show the home page."""
        self.ui.navigationList.setCurrentRow(0)

    def closeEvent(self, event: object) -> None:  # noqa: N802 - Qt API name.
        """Save the Mission Control workspace session when the window closes."""
        self._save_workspace_session()
        super().closeEvent(event)

    def _load_workspace_session(self) -> WorkspaceSession:
        """Load global Mission Control workspace session state."""
        try:
            return self.workspace_manager.load_global_session()
        except Exception:  # noqa: BLE001 - a bad session file should not break plugin loading.
            return WorkspaceSession()

    def _restore_workspace_session(self) -> None:
        """Restore lightweight session context without manipulating the QGIS project."""
        session = self.workspace_session
        if session.last_output_folder is not None and session.remember_last_output_folder:
            self.state = self.state.with_default_output_folder(session.last_output_folder)
            self.dataset_page.set_default_output_folder(session.last_output_folder)
            self.batch_page.set_default_output_folder(session.last_output_folder)
            self.settings_page.default_output_folder.setText(str(session.last_output_folder))
        if session.last_selected_dataset is not None and session.remember_last_dataset:
            self.dataset_page.dataset_path_edit.setText(str(session.last_selected_dataset))
            self.state = self.state.with_dataset(str(session.last_selected_dataset))
        if session.last_opened_workspace is not None and session.remember_last_workspace:
            workspace_root = session.last_opened_workspace.parent if session.last_opened_workspace.name == ".pyforestscan" else session.last_opened_workspace
            try:
                self.workspace = self.workspace_manager.load_workspace(workspace_root)
            except Exception:  # noqa: BLE001 - restore should be best effort.
                self.workspace = None
        if session.window_geometry:
            try:
                self.restoreGeometry(QByteArray.fromBase64(session.window_geometry.encode("ascii")))
            except Exception:  # noqa: BLE001 - geometry restore is best effort.
                pass
        if session.last_page in self.PAGE_NAMES:
            self.ui.navigationList.setCurrentRow(self.PAGE_NAMES.index(session.last_page))

    def _populate_navigation(self) -> None:
        for name, page in zip(self.PAGE_NAMES, self.pages):
            self.ui.navigationList.addItem(name)
            self.ui.pageStack.addWidget(page)
        self.ui.navigationList.setCurrentRow(0)

    def _wire_signals(self) -> None:
        self.ui.navigationList.currentRowChanged.connect(self.ui.pageStack.setCurrentIndex)
        self.ui.navigationList.currentRowChanged.connect(lambda _row: self._refresh_guided_workflow())
        self.home_page.continueWorkflowRequested.connect(self._continue_guided_workflow)
        self.home_page.checkEnvironmentRequested.connect(self._open_environment_and_refresh)
        self.home_page.continueLastRequested.connect(self._continue_last_workspace)
        self.environment_page.backendSettingsRequested.connect(lambda: self.ui.navigationList.setCurrentRow(self.PAGE_NAMES.index("Settings")))
        self.workspace_page.continueLastRequested.connect(self._continue_last_workspace)
        self.workspace_page.startNewRequested.connect(self._start_new_workspace)
        self.workspace_page.workspaceSelected.connect(self._open_workspace_path)
        self.workspace_page.removeRecentRequested.connect(self._remove_recent_workspace)
        self.workspace_page.resetWorkspaceRequested.connect(self._reset_current_workspace)
        self.workspace_page.notesSaveRequested.connect(self._save_workspace_notes)
        self.environment_page.environmentChanged.connect(self._set_environment_status)
        self.dataset_page.datasetSelectionChanged.connect(self._set_dataset_pending)
        self.dataset_page.datasetExplored.connect(self._set_dataset_report)
        self.planning_page.planningChanged.connect(self._set_planning_status)
        self.processing_page.jobUpdated.connect(self._set_job_status)
        self.batch_page.jobUpdated.connect(self._set_job_status)
        self.batch_page.batchCompleted.connect(self._set_batch_status)
        self.results_page.outputsLoaded.connect(self._set_outputs_loaded_status)
        self.results_page.currentRunCleared.connect(self._clear_current_run_state)
        self.settings_page.defaultOutputFolderChanged.connect(self._set_default_output_folder)
        self.settings_page.backendStateChanged.connect(self._set_backend_page_status)
        self.workspace_page.nextStepRequested.connect(lambda: self._go_to_guided_next_step("Workspace"))
        self.dataset_page.nextStepRequested.connect(lambda: self._go_to_guided_next_step("Dataset"))
        self.planning_page.nextStepRequested.connect(lambda: self._go_to_guided_next_step("Planning"))
        self.processing_page.nextStepRequested.connect(lambda: self._go_to_guided_next_step("Processing"))
        self.results_page.nextStepRequested.connect(lambda: self._go_to_guided_next_step("Results"))

    def _configure_style(self) -> None:
        self.root_widget.setStyleSheet(
            """
            QWidget { background: #f7f8f9; color: #23313a; }
            #headerFrame { background: #eef3f4; color: #22323a; border-bottom: 1px solid #d8e1e5; }
            #titleLabel { font-size: 20px; font-weight: 700; }
            #subtitleLabel { color: #5f6f77; }
            #statusFrame { background: #f2f5f6; border-top: 1px solid #dbe3e6; }
            #pageHeading { font-size: 21px; font-weight: 700; margin: 12px 24px 6px 24px; color: #22323a; }
            #workflowStepIndicator { margin: 0 24px 6px 24px; color: #667780; font-size: 12px; background: transparent; }
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
            QLabel#statusBadge { font-size: 14px; font-weight: 600; border: 1px solid #dfe6e9; border-left: 4px solid #9eacb3; border-radius: 6px; padding: 10px 12px; background: #f8fafb; color: #22323a; }
            QLabel#statusBadge[tone="success"] { border-left-color: #3f7f52; background: #f5faf6; }
            QLabel#statusBadge[tone="progress"] { border-left-color: #497f9f; background: #f4f8fb; }
            QLabel#statusBadge[tone="warning"] { border-left-color: #b4842c; background: #fffaf0; }
            QLabel#statusBadge[tone="danger"] { border-left-color: #b45b52; background: #fff7f5; }
            QLabel#statusBadge[tone="muted"] { border-left-color: #8b969b; background: #f6f7f8; color: #58666d; }
            QLabel#statusBadge[tone="planned"] { border-left-color: #7a6da8; background: #f8f6fc; }
            #advisorList { font-size: 13px; border: 1px solid #dfe6e9; background: #ffffff; border-radius: 5px; }
            #advisorWarningList { font-size: 13px; border: 1px solid #e0cda8; background: #fffdf8; border-radius: 5px; }
            QListWidget { border: 1px solid #dfe6e9; background: #ffffff; border-radius: 4px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #eef2f3; }
            QListWidget::item:selected { background: #dde8ec; color: #1f2d35; }
            QGroupBox { font-weight: 600; margin-top: 12px; border: 1px solid #dfe6e9; border-radius: 6px; padding: 12px; background: #ffffff; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #32424a; }
            QPushButton { background: #ffffff; border: 1px solid #cfd9dd; border-radius: 4px; padding: 8px 12px; }
            QPushButton[buttonRole="primary"] { background: #2f6f7d; border-color: #275e6a; color: #ffffff; font-weight: 600; }
            QPushButton[buttonRole="secondary"] { background: #ffffff; border-color: #b9c9cf; color: #263840; }
            QPushButton[buttonRole="neutral"] { background: #f8fafb; border-color: #cfd9dd; color: #30414a; }
            QPushButton[buttonRole="danger"] { background: #fff7f5; border-color: #c98b84; color: #7a302b; }
            QPushButton:hover { background: #f0f4f5; }
            QPushButton[buttonRole="primary"]:hover { background: #285f6c; }
            QLineEdit, QTextEdit, QDoubleSpinBox, QComboBox { background: #ffffff; border: 1px solid #d4dee2; border-radius: 4px; padding: 5px; }
            QProgressBar { border: 1px solid #cfd9dd; border-radius: 4px; background: #ffffff; text-align: center; }
            QProgressBar::chunk { background: #5f8790; border-radius: 3px; }
            """
        )


    def _open_environment_and_refresh(self) -> None:
        """Open Environment and immediately refresh readiness."""
        self.ui.navigationList.setCurrentRow(self.PAGE_NAMES.index("Environment"))
        self.environment_page.refresh()

    def _notify(self, message: str, level: str = "info") -> None:
        """Show a lightweight QGIS message bar notification when available."""
        bar_getter = getattr(self.iface, "messageBar", None)
        bar = bar_getter() if callable(bar_getter) else None
        if bar is None or not hasattr(bar, "pushMessage"):
            return
        try:
            from qgis.core import Qgis

            qgis_level = {
                "success": getattr(Qgis, "Success", getattr(Qgis, "Info", 0)),
                "warning": getattr(Qgis, "Warning", 1),
                "error": getattr(Qgis, "Critical", 2),
                "info": getattr(Qgis, "Info", 0),
            }.get(level, getattr(Qgis, "Info", 0))
        except Exception:  # noqa: BLE001 - QGIS level constants vary by runtime.
            qgis_level = 0
        try:
            bar.pushMessage("PyForestScan", message, level=qgis_level, duration=5)
        except TypeError:
            try:
                bar.pushMessage("PyForestScan", message)
            except Exception:  # noqa: BLE001 - notifications must never break workflow actions.
                return
        except Exception:  # noqa: BLE001 - notifications must never break workflow actions.
            return

    def _set_environment_status(self, status: str) -> None:
        self.state = self.state.with_environment(status).with_activity("Environment verified", status)
        self._record_workspace_event("environment_refreshed", f"Environment verified: {status}")
        if self.ui.navigationList.currentRow() != self.PAGE_NAMES.index("Settings"):
            self.settings_page.refresh_backend_summary()
        self._save_workspace_session()
        self._refresh_home()
        self._update_status_bar()
        self._notify("Environment verified.", "success" if environment_is_ready(status) else "warning")

    def _set_dataset_pending(self, dataset_path: str) -> None:
        """Clear downstream workflow state when the selected dataset changes."""
        self.state = self.state.with_dataset_pending(dataset_path).with_activity("Dataset selected", Path(dataset_path).name)
        self.job_history = ()
        self.loaded_result_paths = set()
        self.batch_status = "Not started"
        self.planning_page.reset_for_new_dataset(Path(dataset_path).name)
        self.processing_page.set_run_context(None)
        self.results_page.set_run_context(None)
        self.advisor_page.reset_for_new_dataset()
        self._save_workspace_session()
        self._refresh_home()
        self._update_status_bar()
        self._notify("Dataset selected. Analyze it to continue.", "info")

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
        self._ensure_workspace_for_context(context)
        self._workspace_status(WorkspaceStatus.DATASET_SELECTED, True, "Build product plan")
        self._record_workspace_event("dataset_selected", f"Dataset selected: {Path(dataset_path).name}", {"dataset": str(dataset_path)})
        self._record_workspace_event("dataset_explored", f"Dataset explored: {Path(dataset_path).name}", {"report": str(context.dataset_report_html)})
        self._record_workspace_recent("dataset", dataset_path, Path(dataset_path).name)
        self._record_workspace_recent("output_folder", context.output_root, context.output_root.name)
        self._record_workspace_recent("report", context.dataset_report_html, "Dataset Report")
        self._save_workspace_session()
        self._refresh_home()
        self._update_status_bar()
        self._notify("Dataset loaded.", "success")

    def _set_planning_status(self, status: str, plan: object | None = None) -> None:
        state = self.state.with_planning(status).with_activity("Planning updated", status)
        if self.state.active_run is not None and plan is not None:
            self.processing_page.set_run_context(self.state.active_run)
            self.results_page.set_run_context(self.state.active_run)
            state = state.with_report_path(self.state.active_run.product_plan_html)
            state = state.with_report_path(self.state.active_run.product_plan_csv)
        self.state = state
        planning_complete = status == "Ready"
        self._workspace_status(WorkspaceStatus.PLANNING_COMPLETE, planning_complete, "Run selected products" if planning_complete else "Review product plan")
        self._record_workspace_event("planning_updated", f"Planning updated: {status}")
        if self.state.active_run is not None:
            self._record_workspace_recent("report", self.state.active_run.product_plan_html, "Product Plan")
        self._save_workspace_session()
        self._refresh_home()
        self._update_status_bar()
        self._notify("Product plan updated." if planning_complete else "Product plan needs review.", "success" if planning_complete else "warning")

    def _set_default_output_folder(self, folder: object) -> None:
        path = folder if isinstance(folder, Path) else None
        self.state = self.state.with_default_output_folder(path).with_activity("Default output folder", str(path) if path else "Cleared")
        self.dataset_page.set_default_output_folder(path)
        self.batch_page.set_default_output_folder(path)
        self._save_workspace_session()
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
        self._record_job_in_workspace(job)
        self._save_workspace_session()
        self._refresh_home()
        self._update_status_bar()
        if job.status == JobStatus.COMPLETED:
            self._notify("Processing completed.", "success")
        elif job.status == JobStatus.FAILED:
            self._notify("Processing failed. Review Technical Details.", "error")
        elif job.status == JobStatus.CANCELLED:
            self._notify("Processing cancelled.", "warning")

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
        self._workspace_status(WorkspaceStatus.BATCH_COMPLETE, True, "Review batch results")
        self._record_workspace_event("batch_complete", f"Batch complete: {self.batch_status}")
        for path in (summary_html, summary_csv, summary_json):
            if isinstance(path, Path):
                self._record_workspace_recent("batch_report", path, path.name)
        self._save_workspace_session()
        self._refresh_home()
        self._update_status_bar()
        self._notify("Batch completed." if failure_count == 0 else "Batch completed with files to review.", "success" if failure_count == 0 else "warning")

    def _set_outputs_loaded_status(self, message: str, loaded_count: int, candidate_count: int) -> None:
        """Record Load Outputs feedback and show a lightweight notification."""
        level = "success" if loaded_count else ("warning" if candidate_count else "info")
        self.loaded_result_paths.update(self.results_page.loaded_output_paths())
        self.state = self.state.with_activity("Outputs loaded" if loaded_count else "Load outputs", message)
        self._refresh_home()
        self.results_page._set_load_message(message)
        self._update_status_bar()
        self._notify(message, level)

    def _clear_current_run_state(self) -> None:
        """Clear active run state after the Results page is reset."""
        self.state = self.state.without_active_run().with_activity("Results cleared", "Current run cleared")
        self.job_history = ()
        self.loaded_result_paths = set()
        self._save_workspace_session()
        self._refresh_home()
        self._update_status_bar()
        self._notify("Current run cleared.", "info")

    def _set_backend_page_status(self, status: str, message: str) -> None:
        """Keep Environment and Home synchronized after Backend page actions."""
        self.state = self.state.with_backend(status)
        self.environment_page.refresh()
        self._refresh_home()
        self._update_status_bar()
        normalized = status.lower()
        level = "success" if "ready" in normalized else ("error" if "fail" in normalized else "warning")
        self._notify(message, level)


    def _ensure_workspace_for_context(self, context: RunContext) -> None:
        """Load or create the workspace for a run context output root."""
        try:
            self.workspace_manager.recent_limit = self.settings_page.maximum_recent_items_spin.value()
            self.workspace_manager.auto_save = self.settings_page.auto_save_workspace_check.isChecked()
            self.workspace = self.workspace_manager.load_workspace(context.output_root)
            session = self.workspace.session
            self.workspace = self.workspace.with_session(
                WorkspaceSession(
                    last_opened_workspace=self.workspace.workspace_dir,
                    last_selected_dataset=context.lidar_path,
                    last_output_folder=context.output_root,
                    last_planner_settings=session.last_planner_settings,
                    last_selected_products=session.last_selected_products,
                    last_page=self.PAGE_NAMES[self.ui.navigationList.currentRow()] if self.ui.navigationList.currentRow() >= 0 else session.last_page,
                    window_geometry=session.window_geometry,
                    floating=session.floating,
                    docked=session.docked,
                    remember_last_workspace=self.settings_page.remember_workspace_check.isChecked(),
                    remember_last_dataset=self.settings_page.remember_dataset_check.isChecked(),
                    remember_last_output_folder=self.settings_page.remember_output_folder_check.isChecked(),
                    maximum_recent_items=self.settings_page.maximum_recent_items_spin.value(),
                    auto_save_enabled=self.settings_page.auto_save_workspace_check.isChecked(),
                )
            )
            if self.workspace_manager.auto_save:
                self.workspace = self.workspace_manager.save_workspace(self.workspace)
        except Exception:  # noqa: BLE001 - workspace persistence must not break QGIS workflows.
            self.workspace = None

    def _workspace_status(self, status: WorkspaceStatus, value: bool, current_step: str) -> None:
        """Update workspace status if a workspace is active."""
        if self.workspace is None:
            return
        try:
            self.workspace = self.workspace_manager.update_state(self.workspace, status, value, current_step)
        except Exception:  # noqa: BLE001 - workspace persistence must not block processing.
            pass

    def _record_workspace_event(self, event_type: str, message: str, details: dict[str, str] | None = None) -> None:
        """Append a workspace timeline event when possible."""
        if self.workspace is None:
            return
        try:
            self.workspace = self.workspace_manager.add_timeline_event(self.workspace, event_type, message, details)
        except Exception:  # noqa: BLE001 - timeline persistence is best effort.
            pass

    def _record_workspace_recent(self, item_type: str, path: Path | str, label: str | None = None) -> None:
        """Record a recent workspace item when possible."""
        if self.workspace is None:
            return
        try:
            self.workspace = self.workspace_manager.add_recent_item(self.workspace, item_type, path, label)
        except Exception:  # noqa: BLE001 - recent persistence is best effort.
            pass

    def _record_job_in_workspace(self, job: JobRecord) -> None:
        """Record completed or failed jobs in workspace history."""
        if self.workspace is None or job.job_id in self._workspace_recorded_jobs:
            return
        if job.status not in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            return
        run = WorkspaceHistoryRun(
            run_id=job.job_id,
            products=tuple(job.requested_products),
            parameters={},
            success=job.status == JobStatus.COMPLETED,
            output_paths=tuple(result.path for result in job.results),
            started_at=job.created_at,
            finished_at=job.updated_at,
            error_message=job.error_message,
        )
        try:
            self.workspace = self.workspace_manager.append_history(self.workspace, run)
            if job.status == JobStatus.COMPLETED:
                self._workspace_status(WorkspaceStatus.PRODUCTS_GENERATED, bool(job.results), "Review results")
                self._record_workspace_event("products_generated", f"Products generated: {', '.join(job.requested_products)}")
            else:
                self._record_workspace_event("processing_failed", f"Processing {job.status.value}: {job.title}")
            for result in job.results:
                self._record_workspace_recent("output", result.path, result.description)
            self._workspace_recorded_jobs.add(job.job_id)
        except Exception:  # noqa: BLE001 - history persistence is best effort.
            pass

    def _save_workspace_session(self) -> None:
        """Persist global Mission Control session metadata."""
        current_page = self.PAGE_NAMES[self.ui.navigationList.currentRow()] if self.ui.navigationList.currentRow() >= 0 else None
        dataset_text = self.dataset_page.dataset_path_edit.text().strip()
        output_text = self.dataset_page.output_folder_edit.text().strip() or self.batch_page.output_folder_edit.text().strip()
        workspace_path = self.workspace.workspace_dir if self.workspace is not None else self.workspace_session.last_opened_workspace
        session = WorkspaceSession(
            last_opened_workspace=workspace_path if self.settings_page.remember_workspace_check.isChecked() else None,
            last_selected_dataset=Path(dataset_text) if dataset_text and self.settings_page.remember_dataset_check.isChecked() else None,
            last_output_folder=Path(output_text) if output_text and self.settings_page.remember_output_folder_check.isChecked() else None,
            last_planner_settings={
                "grid_resolution": str(self.planning_page.resolution_spin.value()),
                "height_bin_size": str(self.planning_page.height_bin_spin.value()),
            },
            last_selected_products=tuple(
                product.value for product, check in self.planning_page.product_checks.items() if check.isChecked()
            ),
            last_page=current_page,
            window_geometry=bytes(self.saveGeometry().toBase64()).decode("ascii"),
            floating=self.isFloating(),
            docked=not self.isFloating(),
            remember_last_workspace=self.settings_page.remember_workspace_check.isChecked(),
            remember_last_dataset=self.settings_page.remember_dataset_check.isChecked(),
            remember_last_output_folder=self.settings_page.remember_output_folder_check.isChecked(),
            maximum_recent_items=self.settings_page.maximum_recent_items_spin.value(),
            auto_save_enabled=self.settings_page.auto_save_workspace_check.isChecked(),
        )
        self.workspace_session = session
        try:
            self.workspace_manager.save_global_session(session)
        except Exception:  # noqa: BLE001 - session persistence is best effort.
            pass


    def _continue_last_workspace(self) -> None:
        """Open the most recent workspace when available."""
        paths = self.workspace_manager.list_recent_workspace_paths()
        if paths:
            self._open_workspace_path(paths[0])
            return
        if self.workspace_session.last_opened_workspace is not None:
            self._open_workspace_path(self.workspace_session.last_opened_workspace)

    def _start_new_workspace(self) -> None:
        """Create a new workspace under a user-selected output folder."""
        folder = QFileDialog.getExistingDirectory(self, "Choose workspace output folder")
        if not folder:
            return
        try:
            self.workspace = self.workspace_manager.create_workspace(Path(folder))
            self.workspace = self.workspace_manager.add_timeline_event(self.workspace, "workspace_opened", "Workspace opened")
            self.workspace_manager.record_recent_workspace(self.workspace)
        except Exception:  # noqa: BLE001 - workspace creation should fail softly in UI.
            self.workspace = None
            return
        self.dataset_page.set_default_output_folder(Path(folder))
        self.batch_page.set_default_output_folder(Path(folder))
        self.state = self.state.with_default_output_folder(Path(folder)).with_activity("Workspace opened", Path(folder).name)
        self._save_workspace_session()
        self._refresh_home()
        self._update_status_bar()
        self.ui.navigationList.setCurrentRow(self.PAGE_NAMES.index("Workspace"))
        self._notify("Workspace opened.", "success")

    def _open_workspace_path(self, workspace_path: object) -> None:
        """Open a recent workspace path."""
        path = Path(workspace_path)
        root = path.parent if path.name == ".pyforestscan" else path
        if not path.exists() and not (root / ".pyforestscan").exists():
            self.workspace_manager.remove_recent_workspace(path)
            self._refresh_home()
            return
        try:
            self.workspace = self.workspace_manager.load_workspace(root)
            self.workspace_manager.record_recent_workspace(self.workspace)
        except Exception:  # noqa: BLE001 - bad workspace should not break Mission Control.
            self.workspace = None
            return
        session = self.workspace.session
        if session.last_selected_dataset is not None:
            self.dataset_page.dataset_path_edit.setText(str(session.last_selected_dataset))
            self.state = self.state.with_dataset(str(session.last_selected_dataset))
        if session.last_output_folder is not None:
            self.dataset_page.output_folder_edit.setText(str(session.last_output_folder))
            self.batch_page.output_folder_edit.setText(str(session.last_output_folder))
            self.state = self.state.with_default_output_folder(session.last_output_folder)
        self.state = self.state.with_activity("Workspace opened", self.workspace.name)
        self._save_workspace_session()
        self._refresh_home()
        self._update_status_bar()
        self.ui.navigationList.setCurrentRow(self.PAGE_NAMES.index("Workspace"))
        self._notify("Workspace opened.", "success")

    def _remove_recent_workspace(self, workspace_path: object) -> None:
        """Remove a workspace from the recent list."""
        self.workspace_manager.remove_recent_workspace(Path(workspace_path))
        self._refresh_home()

    def _reset_current_workspace(self) -> None:
        """Reset current workspace state/history or clear the UI if no workspace exists."""
        if self.workspace is None:
            self.state = MissionControlState()
            self.job_history = ()
            self.loaded_result_paths = set()
            self.batch_status = "Not started"
            self.workspace_session = WorkspaceSession()
            self._save_workspace_session()
            self._refresh_home()
            self._update_status_bar()
            return
        try:
            self.workspace = self.workspace_manager.reset_workspace_state(self.workspace)
        except Exception:  # noqa: BLE001 - reset should fail softly.
            return
        self.job_history = ()
        self.loaded_result_paths = set()
        self.batch_status = "Not started"
        self.state = self.state.without_active_run().with_activity("Workspace reset", self.workspace.name)
        self._save_workspace_session()
        self._refresh_home()
        self._update_status_bar()

    def _save_workspace_notes(self, markdown: str) -> None:
        """Save notes for the active workspace."""
        if self.workspace is None:
            return
        try:
            self.workspace = self.workspace_manager.save_notes(self.workspace, markdown)
        except Exception:  # noqa: BLE001 - notes should fail softly.
            return
        self.state = self.state.with_activity("Notes saved", self.workspace.name)
        self._refresh_home()
        self._notify("Notes saved.", "success")


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

    def _project_summary(self) -> ProjectSummary:
        """Return the shared current-session project summary."""
        return build_project_summary(
            self.state,
            jobs=self.job_history,
            loaded_paths=self.loaded_result_paths,
            workspace=self.workspace.name if self.workspace is not None else None,
            project_crs=self._current_project_crs(),
        )

    def _current_project_crs(self) -> str | None:
        """Return the current QGIS project CRS label when QGIS exposes one."""
        try:
            from qgis.core import QgsProject

            crs = QgsProject.instance().crs()
            authid = crs.authid() if hasattr(crs, "authid") else ""
            description = crs.description() if hasattr(crs, "description") else ""
            return authid or description or None
        except Exception:  # noqa: BLE001 - QGIS-free tests and unusual projects should degrade softly.
            return None

    def _refresh_home(self) -> None:
        self.home_page.set_versions(self._pyforestscan_version())
        summary = self._project_summary()
        recent_run = str(self.state.active_run.run_folder) if self.state.active_run is not None else None
        self.home_page.set_summary(
            self.state.environment_status,
            self.state.latest_dataset,
            self.state.latest_project,
            self.batch_status,
            recent_run,
        )
        self.home_page.set_workspace(self.workspace)
        self.home_page.set_project_summary(summary)
        recent = summarize_recent_workspaces(self.workspace_manager.list_recent_workspace_paths(), self.workspace_session.maximum_recent_items)
        self.home_page.set_continue_available(self.workspace is not None or bool(recent))
        self.workspace_page.set_workspace(self.workspace)
        self.workspace_page.set_project_summary(summary)
        self.workspace_page.set_recent_workspaces(recent)
        self.home_page.set_activities(tuple((item.label, item.detail) for item in self.state.activities))
        self.results_page.set_run_context(self.state.active_run)
        self.advisor_page.set_run_context(self.state.active_run)
        self.results_page.set_report_paths(self.state.latest_report_paths)
        self.results_page.set_jobs(self.job_history)
        self.processing_page.set_project_summary(summary)
        self.results_page.set_project_summary(summary)
        self.advisor_page.set_project_summary(summary)
        self._refresh_guided_workflow()

    def _workflow_flags(self) -> dict[str, bool]:
        """Return compact workflow completion flags for guidance UI."""
        return {
            "environment_ready": environment_is_ready(self.state.environment_status),
            "workspace_ready": True,
            "dataset_loaded": bool(self.state.latest_dataset),
            "planning_ready": self.state.planning_status == "Ready",
            "processing_complete": self._has_outputs(),
            "batch_complete": self.batch_status != "Not started",
            "outputs_available": self._has_outputs(),
        }

    def _has_outputs(self) -> bool:
        """Return whether generated output products are available for review."""
        return any(job.results for job in self.job_history)

    def _refresh_guided_workflow(self) -> None:
        """Update subtle workflow orientation and next-step cards."""
        flags = self._workflow_flags()
        for page_name, page in zip(self.PAGE_NAMES, self.pages):
            if page_name in guided_workflow_pages() and page_name != "Home":
                page.set_workflow_indicator(guided_workflow_indicator(page_name, **flags))
                message, button, _target, enabled = guided_next_step(page_name, **flags)
                page.set_next_step(message, button, enabled)
            else:
                page.set_workflow_indicator(None)
        message, button, _target, enabled = guided_next_step("Home", **flags)
        backend_ready = flags["environment_ready"]
        workflow_status = "; ".join(
            guided_workflow_status_lines(
                backend_ready=backend_ready,
                dataset_loaded=flags["dataset_loaded"],
                planning_ready=flags["planning_ready"],
                outputs_available=flags["outputs_available"],
                processing_ready=flags["planning_ready"],
                batch_complete=flags["batch_complete"],
            )
        )
        recent_run = str(self.state.active_run.run_folder) if self.state.active_run is not None else None
        self.home_page.set_summary(
            self.state.environment_status,
            self.state.latest_dataset,
            self.state.latest_project,
            self.batch_status,
            recent_run,
            workflow_status=workflow_status,
            continue_label=button,
            continue_enabled=enabled,
        )
        self.home_page.set_project_summary(self._project_summary())

    def _go_to_guided_next_step(self, page_name: str) -> None:
        """Move to the recommended workflow page without forcing work to run."""
        _message, _button, target, enabled = guided_next_step(page_name, **self._workflow_flags())
        if enabled and target in self.PAGE_NAMES:
            self.ui.navigationList.setCurrentRow(self.PAGE_NAMES.index(target))

    def _continue_guided_workflow(self) -> None:
        """Continue from Home to the next incomplete workflow step."""
        self._go_to_guided_next_step("Home")

    def _update_status_bar(self) -> None:
        self.ui.environmentStatusLabel.setText(f"{readiness_marker_label(self.state.environment_status)} Environment: {self.state.environment_status}")
        self.ui.datasetStatusLabel.setText(f"Dataset: {Path(self.state.latest_dataset).name if self.state.latest_dataset else 'None'}")
        self.ui.planningStatusLabel.setText(f"Planning: {self.state.planning_status}")
        ready = "Ready" if environment_is_ready(self.state.environment_status) else "Needs attention"
        self.ui.readyStatusLabel.setText(f"{readiness_marker_label(self.state.environment_status)} {ready}")

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
