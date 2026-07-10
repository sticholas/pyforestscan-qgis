"""Mission Control page widgets.

These widgets orchestrate existing adapter-backed workflows. They do not call
PyForestScan directly. CHM execution is routed through JobManager, Pipeline, and
the adapter boundary.
"""

from __future__ import annotations

import json
import time
from html import escape
from pathlib import Path
from typing import Callable

from qgis.PyQt.QtCore import QObject, QSize, Qt, QThread, QTimer, QUrl, pyqtSignal
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStyle,
    QSizePolicy,
    QSpinBox,
    QDoubleSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.adapter import PyForestScanAdapter
from ..core.backend import BackendService
from ..core.qgis_compat import build_qgis_compatibility_report, format_qgis_compatibility_report
from ..core.batch import BatchProductSettings, BatchRequest, discover_lidar_files
from ..core.batch_executor import PARALLEL_SAFE_MODE, SEQUENTIAL_MODE, BatchExecutor
from ..core.batch_preflight import BatchPreflightReport, run_batch_preflight
from ..core.batch_runner import BatchExecutionError
from ..core.dataset_report import (
    DatasetExplorerReport,
    build_dataset_explorer_report,
    format_count_for_display,
    format_crs_for_display,
    format_density_for_display,
    report_to_dict,
    write_csv_summary,
    write_html_report,
    write_json_report,
)
from ..core.dependency_check import CheckStatus, EnvironmentReport
from ..core.exceptions import AdapterError, ProcessingError
from ..core.ept_subset import build_ept_subset_request, compact_ept_subset_summary
from ..core.lidar_inventory import LidarFolderRequest, discover_lidar_sources
from ..core.polygon_processing import build_polygon_processing_plan, polygon_preflight_summary
from ..core.polygon_source import POLYGON_VECTOR_FILE_FILTER, PolygonSource, polygon_source_summary, selected_feature_count_text
from ..core.polygon_normalization import normalize_polygon_source
from ..core.job_manager import JobExecutionError, JobManager
from ..core.knowledge import RecommendationReport
from ..core.jobs import JobRecord, JobStatus
from ..core.processing_footprint import ProcessingFootprint, footprint_from_plan_file
from ..core.product_plan import (
    PRODUCT_LABELS,
    ProductPlanError,
    ProductPlannerReport,
    ProductPlannerRequest,
    build_product_plan,
    write_plan_csv,
    write_plan_html,
    write_plan_json,
)
from ..core.types import ProductType
from ..core.workspace import (
    RecentWorkspaceSummary,
    RunContext,
    Workspace,
    WorkspaceSession,
    format_timeline_events,
    workspace_primary_action,
    workspace_status_label,
    create_run_context,
)
from .advisor import PRODUCT_EXPLANATIONS, QGIS_TOOL_INSTRUCTIONS
from .output_loading import LoadableOutput, collect_loadable_outputs, compact_dataset_summary_lines, output_loading_summary
from .state import ProjectSummary
from .qgis_footprint import FootprintPreview, add_footprint_layer, preview_from_report, zoom_to_footprint
from .polygon_source_selector import normalize_qgis_layer_selection, normalize_vector_file_selection, polygon_layer_items, vector_file_layer_options
from .raster_styling import apply_generated_raster_renderer, layer_display_name
from .ux_summary import action_icon_intent, backend_summary_from_environment, button_role_for_label, design_spacing_tokens, empty_state_message, environment_headline, home_environment_action_label, home_environment_readiness, primary_action_label, qgis_fallback_summary, readiness_status_text, routed_products_summary, status_badge_label, status_badge_tone, status_display_word, workflow_action_labels

ActivityCallback = Callable[[str, str], None]

DESIGN_SPACING = design_spacing_tokens()
SPACING_XS = DESIGN_SPACING["xs"]
SPACING_SM = DESIGN_SPACING["sm"]
SPACING_MD = DESIGN_SPACING["md"]
SPACING_LG = DESIGN_SPACING["lg"]
SPACING_XL = DESIGN_SPACING["xl"]
PAGE_MARGINS = (SPACING_XL, SPACING_MD, SPACING_XL, SPACING_XL)
SECTION_MARGINS = (SPACING_MD, SPACING_LG, SPACING_MD, SPACING_MD)
SECTION_SPACING = SPACING_MD
ACTION_ROW_SPACING = SPACING_SM
PRIMARY_BUTTON_HEIGHT = 40
SECONDARY_BUTTON_HEIGHT = 34
COMPACT_LIST_HEIGHT = 96
TECHNICAL_DETAIL_HEIGHT = 84


class MissionPage(QWidget):
    """Base class for Mission Control pages with one full-page scroll region."""

    nextStepRequested = pyqtSignal()

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        """Create a page with a title and full-width scrollable content."""
        super().__init__(parent)
        self.title = title
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        heading = QLabel(title)
        heading.setObjectName("pageHeading")
        heading.setWordWrap(True)
        self.main_layout.addWidget(heading)
        self.workflow_indicator_label = QLabel("")
        self.workflow_indicator_label.setObjectName("workflowStepIndicator")
        self.workflow_indicator_label.setWordWrap(True)
        self.workflow_indicator_label.setVisible(False)
        self.main_layout.addWidget(self.workflow_indicator_label)
        self.next_step_section: QGroupBox | None = None
        self.next_step_label: QLabel | None = None
        self.next_step_button: QPushButton | None = None

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("pageScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.content_widget = QWidget()
        self.content_widget.setObjectName("pageContent")
        self.content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(*PAGE_MARGINS)
        self.content_layout.setSpacing(SPACING_LG)
        self.scroll_area.setWidget(self.content_widget)
        self.main_layout.addWidget(self.scroll_area, 1)

    def add_section(self, title: str) -> QVBoxLayout:
        """Add a titled full-width section and return its layout."""
        group = QGroupBox(title)
        group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(*SECTION_MARGINS)
        layout.setSpacing(SECTION_SPACING)
        self.content_layout.addWidget(group)
        return layout

    def set_workflow_indicator(self, text: str | None) -> None:
        """Show or hide subtle completed/current/upcoming workflow context."""
        self.workflow_indicator_label.setText(text or "")
        self.workflow_indicator_label.setVisible(bool(text))

    def set_next_step(self, message: str, button_label: str, enabled: bool = True) -> None:
        """Show one concise next-step recommendation at the bottom of the page."""
        if self.next_step_section is None:
            layout = self.add_section("Next Step")
            self.next_step_section = layout.parentWidget()
            self.next_step_label = _body_label("")
            layout.addWidget(self.next_step_label)
            row = QHBoxLayout()
            row.setSpacing(ACTION_ROW_SPACING)
            self.next_step_button = QPushButton(button_label)
            self.next_step_button.setMinimumHeight(SECONDARY_BUTTON_HEIGHT)
            self.next_step_button.clicked.connect(self.nextStepRequested.emit)
            row.addWidget(self.next_step_button)
            row.addStretch(1)
            layout.addLayout(row)
        assert self.next_step_label is not None
        assert self.next_step_button is not None
        self.next_step_label.setText(f"Next: {message}")
        self.next_step_button.setText(button_label)
        self.next_step_button.setEnabled(enabled)
        _apply_button_role(self.next_step_button, "primary" if enabled else "neutral")
        self.next_step_section.setVisible(True)


class HomePage(MissionPage):
    """Mission Control workflow dashboard."""

    startSingleDatasetRequested = pyqtSignal()
    startBatchRequested = pyqtSignal()
    continueLastRequested = pyqtSignal()
    continueWorkflowRequested = pyqtSignal()
    checkEnvironmentRequested = pyqtSignal()
    refreshSummaryRequested = pyqtSignal()

    def __init__(self, plugin_version: str, parent: QWidget | None = None) -> None:
        """Create the home dashboard."""
        super().__init__("Home", parent)
        dashboard = self.add_section("Workflow Overview")
        self.backend_label = _body_label("Backend: unknown")
        self.environment_label = _body_label("Environment: Check readiness")
        self.dataset_label = _body_label("Dataset: Not selected")
        self.workflow_label = _body_label("Workflow: Not started")
        self.output_label = _body_label("Current output folder: None")
        self.products_generated_label = _body_label("Products generated: None")
        self.products_loaded_label = _body_label("Products loaded: None")
        self.last_run_label = _body_label("Last run: None")
        for label in (
            self.backend_label,
            self.environment_label,
            self.dataset_label,
            self.workflow_label,
            self.output_label,
            self.products_generated_label,
            self.products_loaded_label,
            self.last_run_label,
        ):
            dashboard.addWidget(label)

        actions = QHBoxLayout()
        self.continue_button = QPushButton("Continue")
        self.continue_button.setMinimumHeight(PRIMARY_BUTTON_HEIGHT)
        self.continue_button.clicked.connect(self.continueWorkflowRequested.emit)
        _apply_button_role(self.continue_button, "primary")
        self.check_environment_button = QPushButton("Check Environment")
        self.check_environment_button.setMinimumHeight(SECONDARY_BUTTON_HEIGHT)
        self.check_environment_button.clicked.connect(self.checkEnvironmentRequested.emit)
        _apply_button_role(self.check_environment_button, "neutral")
        self.refresh_summary_button = QPushButton("Refresh Summary")
        self.refresh_summary_button.setMinimumHeight(SECONDARY_BUTTON_HEIGHT)
        self.refresh_summary_button.clicked.connect(self.refreshSummaryRequested.emit)
        _apply_button_role(self.refresh_summary_button, "neutral")
        actions.addWidget(self.continue_button)
        actions.addWidget(self.check_environment_button)
        actions.addWidget(self.refresh_summary_button)
        actions.addStretch(1)
        dashboard.addLayout(actions)

        versions = _collapsible_section(self.content_layout, "Version Details", checked=False)
        version_group, version_layout = versions
        self.plugin_version_label = _details_label(f"Plugin version: {plugin_version}")
        self.pyforestscan_version_label = _details_label("PyForestScan version: Unknown")
        version_layout.addWidget(self.plugin_version_label)
        version_layout.addWidget(self.pyforestscan_version_label)
        _wire_collapsible_group(version_group)

        activity_group, activity = _collapsible_section(self.content_layout, "Recent Activity", checked=False)
        self.activity_list = QListWidget()
        activity.addWidget(self.activity_list)
        _wire_collapsible_group(activity_group)

    def set_versions(self, pyforestscan_version: str | None) -> None:
        """Update version labels."""
        self.pyforestscan_version_label.setText(f"PyForestScan version: {pyforestscan_version or 'Unknown'}")

    def set_summary(self, environment: str, dataset: str | None, project: str | None, batch_status: str = "Not started", recent_run: str | None = None, workflow_status: str | None = None, continue_label: str = "Continue", continue_enabled: bool = True) -> None:
        """Update dashboard labels."""
        current = Path(dataset).name if dataset else "Not selected"
        backend_text = backend_summary_from_environment(environment).replace("Backend status", "Backend")
        self.backend_label.setText(readiness_status_text(environment, backend_text))
        self.environment_label.setText(readiness_status_text(environment, f"Environment: {home_environment_readiness(environment)}"))
        self.dataset_label.setText(f"Dataset: {current}")
        self.workflow_label.setText(f"Workflow: {workflow_status or _next_home_action(environment, dataset, batch_status)}")
        self.output_label.setText(f"Current output folder: {recent_run or 'None'}")
        self.continue_button.setText(continue_label)
        self.continue_button.setEnabled(continue_enabled)
        self.check_environment_button.setText(home_environment_action_label(environment))

    def set_workspace(self, workspace: Workspace | None) -> None:
        """Display active workspace status on Home."""
        if workspace is None:
            return
        session = workspace.session
        self.dataset_label.setText(f"Dataset: {Path(session.last_selected_dataset).name if session.last_selected_dataset else workspace.name}")
        self.output_label.setText(f"Current output folder: {session.last_output_folder or workspace.output_root}")
        self.workflow_label.setText(f"Workflow: {workspace_primary_action(workspace)}")

    def set_project_summary(self, summary: ProjectSummary) -> None:
        """Display the shared current-session project summary."""
        self.dataset_label.setText(f"Dataset: {summary.dataset_name} ({summary.dataset_type})")
        self.output_label.setText(f"Current output folder: {summary.output_folder or 'None'}")
        self.products_generated_label.setText(summary.generated_summary())
        self.products_loaded_label.setText(summary.loaded_summary())
        self.last_run_label.setText(f"Last run: {summary.last_processing_time or 'None'}")

    def set_continue_available(self, available: bool) -> None:
        """Enable Continue Last Run when a current or recent workspace exists."""
        if not available and not self.continue_button.isEnabled():
            self.continue_button.setEnabled(False)

    def set_activities(self, activities: tuple[tuple[str, str], ...]) -> None:
        """Display recent activity."""
        self.activity_list.clear()
        for label, detail in activities[:8]:
            self.activity_list.addItem(f"{label}: {detail}" if detail else label)


class WorkspacePage(MissionPage):
    """Workspace welcome, resume, timeline, and notes page."""

    continueLastRequested = pyqtSignal()
    startNewRequested = pyqtSignal()
    workspaceSelected = pyqtSignal(object)
    removeRecentRequested = pyqtSignal(object)
    resetWorkspaceRequested = pyqtSignal()
    notesSaveRequested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the Workspace page."""
        super().__init__("Workspace", parent)
        self.recent_workspaces: tuple[RecentWorkspaceSummary, ...] = ()
        self.current_workspace: Workspace | None = None

        welcome = self.add_section("Welcome")
        self.workspace_status_card = QLabel(empty_state_message("workspace"))
        self.workspace_status_card.setObjectName("advisorMetric")
        self.workspace_status_card.setWordWrap(True)
        welcome.addWidget(self.workspace_status_card)
        action_row = QHBoxLayout()
        self.continue_button = QPushButton(primary_action_label("workspace"))
        self.continue_button.setMinimumHeight(PRIMARY_BUTTON_HEIGHT)
        self.continue_button.clicked.connect(self.continueLastRequested.emit)
        _apply_button_role(self.continue_button, "primary")
        self.start_new_button = QPushButton("Start New Workspace")
        self.start_new_button.setMinimumHeight(PRIMARY_BUTTON_HEIGHT)
        self.start_new_button.clicked.connect(self.startNewRequested.emit)
        _apply_button_role(self.start_new_button, "secondary")
        action_row.addWidget(self.continue_button)
        action_row.addWidget(self.start_new_button)
        action_row.addStretch(1)
        welcome.addLayout(action_row)

        recent = self.add_section("Recent Workspaces")
        self.recent_section = recent.parentWidget()
        self.recent_list = QListWidget()
        self.recent_list.itemDoubleClicked.connect(lambda _item: self.open_selected_workspace())
        recent.addWidget(self.recent_list)
        recent_row = QHBoxLayout()
        open_recent = QPushButton("Open Selected")
        open_recent.clicked.connect(self.open_selected_workspace)
        remove_recent = QPushButton("Remove Missing/Selected")
        remove_recent.clicked.connect(self.remove_selected_workspace)
        _apply_button_role(remove_recent, "danger")
        recent_row.addWidget(open_recent)
        recent_row.addWidget(remove_recent)
        recent_row.addStretch(1)
        recent.addLayout(recent_row)
        self.recent_section.setVisible(False)

        status = self.add_section("Workspace Status")
        self.status_section = status.parentWidget()
        self.current_step_label = _body_label("Current step: None")
        self.completion_label = _body_label("Completion: 0%")
        self.dataset_label = _body_label("Last dataset: None")
        self.output_label = _body_label("Last output folder: None")
        self.primary_action_label = _body_label("Primary next action: start or continue a workspace.")
        self.current_project_label = _body_label("Current project: Unknown")
        self.products_label = _body_label("Products: None")
        self.session_status_label = _body_label("Session: not started")
        for label in (
            self.current_step_label,
            self.completion_label,
            self.current_project_label,
            self.dataset_label,
            self.output_label,
            self.products_label,
            self.session_status_label,
            self.primary_action_label,
        ):
            status.addWidget(label)

        runs = self.add_section("Recent Runs")
        self.runs_section = runs.parentWidget()
        self.runs_list = QListWidget()
        runs.addWidget(self.runs_list)

        outputs = self.add_section("Key Output Links")
        self.outputs_section = outputs.parentWidget()
        self.output_links_list = QListWidget()
        outputs.addWidget(self.output_links_list)

        timeline = self.add_section("Timeline Summary")
        self.timeline_section = timeline.parentWidget()
        self.timeline_list = QListWidget()
        timeline.addWidget(self.timeline_list)

        notes_group, notes = _collapsible_section(self.content_layout, "Notes", checked=False)
        self.notes_section = notes_group
        self.notes_edit = QTextEdit()
        self.notes_edit.setMinimumHeight(TECHNICAL_DETAIL_HEIGHT)
        notes.addWidget(self.notes_edit)
        save_notes = QPushButton("Save Notes")
        save_notes.clicked.connect(lambda: self.notesSaveRequested.emit(self.notes_edit.toPlainText()))
        notes.addWidget(save_notes)
        _wire_collapsible_group(notes_group)

        reset_group, reset = _collapsible_section(self.content_layout, "Troubleshooting: reset workspace", checked=False)
        self.reset_section = reset_group
        reset.addWidget(_body_label("Clear the current workspace from Mission Control or reset its progress/history. Workspace files remain local."))
        self.reset_button = QPushButton("Clear / Reset Current Workspace")
        self.reset_button.clicked.connect(self.resetWorkspaceRequested.emit)
        _apply_button_role(self.reset_button, "danger")
        reset.addWidget(self.reset_button)
        _wire_collapsible_group(reset_group)
        for section in (self.status_section, self.runs_section, self.outputs_section, self.timeline_section, self.notes_section, self.reset_section):
            section.setVisible(False)

    def set_workspace(self, workspace: Workspace | None) -> None:
        """Display the current workspace."""
        self.current_workspace = workspace
        if workspace is None:
            self.workspace_status_card.setText(empty_state_message("workspace"))
            self.current_step_label.setText("Current step: None")
            self.completion_label.setText("Completion: 0%")
            self.dataset_label.setText("Last dataset: None")
            self.output_label.setText("Last output folder: None")
            self.primary_action_label.setText("Primary next action: start or continue a workspace.")
            self.current_project_label.setText("Current project: Unknown")
            self.products_label.setText("Products: None")
            self.session_status_label.setText("Session: not started")
            self.runs_list.clear()
            self.output_links_list.clear()
            self.timeline_list.clear()
            self.notes_edit.setPlainText("")
            for section in (self.status_section, self.runs_section, self.outputs_section, self.timeline_section, self.notes_section, self.reset_section):
                section.setVisible(False)
            return
        for section in (self.status_section, self.notes_section, self.reset_section):
            section.setVisible(True)
        session = workspace.session
        self.workspace_status_card.setText(workspace_status_label(workspace))
        self.current_step_label.setText(f"Current step: {workspace.state.current_step}")
        self.completion_label.setText(f"Completion: {workspace.state.completion_percentage}%")
        self.dataset_label.setText(f"Last dataset: {session.last_selected_dataset or 'None'}")
        self.output_label.setText(f"Last output folder: {session.last_output_folder or workspace.output_root}")
        self.primary_action_label.setText(f"Primary next action: {workspace_primary_action(workspace)}")
        self.notes_edit.setPlainText(workspace.notes.markdown)
        self._set_runs(workspace)
        self._set_outputs(workspace)
        self._set_timeline(workspace)

    def set_project_summary(self, summary: ProjectSummary) -> None:
        """Display compact current-session state independent of persisted history."""
        for section in (self.status_section,):
            section.setVisible(True)
        project = summary.workspace or "Current QGIS project"
        crs = summary.project_crs or "Unknown CRS"
        self.current_project_label.setText(f"Current project: {project}; CRS: {crs}")
        self.dataset_label.setText(f"Dataset: {summary.dataset_name} ({summary.dataset_type})")
        self.output_label.setText(f"Output folder: {summary.output_folder or 'None'}")
        self.products_label.setText(summary.generated_summary())
        self.session_status_label.setText(summary.compact_status())

    def set_recent_workspaces(self, recent_workspaces: tuple[RecentWorkspaceSummary, ...]) -> None:
        """Display recent workspace choices."""
        self.recent_workspaces = recent_workspaces[:10]
        self.recent_list.clear()
        for item in self.recent_workspaces:
            suffix = "" if item.exists else " [missing]"
            self.recent_list.addItem(f"{item.label}{suffix}\n{item.path}")
        has_recent = bool(self.recent_workspaces)
        self.recent_section.setVisible(has_recent)
        self.continue_button.setEnabled(has_recent)

    def open_selected_workspace(self) -> None:
        """Emit the selected recent workspace path."""
        row = self.recent_list.currentRow()
        if 0 <= row < len(self.recent_workspaces):
            self.workspaceSelected.emit(self.recent_workspaces[row].path)

    def remove_selected_workspace(self) -> None:
        """Request removal of the selected recent workspace path."""
        row = self.recent_list.currentRow()
        if 0 <= row < len(self.recent_workspaces):
            self.removeRecentRequested.emit(self.recent_workspaces[row].path)

    def _set_runs(self, workspace: Workspace) -> None:
        self.runs_list.clear()
        for run in workspace.history.runs[:10]:
            status = "success" if run.success else "failed"
            products = ", ".join(run.products) or "no products"
            self.runs_list.addItem(f"{status.upper()} - {products}\n{run.finished_at or run.started_at or run.run_id}")
        self.runs_section.setVisible(bool(workspace.history.runs))

    def _set_outputs(self, workspace: Workspace) -> None:
        self.output_links_list.clear()
        outputs = []
        for run in workspace.history.runs:
            outputs.extend(run.output_paths)
        for path in outputs[:10]:
            self.output_links_list.addItem(str(path))
        self.outputs_section.setVisible(bool(outputs))

    def _set_timeline(self, workspace: Workspace) -> None:
        self.timeline_list.clear()
        lines = format_timeline_events(workspace.timeline, limit=12)
        for line in lines:
            self.timeline_list.addItem(line)
        self.timeline_section.setVisible(bool(lines))


class EnvironmentPage(MissionPage):
    """Environment diagnostics page."""

    environmentChanged = pyqtSignal(str)
    backendSettingsRequested = pyqtSignal()

    def __init__(self, adapter: PyForestScanAdapter, parent: QWidget | None = None) -> None:
        """Create the environment page."""
        super().__init__("Environment", parent)
        self.adapter = adapter
        controls = self.add_section("Readiness")
        button_row = QHBoxLayout()
        self.refresh_button = QPushButton(primary_action_label("environment"))
        self.refresh_button.clicked.connect(self.refresh)
        _apply_button_role(self.refresh_button, "primary")
        self.open_backend_settings_button = QPushButton("Open Backend Settings")
        self.open_backend_settings_button.clicked.connect(self.backendSettingsRequested.emit)
        _apply_button_role(self.open_backend_settings_button, "secondary")
        button_row.addWidget(self.refresh_button)
        button_row.addWidget(self.open_backend_settings_button)
        button_row.addStretch(1)
        controls.addLayout(button_row)
        self.status_label = QLabel()
        _set_status_badge(self.status_label, "NOT CONFIGURED", readiness_status_text("NOT CONFIGURED", "Status: Not set up - refresh to check readiness."))
        self.pbm_status_label = _body_label("PBM backend status: not checked")
        self.execution_label = _body_label("Execution backend: not checked")
        self.scope_label = _body_label(routed_products_summary())
        self.next_step_label = _body_label("Recommended next step: refresh environment.")
        for label in (self.status_label, self.pbm_status_label, self.execution_label, self.scope_label, self.next_step_label):
            controls.addWidget(label)

        fallback_group, fallback = _collapsible_section(self.content_layout, "QGIS Python fallback environment", checked=False)
        fallback.addWidget(_details_label("Optional when PBM backend is READY. Expand only for tools that still use QGIS Python or for troubleshooting."))
        self.fallback_checks_list = QListWidget()
        fallback.addWidget(self.fallback_checks_list)
        _wire_collapsible_group(fallback_group)

        technical_group, technical = _collapsible_section(self.content_layout, "Technical dependency details", checked=False)
        self.checks_list = QListWidget()
        technical.addWidget(self.checks_list)
        _wire_collapsible_group(technical_group)

    def refresh(self) -> None:
        """Run adapter-backed environment validation."""
        self.refresh_button.setEnabled(False)
        _set_status_badge(self.status_label, "RUNNING", readiness_status_text("RUNNING", "Status: Running - checking environment."))
        QApplication.processEvents()
        try:
            report = self.adapter.check_environment()
            self.set_report(report)
        finally:
            self.refresh_button.setEnabled(True)

    def set_report(self, report: EnvironmentReport) -> None:
        """Display an environment report."""
        _set_status_badge(self.status_label, report.readiness.value, readiness_status_text(report.readiness.value, environment_headline(report.readiness.value)))
        self.checks_list.clear()
        self.fallback_checks_list.clear()
        pbm_message = "PBM backend status: not checked"
        execution_message = "Execution backend: not checked"
        next_step = "Recommended next step: continue with Dataset Explorer or Batch when READY."
        fallback_names = {"pyforestscan", "pdal", "osgeo.gdal", "rasterio", "numpy"}
        for check in report.checks:
            icon = _status_icon(check.status.value)
            version = f" ({check.version})" if check.version else ""
            guidance = f"\nNext: {check.guidance}" if check.guidance else ""
            row = f"{icon} {check.name}{version}: {check.message}{guidance}"
            self.checks_list.addItem(row)
            if check.name == "PBM managed backend":
                pbm_message = f"PBM backend status: {check.message}"
            elif check.name == "Active execution backend":
                execution_message = f"Execution backend: {check.message}"
            elif check.name in fallback_names:
                self.fallback_checks_list.addItem(row)
        if report.readiness.value == "NOT READY":
            next_step = "Recommended next step: open Backend Settings and install or repair PBM."
        elif report.readiness.value == "READY WITH QGIS PYTHON":
            next_step = "Recommended next step: run guided workflows, or install PBM for no-manual-setup routed products."
        self.pbm_status_label.setText(pbm_message)
        self.execution_label.setText(execution_message)
        self.scope_label.setText(f"{routed_products_summary()}\n{qgis_fallback_summary()}")
        self.next_step_label.setText(next_step)
        self.environmentChanged.emit(report.readiness.value)


class DatasetPage(MissionPage):
    """Dataset inspection page with automatic run-folder creation."""

    datasetExplored = pyqtSignal(object, str, object)
    datasetSelectionChanged = pyqtSignal(str)

    def __init__(self, adapter: PyForestScanAdapter, iface: object | None = None, parent: QWidget | None = None) -> None:
        """Create the dataset page."""
        super().__init__("Dataset", parent)
        self.adapter = adapter
        self.iface = iface
        self.active_run: RunContext | None = None
        self.footprint_preview: FootprintPreview | None = None
        picker = self.add_section("Dataset")
        row = QHBoxLayout()
        self.dataset_path_edit = QLineEdit()
        self.dataset_path_edit.setPlaceholderText("Choose LAS, LAZ, COPC, or ept.json")
        self.browse_dataset_button = QPushButton("Select Dataset")
        self.browse_dataset_button.clicked.connect(self.browse_dataset)
        row.addWidget(self.dataset_path_edit)
        row.addWidget(self.browse_dataset_button)
        picker.addLayout(row)

        output_row = QHBoxLayout()
        self.output_folder_edit = QLineEdit()
        self.output_folder_edit.setPlaceholderText("Choose output folder")
        output_browse = QPushButton("Browse")
        output_browse.clicked.connect(self.browse_output_folder)
        output_row.addWidget(self.output_folder_edit)
        output_row.addWidget(output_browse)
        picker.addLayout(output_row)

        dataset_actions = QHBoxLayout()
        dataset_actions.setSpacing(ACTION_ROW_SPACING)
        self.analyze_button = QPushButton(primary_action_label("dataset"))
        self.analyze_button.clicked.connect(self.run_explorer)
        _apply_button_role(self.analyze_button, "primary")
        self.dataset_refresh_button = QPushButton("Refresh Dataset Page")
        self.dataset_refresh_button.clicked.connect(self.refresh_dataset_page)
        _apply_button_role(self.dataset_refresh_button, "neutral")
        dataset_actions.addWidget(self.analyze_button)
        dataset_actions.addWidget(self.dataset_refresh_button)
        dataset_actions.addStretch(1)
        picker.addLayout(dataset_actions)

        summary = self.add_section("Dataset Summary")
        self.summary_section = summary.parentWidget()
        self.summary_text = _body_label(empty_state_message("dataset"))
        summary.addWidget(self.summary_text)
        self.summary_section.setVisible(False)

        metadata_group, metadata = _collapsible_section(self.content_layout, "Technical Metadata", checked=False)
        self.dataset_technical_text = _details_label("Dataset technical metadata appears after analysis.")
        metadata.addWidget(self.dataset_technical_text)
        _wire_collapsible_group(metadata_group)

        ept_group, ept_layout = _collapsible_section(self.content_layout, "EPT Subset", checked=False)
        ept_layout.addWidget(_body_label("Extract a bounded EPT subset to LAS/LAZ, then use it as the current dataset."))
        ept_form = QFormLayout()
        ept_form.setVerticalSpacing(SECTION_SPACING)
        self.ept_srs_edit = QLineEdit("EPSG:4326")
        self.ept_bounds_edit = QLineEdit()
        self.ept_bounds_edit.setPlaceholderText("xmin,xmax,ymin,ymax[,zmin,zmax]")
        self.ept_thin_radius_spin = QDoubleSpinBox()
        self.ept_thin_radius_spin.setDecimals(3)
        self.ept_thin_radius_spin.setMinimum(0.0)
        self.ept_thin_radius_spin.setSpecialValueText("None")
        self.ept_hag_combo = QComboBox()
        self.ept_hag_combo.addItems(("None", "Delaunay HAG", "DTM-backed HAG"))
        self.ept_dtm_edit = QLineEdit()
        self.ept_dtm_edit.setPlaceholderText("Required only for DTM-backed HAG")
        dtm_row = QHBoxLayout()
        dtm_browse = QPushButton("Browse")
        dtm_browse.clicked.connect(self.browse_ept_dtm)
        dtm_row.addWidget(self.ept_dtm_edit, 1)
        dtm_row.addWidget(dtm_browse, 0)
        self.ept_crop_check = QCheckBox("Crop with polygon")
        self.ept_poly_edit = QLineEdit()
        self.ept_poly_edit.setPlaceholderText("Polygon WKT or polygon file path")
        self.ept_reproject_check = QCheckBox("Reproject while reading")
        self.ept_output_edit = QLineEdit()
        self.ept_output_edit.setPlaceholderText("outputs/ept_subset.laz")
        output_path_row = QHBoxLayout()
        output_browse = QPushButton("Browse")
        output_browse.clicked.connect(self.browse_ept_output)
        output_path_row.addWidget(self.ept_output_edit, 1)
        output_path_row.addWidget(output_browse, 0)
        ept_form.addRow("SRS / CRS", self.ept_srs_edit)
        ept_form.addRow("Bounds", self.ept_bounds_edit)
        ept_form.addRow("Thin radius", self.ept_thin_radius_spin)
        ept_form.addRow("HAG method", self.ept_hag_combo)
        ept_form.addRow("DTM", dtm_row)
        ept_form.addRow("Crop", self.ept_crop_check)
        ept_form.addRow("Polygon", self.ept_poly_edit)
        ept_form.addRow("Reproject", self.ept_reproject_check)
        ept_form.addRow("Output LAS/LAZ", output_path_row)
        ept_layout.addLayout(ept_form)
        ept_actions = QHBoxLayout()
        ept_actions.setSpacing(ACTION_ROW_SPACING)
        self.ept_extract_button = QPushButton("Extract Subset")
        self.ept_extract_button.clicked.connect(self.extract_ept_subset)
        _apply_button_role(self.ept_extract_button, "primary")
        self.ept_use_output_button = QPushButton("Use Extracted Subset as Dataset")
        self.ept_use_output_button.clicked.connect(self.use_extracted_subset_as_dataset)
        self.ept_use_output_button.setEnabled(False)
        _apply_button_role(self.ept_use_output_button, "secondary")
        ept_actions.addWidget(self.ept_extract_button)
        ept_actions.addWidget(self.ept_use_output_button)
        ept_actions.addStretch(1)
        ept_layout.addLayout(ept_actions)
        self.ept_message_label = _details_label("Select an ept.json source to enable subset extraction.")
        ept_layout.addWidget(self.ept_message_label)
        self.ept_subset_output_path: Path | None = None
        _wire_collapsible_group(ept_group)

        polygon_group, polygon_layout = _collapsible_section(self.content_layout, "Process Folder by Polygon", checked=False)
        self.polygon_group = polygon_group
        polygon_layout.addWidget(_body_label("Choose a LiDAR folder, choose a polygon from QGIS or disk, select products, then run preflight."))
        polygon_form = QFormLayout()
        polygon_form.setVerticalSpacing(SECTION_SPACING)
        self.polygon_folder_edit = QLineEdit()
        self.polygon_folder_edit.setPlaceholderText("Folder containing LAS, LAZ, COPC, or local ept.json")
        polygon_folder_row = QHBoxLayout()
        polygon_folder_browse = QPushButton("Browse")
        polygon_folder_browse.clicked.connect(self.browse_polygon_folder)
        polygon_folder_row.addWidget(self.polygon_folder_edit, 1)
        polygon_folder_row.addWidget(polygon_folder_browse, 0)
        self.polygon_output_edit = QLineEdit()
        self.polygon_output_edit.setPlaceholderText("Choose polygon processing output folder")
        polygon_output_row = QHBoxLayout()
        polygon_output_browse = QPushButton("Browse")
        polygon_output_browse.clicked.connect(self.browse_polygon_output_folder)
        polygon_output_row.addWidget(self.polygon_output_edit, 1)
        polygon_output_row.addWidget(polygon_output_browse, 0)
        self.polygon_source_combo = QComboBox()
        self.polygon_source_combo.addItem("Use QGIS Layer", "qgis")
        self.polygon_source_combo.addItem("Choose Vector File", "file")
        self.polygon_source_combo.addItem("Advanced WKT", "wkt")
        self.polygon_source_combo.currentIndexChanged.connect(self._update_polygon_source_visibility)
        polygon_form.addRow("LiDAR folder", polygon_folder_row)
        polygon_form.addRow("Polygon source", self.polygon_source_combo)
        polygon_form.addRow("Output folder", polygon_output_row)
        polygon_layout.addLayout(polygon_form)

        self.polygon_qgis_source_frame = QFrame()
        qgis_source_layout = QVBoxLayout(self.polygon_qgis_source_frame)
        qgis_source_layout.setContentsMargins(0, 0, 0, 0)
        qgis_source_layout.setSpacing(SECTION_SPACING)
        qgis_layer_row = QHBoxLayout()
        self.polygon_layer_combo = QComboBox()
        self.polygon_layer_combo.currentIndexChanged.connect(self._update_selected_polygon_layer_status)
        self.polygon_refresh_layers_button = QPushButton("Refresh Layers")
        self.polygon_refresh_layers_button.clicked.connect(self.refresh_polygon_layers)
        _apply_button_role(self.polygon_refresh_layers_button, "neutral")
        qgis_layer_row.addWidget(self.polygon_layer_combo, 1)
        qgis_layer_row.addWidget(self.polygon_refresh_layers_button, 0)
        qgis_source_layout.addLayout(qgis_layer_row)
        qgis_mode_row = QHBoxLayout()
        self.polygon_layer_mode_combo = QComboBox()
        self.polygon_layer_mode_combo.addItem("Use Selected Features", "selected")
        self.polygon_layer_mode_combo.addItem("Use Entire Layer", "full")
        self.polygon_dissolve_check = QCheckBox("Dissolve multiple features")
        self.polygon_dissolve_check.setChecked(True)
        qgis_mode_row.addWidget(self.polygon_layer_mode_combo, 0)
        qgis_mode_row.addWidget(self.polygon_dissolve_check, 0)
        qgis_mode_row.addStretch(1)
        qgis_source_layout.addLayout(qgis_mode_row)
        self.polygon_layer_status_label = _details_label("Refresh Layers to choose a loaded polygon layer.")
        qgis_source_layout.addWidget(self.polygon_layer_status_label)
        polygon_layout.addWidget(self.polygon_qgis_source_frame)

        self.polygon_vector_source_frame = QFrame()
        vector_source_layout = QVBoxLayout(self.polygon_vector_source_frame)
        vector_source_layout.setContentsMargins(0, 0, 0, 0)
        vector_source_layout.setSpacing(SECTION_SPACING)
        vector_file_row = QHBoxLayout()
        self.polygon_vector_file_edit = QLineEdit()
        self.polygon_vector_file_edit.setPlaceholderText("GeoPackage, Shapefile, GeoJSON, FlatGeobuf, or KML")
        self.polygon_vector_browse_button = QPushButton("Choose Vector File")
        self.polygon_vector_browse_button.clicked.connect(self.browse_polygon_vector_file)
        _apply_button_role(self.polygon_vector_browse_button, "secondary")
        vector_file_row.addWidget(self.polygon_vector_file_edit, 1)
        vector_file_row.addWidget(self.polygon_vector_browse_button, 0)
        vector_source_layout.addLayout(vector_file_row)
        self.polygon_vector_layer_combo = QComboBox()
        self.polygon_vector_layer_combo.setVisible(False)
        vector_source_layout.addWidget(self.polygon_vector_layer_combo)
        self.polygon_vector_status_label = _details_label("Guided default: all polygon features are dissolved into one processing geometry.")
        vector_source_layout.addWidget(self.polygon_vector_status_label)
        polygon_layout.addWidget(self.polygon_vector_source_frame)

        self.polygon_wkt_group, polygon_wkt_layout = _collapsible_section(polygon_layout, "Advanced WKT", checked=False)
        wkt_form = QFormLayout()
        wkt_form.setVerticalSpacing(SECTION_SPACING)
        self.polygon_wkt_edit = QLineEdit()
        self.polygon_wkt_edit.setPlaceholderText("POLYGON or MULTIPOLYGON WKT")
        self.polygon_crs_edit = QLineEdit("EPSG:4326")
        self.polygon_processing_crs_edit = QLineEdit()
        self.polygon_processing_crs_edit.setPlaceholderText("Optional CRS override, for example EPSG:32610")
        wkt_form.addRow("Polygon WKT", self.polygon_wkt_edit)
        wkt_form.addRow("Source CRS", self.polygon_crs_edit)
        wkt_form.addRow("Processing CRS", self.polygon_processing_crs_edit)
        polygon_wkt_layout.addLayout(wkt_form)
        _wire_collapsible_group(self.polygon_wkt_group)

        products_row = QHBoxLayout()
        self.polygon_product_checks: dict[ProductType, QCheckBox] = {}
        for product, label in PRODUCT_LABELS.items():
            check = QCheckBox(label.split(" (")[0])
            check.setChecked(product is ProductType.CHM)
            self.polygon_product_checks[product] = check
            products_row.addWidget(check)
        polygon_layout.addLayout(products_row)
        polygon_actions = QHBoxLayout()
        polygon_actions.setSpacing(ACTION_ROW_SPACING)
        self.polygon_run_button = QPushButton("Analyze / Preflight")
        self.polygon_run_button.clicked.connect(self.run_polygon_processing_preflight)
        _apply_button_role(self.polygon_run_button, "primary")
        polygon_actions.addWidget(self.polygon_run_button)
        polygon_actions.addStretch(1)
        polygon_layout.addLayout(polygon_actions)
        self.polygon_preflight_text = _details_label("Choose a polygon layer or vector file; WKT is available under Advanced.")
        polygon_layout.addWidget(self.polygon_preflight_text)
        self.refresh_polygon_layers()
        self._update_polygon_source_visibility()
        _wire_collapsible_group(polygon_group)
        polygon_group.toggled.connect(lambda _checked: self._update_polygon_source_visibility())

        spatial = self.add_section("Spatial Preview")
        self.spatial_section = spatial.parentWidget()
        self.footprint_text = QTextEdit()
        self.footprint_text.setReadOnly(True)
        spatial.addWidget(self.footprint_text)
        self.spatial_section.setVisible(False)
        spatial_buttons = QHBoxLayout()
        self.add_footprint_button = QPushButton("Add Footprint Layer")
        self.add_footprint_button.clicked.connect(self.add_footprint_layer)
        _apply_button_role(self.add_footprint_button, "secondary")
        self.add_footprint_button.setEnabled(False)
        self.zoom_footprint_button = QPushButton("Zoom to Footprint")
        self.zoom_footprint_button.clicked.connect(self.zoom_to_footprint)
        _apply_button_role(self.zoom_footprint_button, "secondary")
        self.zoom_footprint_button.setEnabled(False)
        self.open_report_button = QPushButton("Open Report")
        self.open_report_button.clicked.connect(self.open_report)
        _apply_button_role(self.open_report_button, "secondary")
        self.open_report_button.setEnabled(False)
        spatial_buttons.addWidget(self.add_footprint_button)
        spatial_buttons.addWidget(self.zoom_footprint_button)
        spatial_buttons.addWidget(self.open_report_button)
        spatial.addLayout(spatial_buttons)

    def set_default_output_folder(self, folder: Path | None) -> None:
        """Use the configured output folder when the page has no explicit folder."""
        if folder is not None and not self.output_folder_edit.text().strip():
            self.output_folder_edit.setText(str(folder))

    def browse_dataset(self) -> None:
        """Open a file picker for supported point-cloud datasets."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose lidar dataset",
            "",
            "Point cloud datasets (*.las *.laz *.copc *.copc.laz *ept.json);;All files (*.*)",
        )
        if path:
            previous = self.dataset_path_edit.text().strip()
            self.dataset_path_edit.setText(path)
            self.browse_dataset_button.setText("Change Dataset")
            _apply_button_role(self.browse_dataset_button, "secondary")
            self.analyze_button.setText("Analyze Dataset")
            if path != previous:
                self._reset_dataset_outputs()
                self.datasetSelectionChanged.emit(path)

    def browse_output_folder(self) -> None:
        """Choose the root output folder for Mission Control runs."""
        path = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if path:
            self.output_folder_edit.setText(path)

    def browse_polygon_folder(self) -> None:
        """Choose a LiDAR folder for polygon-driven processing."""
        path = QFileDialog.getExistingDirectory(self, "Choose LiDAR folder")
        if path:
            self.polygon_folder_edit.setText(path)

    def browse_polygon_output_folder(self) -> None:
        """Choose an output folder for polygon-driven processing."""
        path = QFileDialog.getExistingDirectory(self, "Choose polygon processing output folder")
        if path:
            self.polygon_output_edit.setText(path)

    def browse_polygon_vector_file(self) -> None:
        """Choose a polygon vector file for folder preflight."""
        path, _ = QFileDialog.getOpenFileName(self, "Choose polygon vector file", "", POLYGON_VECTOR_FILE_FILTER)
        if path:
            self.polygon_vector_file_edit.setText(path)
            self._refresh_polygon_vector_layers(path)

    def refresh_polygon_layers(self) -> None:
        """Refresh loaded QGIS polygon layers and preserve selection when possible."""
        previous = self.polygon_layer_combo.currentData()
        previous_id = getattr(previous, "layer_id", None)
        self.polygon_layer_combo.blockSignals(True)
        self.polygon_layer_combo.clear()
        items = polygon_layer_items(self.iface)
        for item in items:
            self.polygon_layer_combo.addItem(item.label, item)
        if previous_id:
            for index in range(self.polygon_layer_combo.count()):
                item = self.polygon_layer_combo.itemData(index)
                if getattr(item, "layer_id", None) == previous_id:
                    self.polygon_layer_combo.setCurrentIndex(index)
                    break
        self.polygon_layer_combo.blockSignals(False)
        if not items:
            self.polygon_layer_status_label.setText("No polygon layers are loaded. Add a polygon layer to QGIS or choose a vector file from disk.")
        else:
            current = self.polygon_layer_combo.currentData()
            if current is not None and getattr(current, "selected_feature_count", 0) > 0:
                self.polygon_layer_mode_combo.setCurrentIndex(0)
            elif current is not None:
                self.polygon_layer_mode_combo.setCurrentIndex(1)
            self._update_selected_polygon_layer_status()

    def _update_selected_polygon_layer_status(self, *_args: object) -> None:
        item = self.polygon_layer_combo.currentData()
        if item is None:
            self.polygon_layer_status_label.setText("No polygon layer selected.")
            return
        selected = selected_feature_count_text(getattr(item, "selected_feature_count", 0))
        guidance = "Use Selected Features is ready." if getattr(item, "selected_feature_count", 0) else "No selected features; use the entire layer or select polygon features on the map."
        self.polygon_layer_status_label.setText(f"{item.name}: {selected}; CRS {item.crs or 'unknown'}. {guidance}")

    def _update_polygon_source_visibility(self, *_args: object) -> None:
        mode = self.polygon_source_combo.currentData()
        container_visible = not hasattr(self, "polygon_group") or self.polygon_group.isChecked()
        self.polygon_qgis_source_frame.setVisible(container_visible and mode == "qgis")
        self.polygon_vector_source_frame.setVisible(container_visible and mode == "file")
        self.polygon_wkt_group.setVisible(container_visible and mode == "wkt")
        if mode == "wkt":
            self.polygon_wkt_group.setChecked(True)
        if mode == "qgis" and container_visible:
            self.refresh_polygon_layers()

    def _refresh_polygon_vector_layers(self, path: str) -> None:
        self.polygon_vector_layer_combo.clear()
        self.polygon_vector_layer_combo.setVisible(False)
        try:
            options = vector_file_layer_options(path)
        except Exception as exc:  # noqa: BLE001 - report file inspection failures concisely.
            self.polygon_vector_status_label.setText(f"Vector file could not be inspected: {exc}")
            return
        if not options:
            self.polygon_vector_status_label.setText("No polygon layers were found in this vector file. Point and line layers are not accepted.")
            return
        for option in options:
            self.polygon_vector_layer_combo.addItem(option.label, option)
        self.polygon_vector_layer_combo.setVisible(len(options) > 1)
        if len(options) > 1:
            self.polygon_vector_status_label.setText("GeoPackage/container has multiple polygon layers. Choose one; all features are dissolved for preflight.")
        else:
            option = options[0]
            self.polygon_vector_status_label.setText(f"{option.name}: {option.geometry_type}, CRS {option.crs or 'unknown'}. All features will be dissolved.")

    def _normalized_polygon_selection(self):
        mode = self.polygon_source_combo.currentData()
        processing_crs = self.polygon_processing_crs_edit.text().strip() if hasattr(self, "polygon_processing_crs_edit") else ""
        if mode == "qgis":
            item = self.polygon_layer_combo.currentData()
            if item is None:
                raise ValueError("Choose a loaded QGIS polygon layer or choose a vector file.")
            use_selected = self.polygon_layer_mode_combo.currentData() == "selected"
            return normalize_qgis_layer_selection(
                self.iface,
                item.layer_id,
                use_selected=use_selected,
                dissolve=self.polygon_dissolve_check.isChecked(),
                processing_crs=processing_crs,
            )
        if mode == "file":
            path = self.polygon_vector_file_edit.text().strip()
            if not path:
                raise ValueError("Choose a polygon vector file.")
            if self.polygon_vector_layer_combo.count() == 0:
                self._refresh_polygon_vector_layers(path)
            option = self.polygon_vector_layer_combo.currentData()
            return normalize_vector_file_selection(
                path,
                layer_uri=getattr(option, "uri", None),
                layer_name=getattr(option, "name", None),
                processing_crs=processing_crs,
            )
        source = PolygonSource(
            source_mode="wkt",
            polygon_wkt=self.polygon_wkt_edit.text(),
            source_crs=self.polygon_crs_edit.text(),
            processing_crs=processing_crs or self.polygon_crs_edit.text(),
        )
        return normalize_polygon_source(source)

    def run_polygon_processing_preflight(self) -> None:
        """Build a polygon-folder preflight plan without unbounded point reads."""
        folder = self.polygon_folder_edit.text().strip()
        output = self.polygon_output_edit.text().strip() or self.output_folder_edit.text().strip()
        products = tuple(product.value for product, check in self.polygon_product_checks.items() if check.isChecked())
        if not folder or not output:
            self.polygon_preflight_text.setText("Choose a LiDAR folder and output folder before running polygon processing.")
            return
        try:
            normalized = self._normalized_polygon_selection()
            inventory = discover_lidar_sources(LidarFolderRequest(Path(folder), recursive=True, include_ept=True))
            plan = build_polygon_processing_plan(inventory, normalized.to_polygon_selection(), Path(output), products, processing_crs=normalized.processing_crs)
        except Exception as exc:  # noqa: BLE001 - preflight should report concise guidance.
            self.polygon_preflight_text.setText(f"Polygon processing preflight failed: {exc}")
            return
        lines = [polygon_source_summary(normalized), *polygon_preflight_summary(plan)]
        lines.append("Execution note: PBM/chunked clipped processing is required before generating products from this plan.")
        self.polygon_preflight_text.setText("\n".join(lines))

    def browse_ept_dtm(self) -> None:
        """Choose a DTM raster for DTM-backed EPT HAG."""
        path, _ = QFileDialog.getOpenFileName(self, "Choose DTM GeoTIFF", "", "GeoTIFF files (*.tif *.tiff);;All files (*.*)")
        if path:
            self.ept_dtm_edit.setText(path)

    def browse_ept_output(self) -> None:
        """Choose the LAS/LAZ output path for an extracted EPT subset."""
        path, _ = QFileDialog.getSaveFileName(self, "Choose EPT subset output", str(self._default_ept_output_path()), "LAS/LAZ files (*.las *.laz);;All files (*.*)")
        if path:
            self.ept_output_edit.setText(path)

    def refresh_dataset_page(self) -> None:
        """Recover Dataset page button states without deleting outputs or backend state."""
        has_dataset = bool(self.dataset_path_edit.text().strip())
        self.browse_dataset_button.setEnabled(True)
        self.browse_dataset_button.setText("Change Dataset" if has_dataset else "Select Dataset")
        _apply_button_role(self.browse_dataset_button, "secondary" if has_dataset else "neutral")
        self.analyze_button.setEnabled(True)
        self.ept_extract_button.setEnabled(True)
        self.ept_use_output_button.setEnabled(self.ept_subset_output_path is not None)
        self.refresh_polygon_layers()
        self._set_ept_message("Dataset page refreshed. EPT subset extraction is available for ept.json sources.")
        if not self.summary_text.text().strip():
            self._set_dataset_message(empty_state_message("dataset"))

    def extract_ept_subset(self) -> None:
        """Extract the selected EPT subset and offer it as the active dataset."""
        source = self.dataset_path_edit.text().strip()
        if not source:
            self._set_ept_message("Select an ept.json source before extracting a subset.")
            return
        output = self.ept_output_edit.text().strip() or str(self._default_ept_output_path())
        self.ept_output_edit.setText(output)
        method = self.ept_hag_combo.currentText().lower()
        thin_radius = self.ept_thin_radius_spin.value() if self.ept_thin_radius_spin.value() > 0 else None
        try:
            request = build_ept_subset_request(
                input_path=source,
                crs=self.ept_srs_edit.text(),
                output_path=output,
                bounds_text=self.ept_bounds_edit.text(),
                thin_radius=thin_radius,
                hag=method.startswith("delaunay"),
                hag_dtm=method.startswith("dtm"),
                dtm_path=self.ept_dtm_edit.text().strip() or None,
                crop_poly=self.ept_crop_check.isChecked(),
                poly=self.ept_poly_edit.text(),
                reproject=self.ept_reproject_check.isChecked(),
            )
        except ProcessingError as exc:
            self._set_ept_message(str(exc))
            return
        self.ept_extract_button.setEnabled(False)
        self._set_ept_message("Extracting EPT subset...")
        QApplication.processEvents()
        try:
            result = self.adapter.extract_lidar_subset(request)
        except (AdapterError, ProcessingError) as exc:
            self._set_ept_message(f"EPT subset extraction failed.\n{exc}")
            return
        finally:
            self.ept_extract_button.setEnabled(True)
        self.ept_subset_output_path = result.output_path
        self.ept_use_output_button.setEnabled(True)
        self._set_ept_message(compact_ept_subset_summary(result) + "\nNext: use the extracted subset as the current dataset or load it in QGIS.")

    def use_extracted_subset_as_dataset(self) -> None:
        """Switch the Dataset page to the extracted LAS/LAZ subset."""
        if self.ept_subset_output_path is None:
            self._set_ept_message("Extract an EPT subset before using it as the dataset.")
            return
        self.dataset_path_edit.setText(str(self.ept_subset_output_path))
        self.browse_dataset_button.setText("Change Dataset")
        _apply_button_role(self.browse_dataset_button, "secondary")
        self.analyze_button.setText("Analyze Dataset")
        self._reset_dataset_outputs()
        self.datasetSelectionChanged.emit(str(self.ept_subset_output_path))
        self._set_dataset_message("Extracted subset selected. Click Analyze Dataset to inspect it.")

    def _default_ept_output_path(self) -> Path:
        if self.active_run is not None:
            return self.active_run.outputs_dir / "ept_subset.laz"
        output_root = self.output_folder_edit.text().strip()
        if output_root:
            return Path(output_root) / "ept_subset.laz"
        source = self.dataset_path_edit.text().strip()
        return Path(source).parent / "ept_subset.laz" if source else Path("ept_subset.laz")

    def _set_ept_message(self, message: str) -> None:
        self.ept_message_label.setText(message)

    def run_explorer(self) -> None:
        """Run adapter-backed dataset inspection and write internal reports."""
        path = self.dataset_path_edit.text().strip()
        output_root = self.output_folder_edit.text().strip()
        if not path:
            self._set_dataset_message(empty_state_message("dataset"))
            return
        if not output_root:
            self._set_dataset_message("No output folder selected.\nChoose where Mission Control should write reports and products.")
            return
        context = create_run_context(path, output_root).ensure_directories()
        try:
            self.analyze_button.setEnabled(False)
            self.browse_dataset_button.setEnabled(False)
            self._set_dataset_message("Preparing dataset inspection...")
            QApplication.processEvents()
            inspection = self.adapter.inspect_dataset(path)
            report = build_dataset_explorer_report(inspection)
            write_json_report(report, context.dataset_report_json)
            write_html_report(report, context.dataset_report_html)
            write_csv_summary(report, context.dataset_summary_csv)
        except AdapterError as exc:
            self._set_dataset_message(f"Dataset inspection failed.\n{exc}")
            return
        except OSError as exc:
            self._set_dataset_message(f"Dataset reports could not be written.\n{exc}")
            return
        finally:
            self.analyze_button.setEnabled(True)
            self.browse_dataset_button.setEnabled(True)
        self.active_run = context
        self.set_report(report, context)
        self.set_footprint_preview(report, path, context)
        self.datasetExplored.emit(report, path, context)

    def set_report(self, report: DatasetExplorerReport, context: RunContext | None = None) -> None:
        """Display a Dataset Explorer report summary."""
        self.summary_text.setText("\n".join(compact_dataset_summary_lines(report)))
        technical_lines = [
            f"Density: {format_density_for_display(report.estimated_density)}",
            f"Point format: {report.point_format or 'Unknown'}",
            f"Metadata source: {report.metadata_source}",
        ]
        if report.dimensions:
            technical_lines.append(f"Dimensions: {', '.join(report.dimensions)}")
        if report.warnings:
            technical_lines.extend(("Warnings:", *[f"- {warning.code}: {warning.message}" for warning in report.warnings], ""))
        if report.products:
            technical_lines.extend(("Available products:", *[f"- {item.label}: {item.status}" for item in report.products], ""))
        if context:
            technical_lines.extend((f"Run folder: {context.run_folder}", f"Dataset Report: {context.dataset_report_html}"))
        self.dataset_technical_text.setText("\n".join(technical_lines).strip() or "No technical metadata warnings.")
        self.summary_section.setVisible(True)

    def _set_dataset_message(self, message: str) -> None:
        """Show a compact Dataset page empty or warning state."""
        self.summary_text.setText(message)
        self.summary_section.setVisible(True)

    def _reset_dataset_outputs(self) -> None:
        """Clear analysis-dependent UI when the selected dataset changes."""
        self.active_run = None
        self.footprint_preview = None
        self.summary_text.setText("Dataset selected. Click Analyze Dataset to inspect it.")
        self.summary_section.setVisible(True)
        self.dataset_technical_text.setText("Dataset technical metadata appears after analysis.")
        self.footprint_text.clear()
        self.spatial_section.setVisible(False)
        self.add_footprint_button.setEnabled(False)
        self.zoom_footprint_button.setEnabled(False)
        self.open_report_button.setEnabled(False)
        self.ept_use_output_button.setEnabled(self.ept_subset_output_path is not None)

    def set_footprint_preview(self, report: DatasetExplorerReport, dataset_path: str, context: RunContext | None = None) -> None:
        """Display a footprint preview built from Dataset Explorer bounds."""
        self.footprint_preview = preview_from_report(report, dataset_path)
        self.open_report_button.setEnabled(context is not None)
        if self.footprint_preview is None:
            self.footprint_text.setPlainText("Footprint unavailable: Dataset Explorer did not report usable XY bounds.")
            self.add_footprint_button.setEnabled(False)
            self.zoom_footprint_button.setEnabled(False)
            self.spatial_section.setVisible(True)
            return
        preview = self.footprint_preview
        crs = preview.crs or "Unknown"
        lines = [
            "Footprint status: READY",
            f"CRS: {crs}",
            f"Coordinate extent: {preview.extent_text}",
            f"Approximate area: {preview.area:g} square map units",
            f"Center point: {preview.center_text}",
        ]
        if preview.warnings:
            lines.extend(f"Warning: {message}" for message in preview.warnings)
        self.footprint_text.setPlainText("\n".join(lines))
        self.spatial_section.setVisible(True)
        self.add_footprint_button.setEnabled(True)
        self.zoom_footprint_button.setEnabled(bool(preview.crs))

    def add_footprint_layer(self) -> None:
        """Add the current footprint preview to the QGIS project."""
        if self.footprint_preview is None:
            self.footprint_text.setPlainText("Run Dataset Explorer before adding a footprint layer.")
            return
        result = add_footprint_layer(self.footprint_preview, self.iface)
        self._append_footprint_message(result.message)

    def zoom_to_footprint(self) -> None:
        """Zoom the QGIS map canvas to the current footprint preview."""
        if self.footprint_preview is None:
            self.footprint_text.setPlainText("Run Dataset Explorer before zooming to a footprint.")
            return
        result = zoom_to_footprint(self.footprint_preview, self.iface)
        self._append_footprint_message(result.message)

    def open_report(self) -> None:
        """Open the Dataset Explorer HTML report for the active run."""
        if self.active_run is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.active_run.dataset_report_html)))

    def _append_footprint_message(self, message: str) -> None:
        current = self.footprint_text.toPlainText().strip()
        self.footprint_text.setPlainText(f"{current}\n\n{message}" if current else message)


class ScientificAdvisorPage(MissionPage):
    """Scientific Advisor page driven by the deterministic Knowledge Engine."""

    def __init__(self, iface: object | None = None, parent: QWidget | None = None) -> None:
        """Create the advisor page."""
        super().__init__("Scientific Advisor", parent)
        self.iface = iface
        self.run_context: RunContext | None = None
        self.completed_products: tuple[str, ...] = ()

        self.content_widget.setObjectName("advisorBody")
        self.advisor_layout = self.content_layout
        self.advisor_layout.setContentsMargins(*PAGE_MARGINS)
        self.advisor_layout.setSpacing(SPACING_LG)

        executive = self._add_card("Executive Summary")
        self.executive_summary_label = _body_label(empty_state_message("advisor"))
        self.session_context_label = _details_label("Session: no active dataset or products yet.")
        executive.addWidget(self.executive_summary_label)
        executive.addWidget(self.session_context_label)

        overview = self._add_card("Dataset Health")
        self.overview_card = overview.parentWidget()
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(SECTION_SPACING)
        self.score_label = _advisor_metric_card("Dataset score", "Run Dataset Explorer to evaluate.")
        self.confidence_label = _advisor_metric_card("Confidence / readiness", "Unknown")
        metrics_row.addWidget(self.score_label)
        metrics_row.addWidget(self.confidence_label)
        overview.addLayout(metrics_row)

        recommendations = self._add_card("Key Recommendations")
        self.recommendations_card = recommendations.parentWidget()
        self.recommendation_list = _readable_list()
        recommendations.addWidget(self.recommendation_list)

        warnings = self._add_card("Warnings")
        self.warnings_card = warnings.parentWidget()
        self.warning_list = _readable_list()
        self.warning_list.setObjectName("advisorWarningList")
        warnings.addWidget(self.warning_list)

        products = self._add_card("Recommended Products")
        self.products_card = products.parentWidget()
        self.product_list = _readable_list()
        products.addWidget(self.product_list)

        parameters = self._add_card("Recommended Parameters")
        self.parameters_card = parameters.parentWidget()
        self.parameter_list = _readable_list()
        parameters.addWidget(self.parameter_list)

        qgis_tools = self._add_card("Recommended Next Actions")
        self.qgis_tools_card = qgis_tools.parentWidget()
        self.qgis_tools_summary = _body_label("After processing, inspect generated layers in QGIS Layer Styling and Histogram before sharing results.")
        qgis_tools.addWidget(self.qgis_tools_summary)
        self.open_output_folder_button = QPushButton("Open Output Folder")
        self.open_output_folder_button.setMinimumHeight(SECONDARY_BUTTON_HEIGHT)
        self.open_output_folder_button.clicked.connect(self.open_output_folder)
        _apply_button_role(self.open_output_folder_button, "primary")
        qgis_tools.addWidget(self.open_output_folder_button)
        tools_group, tools_layout = _collapsible_section(self.advisor_layout, "QGIS Tool Instructions", checked=False)
        self.qgis_tools_details = _details_label(_tool_instruction_text())
        tools_layout.addWidget(self.qgis_tools_details)
        _wire_collapsible_group(tools_group)

        notes_group, notes = _collapsible_section(self.advisor_layout, "Scientific Notes", checked=False)
        self.notes_summary = _body_label("Recommendations will appear after Dataset Explorer runs. Threshold-based guidance is configurable and must be calibrated for production interpretation.")
        notes.addWidget(self.notes_summary)
        self.notes_details = _details_label("")
        notes.addWidget(self.notes_details)
        _wire_collapsible_group(notes_group)

        cards_group, cards = _collapsible_section(self.advisor_layout, "Product Explanations", checked=False)
        product_grid = QVBoxLayout()
        product_grid.setSpacing(SECTION_SPACING)
        for explanation in PRODUCT_EXPLANATIONS:
            product_grid.addWidget(_product_explanation_card(explanation))
        cards.addLayout(product_grid)
        _wire_collapsible_group(cards_group)

        next_steps = self._add_card("Next Steps")
        self.next_steps_card = next_steps.parentWidget()
        self.next_steps_label = _body_label("Run Dataset Explorer to generate top-priority next steps.")
        next_steps.addWidget(self.next_steps_label)
        for card in (self.overview_card, self.recommendations_card, self.warnings_card, self.products_card, self.parameters_card, self.qgis_tools_card, self.next_steps_card):
            card.setVisible(False)
        self.advisor_layout.addStretch(1)

    def _add_card(self, title: str) -> QVBoxLayout:
        """Add a spacious Advisor card section and return its layout."""
        frame = QFrame()
        frame.setObjectName("advisorCard")
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_LG)
        layout.setSpacing(SECTION_SPACING)
        heading = QLabel(title)
        heading.setObjectName("advisorSectionHeading")
        heading.setWordWrap(True)
        layout.addWidget(heading)
        self.advisor_layout.addWidget(frame)
        return layout

    def set_run_context(self, context: RunContext | None) -> None:
        """Store active run context for output-folder actions."""
        self.run_context = context

    def set_project_summary(self, summary: ProjectSummary) -> None:
        """Display compact session context for Advisor recommendations."""
        self.session_context_label.setText(
            f"Session: {summary.dataset_name}; {summary.generated_summary()}; {summary.loaded_summary()}"
        )

    def reset_for_new_dataset(self) -> None:
        """Clear recommendation content when a different dataset is selected."""
        self.run_context = None
        self.completed_products = ()
        self.executive_summary_label.setText("Dataset selected. Analyze it to receive recommendations.")
        self.session_context_label.setText("Session: dataset changed; recommendations are pending.")
        self.notes_summary.setText("Recommendations will appear after Dataset Explorer runs.")
        self.notes_details.setText("")
        self.next_steps_label.setText("Run Dataset Explorer to generate top-priority next steps.")
        for card in (self.overview_card, self.recommendations_card, self.warnings_card, self.products_card, self.parameters_card, self.qgis_tools_card, self.next_steps_card):
            card.setVisible(False)

    def set_recommendation_report(self, report: RecommendationReport) -> None:
        """Display a Knowledge Engine recommendation report."""
        has_guidance = bool(report.suggested_next_actions or report.warnings or report.recommended_products or report.recommended_parameters)
        if not has_guidance:
            self.executive_summary_label.setText(
                "Dataset analyzed. No recommendations were produced for this dataset.\n"
                "Next: continue to Planning and choose products manually."
            )
            for card in (self.overview_card, self.recommendations_card, self.warnings_card, self.products_card, self.parameters_card, self.qgis_tools_card, self.next_steps_card):
                card.setVisible(False)
            return
        self.overview_card.setVisible(True)
        self.score_label.setText(f"<b>Dataset score</b><br>{report.dataset_score}/100")
        self.confidence_label.setText(f"<b>Confidence / readiness</b><br>{_stars(report.confidence_stars)} ({report.confidence_stars}/5)")
        best_product = report.recommended_products[0].label if report.recommended_products else "No product recommendation yet"
        key_warning = report.warnings[0].reason if report.warnings else "No blocking warning from the Knowledge Engine"
        next_action = report.suggested_next_actions[0].suggested_action if report.suggested_next_actions else "Build a Product Plan when the dataset report is ready"
        self.executive_summary_label.setText(
            f"Dataset readiness: {report.dataset_score}/100 with {_stars(report.confidence_stars)} confidence.\n"
            f"Best product to consider: {best_product}.\n"
            f"Key warning: {key_warning}.\n"
            f"Next: {next_action}"
        )

        self.recommendation_list.clear()
        for item in report.suggested_next_actions[:4]:
            _add_advisor_item(self.recommendation_list, f"{item.reason}\nNext: {item.suggested_action}")
        self.recommendations_card.setVisible(bool(report.suggested_next_actions))

        self.warning_list.clear()
        for item in report.warnings[:5]:
            _add_advisor_item(self.warning_list, f"{item.severity.value.upper()} - {item.reason}\nAction: {item.suggested_action}", 68)
        if len(report.warnings) > 5:
            _add_advisor_item(self.warning_list, f"{len(report.warnings) - 5} additional actionable warning(s) are included in Scientific Notes.")
        self.warnings_card.setVisible(bool(report.warnings))

        self.product_list.clear()
        for product in report.recommended_products[:6]:
            _add_advisor_item(self.product_list, f"{product.label}: {product.status}\n{product.reason}")
        self.products_card.setVisible(bool(report.recommended_products))

        self.parameter_list.clear()
        for parameter in report.recommended_parameters[:6]:
            calibration = " Calibration required." if parameter.calibration_required else ""
            _add_advisor_item(self.parameter_list, f"{parameter.product} {parameter.name}: {parameter.value} {parameter.unit}\n{parameter.reason}{calibration}", 68)
        self.parameters_card.setVisible(bool(report.recommended_parameters))
        self.qgis_tools_card.setVisible(bool(report.recommended_products))
        self.next_steps_card.setVisible(True)

        note_count = len(report.scientific_notes)
        threshold_count = len([threshold for threshold in report.thresholds if threshold.calibration_required])
        self.notes_summary.setText(
            f"{note_count} scientific note(s) and {threshold_count} calibration-sensitive threshold(s) are available. "
            "Use the details below for transparent rationale before interpreting products."
        )
        scientific_notes = [f"* {item.code}: {item.reason} {item.scientific_note or ''}" for item in report.scientific_notes]
        threshold_notes = [f"* {threshold.name}: {threshold.value if threshold.value is not None else 'unset'} {threshold.unit}. {threshold.rationale}" for threshold in report.thresholds if threshold.calibration_required]
        self.notes_details.setText(
            "<b>More details</b><br>"
            + _html_lines(("Scientific notes:", *scientific_notes, "", "Configurable thresholds:", *threshold_notes))
        )
        self._update_next_steps(report)

    def set_completed_products(self, products: tuple[str, ...]) -> None:
        """Update next-step context after processing completes."""
        self.completed_products = products
        if products:
            completed = ", ".join(_product_label(product) for product in products)
            self.next_steps_label.setText(
                f"Completed products: {completed}\n\n"
                "Next: inspect loaded layers with Layer Styling and Histogram, compare extents/CRS, and open the final run summary."
            )

    def open_processing_toolbox(self) -> None:
        """Open QGIS Processing Toolbox when the iface exposes a stable hook."""
        method = getattr(self.iface, "openProcessingToolbox", None) if self.iface is not None else None
        if callable(method):
            method()
            return
        self.qgis_tools_details.setText(_html_lines((_tool_instruction_text(), "", "Processing Toolbox: open it from Processing > Toolbox in QGIS.")))

    def open_layer_styling(self) -> None:
        """Open selected-layer properties when available, otherwise show instructions."""
        layer = _selected_layer(self.iface)
        method = getattr(self.iface, "showLayerProperties", None) if self.iface is not None else None
        if layer is not None and callable(method):
            method(layer)
            return
        self.qgis_tools_details.setText(_html_lines((_tool_instruction_text(), "", "Layer Styling: select a raster layer, then open Layer Styling or Layer Properties > Symbology.")))

    def zoom_to_selected_layer(self) -> None:
        """Zoom the main QGIS canvas to the selected layer when available."""
        layer = _selected_layer(self.iface)
        canvas = self.iface.mapCanvas() if self.iface is not None and hasattr(self.iface, "mapCanvas") else None
        if layer is not None and canvas is not None and hasattr(layer, "extent"):
            canvas.setExtent(layer.extent())
            canvas.refresh()
            return
        self.qgis_tools_details.setText(_html_lines((_tool_instruction_text(), "", "Zoom: select an output layer in the Layers panel, then use Zoom to Layer in QGIS.")))

    def open_output_folder(self) -> None:
        """Open the active run output folder."""
        if self.run_context is None:
            self.next_steps_label.setText("Run Dataset Explorer before opening an output folder.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.run_context.outputs_dir)))

    def _update_next_steps(self, report: RecommendationReport) -> None:
        if report.warnings:
            first = report.warnings[0]
            text = f"Start here: {first.suggested_action}"
        else:
            text = "Start here: build a product plan with the recommended products and settings."
        self.next_steps_label.setText(text + "\n\nUse QGIS review tools after processing before sharing outputs.")


class PlanningPage(MissionPage):
    """Product planning page using the active run context."""

    planningChanged = pyqtSignal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the planning page."""
        super().__init__("Planning", parent)
        self.dataset_report: DatasetExplorerReport | None = None
        self.run_context: RunContext | None = None
        self.latest_plan: ProductPlannerReport | None = None

        dataset = self.add_section("Dataset")
        self.dataset_context_label = _body_label("Run Dataset Explorer to load an active dataset report for planning.")
        dataset.addWidget(self.dataset_context_label)

        output_group, output = _collapsible_section(self.content_layout, "Advanced Output Folder", checked=False)
        self.output_folder_edit = QLineEdit()
        self.output_folder_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        folder_button = QPushButton("Browse")
        folder_button.setMinimumHeight(SECONDARY_BUTTON_HEIGHT)
        folder_button.clicked.connect(self.browse_folder)
        folder_row = QHBoxLayout()
        folder_row.setSpacing(ACTION_ROW_SPACING)
        folder_row.addWidget(self.output_folder_edit, 1)
        folder_row.addWidget(folder_button, 0)
        output.addWidget(_body_label("Mission Control normally uses the active run folder. Override it only when you need a different output location."))
        output.addLayout(folder_row)
        _wire_collapsible_group(output_group)

        products = self.add_section("Product Selection")
        self.product_checks: dict[ProductType, QCheckBox] = {}
        product_grid = QGridLayout()
        product_grid.setHorizontalSpacing(SPACING_XL)
        product_grid.setVerticalSpacing(SPACING_SM)
        for index, (product, label) in enumerate(PRODUCT_LABELS.items()):
            check = QCheckBox(label)
            check.setMinimumHeight(SECONDARY_BUTTON_HEIGHT)
            if product is ProductType.CHM:
                check.setChecked(True)
            self.product_checks[product] = check
            product_grid.addWidget(check, index // 2, index % 2)
        products.addLayout(product_grid)
        product_button_row = QHBoxLayout()
        product_button_row.setSpacing(ACTION_ROW_SPACING)
        select_all = QPushButton("Select All Products")
        select_all.setMinimumHeight(SECONDARY_BUTTON_HEIGHT)
        select_all.clicked.connect(lambda: self._set_all_products(True))
        _apply_button_role(select_all, "neutral")
        clear_all = QPushButton("Clear Products")
        clear_all.setMinimumHeight(SECONDARY_BUTTON_HEIGHT)
        clear_all.clicked.connect(lambda: self._set_all_products(False))
        _apply_button_role(clear_all, "neutral")
        product_button_row.addWidget(select_all)
        product_button_row.addWidget(clear_all)
        product_button_row.addStretch(1)
        products.addLayout(product_button_row)

        shared = self.add_section("Shared Parameters")
        shared_form = QFormLayout()
        shared_form.setLabelAlignment(Qt.AlignLeft)
        shared_form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        shared_form.setHorizontalSpacing(SPACING_LG)
        shared_form.setVerticalSpacing(SECTION_SPACING)
        self.resolution_spin = QDoubleSpinBox()
        self.resolution_spin.setDecimals(3)
        self.resolution_spin.setMinimum(0.01)
        self.resolution_spin.setValue(1.0)
        self.height_bin_spin = QDoubleSpinBox()
        self.height_bin_spin.setDecimals(3)
        self.height_bin_spin.setMinimum(0.0)
        self.height_bin_spin.setSpecialValueText("Not specified")
        self.height_bin_spin.setValue(1.0)
        shared_form.addRow("Grid resolution", self.resolution_spin)
        shared_form.addRow("Height bin size", self.height_bin_spin)
        shared.addLayout(shared_form)

        product_params_group, product_params = _collapsible_section(self.content_layout, "Advanced Product Settings", checked=False)
        product_params.addWidget(_details_label("Expand only when you need to change product-specific filenames, CHM interpolation options, or canopy-cover threshold. Recommended/shared settings above are enough for the default workflow."))
        params_grid = QGridLayout()
        params_grid.setHorizontalSpacing(SPACING_XL)
        params_grid.setVerticalSpacing(SECTION_SPACING)
        chm_box = QGroupBox("CHM")
        chm_layout = QFormLayout(chm_box)
        chm_layout.setVerticalSpacing(SPACING_SM)
        self.chm_interpolation_combo = QComboBox()
        self.chm_interpolation_combo.addItems(("linear", "nearest", "cubic"))
        self.chm_valid_region_check = QCheckBox("Interpolate valid region")
        self.chm_clean_edges_check = QCheckBox("Clean edges")
        self.chm_output_filename_edit = QLineEdit("chm.tif")
        chm_layout.addRow("Interpolation", self.chm_interpolation_combo)
        chm_layout.addRow("Valid region", self.chm_valid_region_check)
        chm_layout.addRow("Edges", self.chm_clean_edges_check)
        chm_layout.addRow("Output filename", self.chm_output_filename_edit)

        canopy_box = QGroupBox("Canopy Cover")
        canopy_layout = QFormLayout(canopy_box)
        canopy_layout.setVerticalSpacing(SPACING_SM)
        self.canopy_cover_threshold_spin = QDoubleSpinBox()
        self.canopy_cover_threshold_spin.setDecimals(3)
        self.canopy_cover_threshold_spin.setMinimum(0.0)
        self.canopy_cover_threshold_spin.setValue(2.0)
        self.canopy_cover_output_filename_edit = QLineEdit("canopy_cover.tif")
        canopy_layout.addRow("Height threshold", self.canopy_cover_threshold_spin)
        canopy_layout.addRow("Output filename", self.canopy_cover_output_filename_edit)

        raster_box = QGroupBox("PAD / PAI / FHD / Rumple")
        raster_layout = QFormLayout(raster_box)
        raster_layout.setVerticalSpacing(SPACING_SM)
        self.pad_output_filename_edit = QLineEdit("pad.tif")
        self.pai_output_filename_edit = QLineEdit("pai.tif")
        self.fhd_output_filename_edit = QLineEdit("fhd.tif")
        self.rumple_output_filename_edit = QLineEdit("rumple_summary.csv")
        raster_layout.addRow("PAD output", self.pad_output_filename_edit)
        raster_layout.addRow("PAI output", self.pai_output_filename_edit)
        raster_layout.addRow("FHD output", self.fhd_output_filename_edit)
        raster_layout.addRow("Rumple output", self.rumple_output_filename_edit)

        for box in (chm_box, canopy_box, raster_box):
            box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        params_grid.addWidget(chm_box, 0, 0)
        params_grid.addWidget(canopy_box, 0, 1)
        params_grid.addWidget(raster_box, 1, 0, 1, 2)
        params_grid.setColumnStretch(0, 1)
        params_grid.setColumnStretch(1, 1)
        product_params.addLayout(params_grid)
        _wire_collapsible_group(product_params_group)

        summary = self.add_section("Plan Summary")
        plan_actions = QHBoxLayout()
        plan_actions.setSpacing(ACTION_ROW_SPACING)
        self.build_plan_button = QPushButton("Build Plan")
        self.build_plan_button.setMinimumHeight(PRIMARY_BUTTON_HEIGHT)
        self.build_plan_button.clicked.connect(self.build_plan)
        _apply_button_role(self.build_plan_button, "primary")
        self.build_plan_button.setEnabled(False)
        self.refresh_plan_button = QPushButton("Refresh Plan State")
        self.refresh_plan_button.clicked.connect(self.refresh_plan_state)
        _apply_button_role(self.refresh_plan_button, "neutral")
        plan_actions.addWidget(self.build_plan_button)
        plan_actions.addWidget(self.refresh_plan_button)
        plan_actions.addStretch(1)
        summary.addLayout(plan_actions)
        self.plan_text = QTextEdit()
        self.plan_text.setReadOnly(True)
        self.plan_text.setMinimumHeight(COMPACT_LIST_HEIGHT)
        self.plan_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plan_text.setPlainText(empty_state_message("planning"))
        summary.addWidget(self.plan_text)

    def _set_all_products(self, checked: bool) -> None:
        """Set all product checkboxes to a common state."""
        for check in self.product_checks.values():
            check.setChecked(checked)

    def refresh_plan_state(self) -> None:
        """Recover Planning page controls from the current dataset/run state."""
        ready = self.dataset_report is not None
        self.build_plan_button.setEnabled(ready)
        if ready:
            self.plan_text.setPlainText("Plan state refreshed. Choose products and build or rebuild the plan.")
        else:
            self.plan_text.setPlainText("Plan state refreshed. Run Dataset Explorer before building a product plan.")

    def set_dataset_report(self, report: DatasetExplorerReport, context: RunContext | None = None) -> None:
        """Store latest Dataset Explorer report and run context for planning."""
        self.dataset_report = report
        self.run_context = context
        dataset_name = context.lidar_path.name if context is not None else "loaded dataset"
        run_folder = str(context.run_folder) if context is not None else "not assigned"
        self.dataset_context_label.setText(
            f"Active dataset: {dataset_name}\nRun folder: {run_folder}\nChoose products and parameters, then build the Product Planner report."
        )
        if context is not None:
            self.output_folder_edit.setText(str(context.outputs_dir))
        self.plan_text.setPlainText("Dataset loaded. Choose products and build a plan.")
        self.build_plan_button.setEnabled(True)

    def reset_for_new_dataset(self, dataset_name: str = "selected dataset") -> None:
        """Clear plan state when the selected dataset changes."""
        self.dataset_report = None
        self.run_context = None
        self.latest_plan = None
        self.dataset_context_label.setText(f"Dataset selected: {dataset_name}\nAnalyze the dataset before choosing products.")
        self.output_folder_edit.clear()
        self.plan_text.setPlainText("Analyze the selected dataset before building a product plan.")
        self.build_plan_button.setEnabled(False)

    def apply_recommendation_report(self, report: RecommendationReport) -> None:
        """Adopt practical Advisor parameter recommendations into planning controls."""
        adopted: list[str] = []
        for parameter in report.recommended_parameters:
            if parameter.product == "chm" and parameter.name == "grid_resolution":
                try:
                    value = float(parameter.value)
                except (TypeError, ValueError):
                    continue
                if value > 0:
                    self.resolution_spin.setValue(value)
                    adopted.append(f"CHM grid resolution set to {value:g} {parameter.unit}")
        if adopted:
            current = self.plan_text.toPlainText().strip()
            note = "Advisor recommendations adopted:\n" + "\n".join(f"- {item}" for item in adopted)
            self.plan_text.setPlainText(f"{current}\n\n{note}" if current else note)

    def browse_folder(self) -> None:
        """Choose a future output folder."""
        path = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if path:
            self.output_folder_edit.setText(path)

    def build_plan(self) -> None:
        """Build an in-memory product plan without writing outputs."""
        if self.dataset_report is None:
            self.plan_text.setPlainText("Run Dataset Explorer before building a product plan.")
            return
        self.build_plan_button.setEnabled(False)
        self.plan_text.setPlainText("Preparing product plan...")
        QApplication.processEvents()
        selected = tuple(product for product, check in self.product_checks.items() if check.isChecked())
        output_folder = self.run_context.outputs_dir if self.run_context is not None else Path(self.output_folder_edit.text().strip() or "planned_outputs")
        height_bin_size = self.height_bin_spin.value() if self.height_bin_spin.value() > 0 else None
        request = ProductPlannerRequest(
            explorer_report_path=self.run_context.dataset_report_json if self.run_context is not None else Path("mission_control_dataset_report.json"),
            requested_products=selected,
            output_folder=output_folder,
            grid_resolution=self.resolution_spin.value(),
            height_bin_size=height_bin_size,
            chm_interpolation=self.chm_interpolation_combo.currentText(),
            chm_interpolate_valid_region=self.chm_valid_region_check.isChecked(),
            chm_clean_edges=self.chm_clean_edges_check.isChecked(),
            chm_output_filename=self.chm_output_filename_edit.text().strip() or "chm.tif",
            pad_output_filename=self.pad_output_filename_edit.text().strip() or "pad.tif",
            pai_output_filename=self.pai_output_filename_edit.text().strip() or "pai.tif",
            fhd_output_filename=self.fhd_output_filename_edit.text().strip() or "fhd.tif",
            rumple_output_filename=self.rumple_output_filename_edit.text().strip() or "rumple_summary.csv",
            canopy_cover_height_threshold=self.canopy_cover_threshold_spin.value(),
            canopy_cover_output_filename=self.canopy_cover_output_filename_edit.text().strip() or "canopy_cover.tif",
            title="Mission Control Product Plan",
        )
        try:
            plan = build_product_plan(report_to_dict(self.dataset_report), request)
        except ProductPlanError as exc:
            self.plan_text.setPlainText(f"Product plan failed: {exc}")
            self.build_plan_button.setEnabled(True)
            self.planningChanged.emit("Needs review", None)
            return
        try:
            if self.run_context is not None:
                write_plan_json(plan, self.run_context.product_plan_json)
                write_plan_csv(plan, self.run_context.product_plan_csv)
                write_plan_html(plan, self.run_context.product_plan_html)
        except OSError as exc:
            self.plan_text.setPlainText(f"Product plan reports could not be written: {exc}")
            self.build_plan_button.setEnabled(True)
            self.planningChanged.emit("Needs review", None)
            return
        self.latest_plan = plan
        ready = sum(1 for product in plan.products if product.plan_status == "Ready")
        review = sum(1 for product in plan.products if product.plan_status == "Needs review")
        blocked = sum(1 for product in plan.products if product.plan_status == "Blocked")
        plan_path = f"Product Plan: {self.run_context.product_plan_html}" if self.run_context is not None else "Product Plan: in memory"
        lines = [
            f"Ready: {ready}",
            f"Needs review: {review}",
            f"Blocked: {blocked}",
            f"Estimated cells: {plan.estimated_cells if plan.estimated_cells is not None else 'Unknown'}",
            f"CHM interpolation: {plan.chm_interpolation}",
            f"CHM valid region interpolation: {plan.chm_interpolate_valid_region}",
            f"CHM clean edges: {plan.chm_clean_edges}",
            f"CHM output: {plan.output_folder / plan.chm_output_filename}",
            f"PAD output: {plan.output_folder / plan.pad_output_filename}",
            f"PAI output: {plan.output_folder / plan.pai_output_filename}",
            f"FHD output: {plan.output_folder / plan.fhd_output_filename}",
            f"Rumple output: {plan.output_folder / plan.rumple_output_filename}",
            f"Canopy cover threshold: {plan.canopy_cover_height_threshold}",
            f"Canopy cover output: {plan.output_folder / plan.canopy_cover_output_filename}",
            plan_path,
            "",
        ]
        lines.extend(f"- {item.label}: {item.plan_status}" for item in plan.products)
        self.plan_text.setPlainText("\n".join(lines))
        self.build_plan_button.setEnabled(True)
        self.planningChanged.emit("Ready" if blocked == 0 else "Needs review", plan)


class ProcessingPage(MissionPage):
    """Pipeline execution page using the active product plan."""

    jobUpdated = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the processing page."""
        super().__init__("Processing", parent)
        self.job_manager = JobManager(event_sink=self._on_job_update)
        self.current_job_id: str | None = None
        self.run_context: RunContext | None = None
        self.current_footprint: ProcessingFootprint | None = None

        overview = self.add_section("Ready To Run")
        self.selected_products_label = _body_label("Selected products: build a Product Plan first.")
        self.current_output_label = _body_label("Outputs: choose a dataset and output folder, then build a Product Plan.")
        self.footprint_label = _body_label("Processing footprint: build a Product Plan to see expected outputs, raster size, bands, and storage.")
        self.already_generated_label = _body_label("Already generated: None")
        self.status_label = QLabel()
        _set_status_badge(self.status_label, "NOT CONFIGURED", "Status: Not set up - build a Product Plan first.")
        overview.addWidget(self.selected_products_label)
        overview.addWidget(self.already_generated_label)
        overview.addWidget(self.current_output_label)
        overview.addWidget(self.footprint_label)
        overview.addWidget(self.status_label)

        self.execution_backend_label = _body_label("Execution backend: PBM when READY; QGIS Python fallback only when PBM is unavailable.")
        overview.addWidget(self.execution_backend_label)

        self.job_title_edit = QLineEdit("Mission Control Product Job")
        self.job_title_edit.setPlaceholderText("Optional run label")
        overview.addWidget(self.job_title_edit)

        button_row = QHBoxLayout()
        button_row.setSpacing(ACTION_ROW_SPACING)
        self.start_button = QPushButton(primary_action_label("processing"))
        self.start_button.setMinimumHeight(PRIMARY_BUTTON_HEIGHT)
        self.start_button.clicked.connect(self.start_job)
        _apply_button_role(self.start_button, "primary")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setMinimumHeight(PRIMARY_BUTTON_HEIGHT)
        self.cancel_button.clicked.connect(self.cancel_current_job)
        _apply_button_role(self.cancel_button, "danger")
        self.cancel_button.setEnabled(False)
        self.refresh_processing_button = QPushButton("Refresh Processing State")
        self.refresh_processing_button.clicked.connect(self.refresh_processing_state)
        _apply_button_role(self.refresh_processing_button, "neutral")
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.refresh_processing_button)
        button_row.addStretch(1)
        overview.addLayout(button_row)

        progress = self.add_section("Current Progress")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress.addWidget(self.progress_bar)
        self.processing_stage_label = _body_label("Stage: Not started")
        progress.addWidget(self.processing_stage_label)
        progress.addWidget(_body_label("Keep QGIS open until processing completes."))

        technical_group, technical = _collapsible_section(self.content_layout, "Technical Details", checked=False)
        technical.addWidget(_details_label("Run files, plan paths, processing stages, and logs are shown here for troubleshooting."))
        self.current_plan_label = QLabel("Product plan file: none")
        self.current_plan_label.setWordWrap(True)
        technical.addWidget(self.current_plan_label)
        plan_row = QHBoxLayout()
        self.product_plan_edit = QLineEdit()
        self.product_plan_edit.setPlaceholderText("Optional Product Planner JSON override")
        plan_browse = QPushButton("Browse")
        plan_browse.clicked.connect(self.browse_product_plan)
        plan_row.addWidget(self.product_plan_edit, 1)
        plan_row.addWidget(plan_browse, 0)
        technical.addLayout(plan_row)
        output_row = QHBoxLayout()
        self.job_output_folder_edit = QLineEdit()
        self.job_output_folder_edit.setPlaceholderText("Optional job log folder override")
        output_browse = QPushButton("Browse")
        output_browse.clicked.connect(self.browse_output_folder)
        output_row.addWidget(self.job_output_folder_edit, 1)
        output_row.addWidget(output_browse, 0)
        technical.addLayout(output_row)
        self.pipeline_list = QListWidget()
        self.pipeline_list.setMinimumHeight(TECHNICAL_DETAIL_HEIGHT)
        technical.addWidget(self.pipeline_list)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(TECHNICAL_DETAIL_HEIGHT)
        technical.addWidget(self.log_text)
        _wire_collapsible_group(technical_group)

    def refresh_processing_state(self) -> None:
        """Recover Processing controls from the current run context and job state."""
        self._refresh_plan_summary()
        job = self.job_manager.get_job(self.current_job_id) if self.current_job_id else None
        running = job is not None and job.status in {JobStatus.PENDING, JobStatus.VALIDATING, JobStatus.RUNNING, JobStatus.CANCELLING}
        self.start_button.setEnabled(not running)
        self.cancel_button.setEnabled(bool(running))
        if not running and self.processing_stage_label.text().strip() == "Stage: Not started":
            self.processing_stage_label.setText("Stage: Ready when a Product Plan is available")
        self.log_text.setPlainText((self.log_text.toPlainText().strip() + "\n" if self.log_text.toPlainText().strip() else "") + "Processing state refreshed.")

    def set_run_context(self, context: RunContext | None) -> None:
        """Use the active Mission Control run context."""
        self.run_context = context
        if context is None:
            self.current_plan_label.setText("Product plan file: none")
            self.selected_products_label.setText("Selected products: build a Product Plan first.")
            self.current_output_label.setText("Outputs: choose a dataset and output folder, then build a Product Plan.")
            self.footprint_label.setText("Processing footprint: build a Product Plan to see expected outputs, raster size, bands, and storage.")
            self.processing_stage_label.setText("Stage: Not started")
            return
        self.product_plan_edit.setText(str(context.product_plan_json))
        self.job_output_folder_edit.setText(str(context.logs_dir))
        self.current_plan_label.setText(f"Product plan file: {context.product_plan_json}")
        self.current_output_label.setText(f"Outputs: {context.outputs_dir}")
        self._refresh_plan_summary()

    def _refresh_plan_summary(self) -> None:
        """Refresh selected products and footprint summary from the active Product Plan."""
        plan_path = Path(self.product_plan_edit.text().strip()) if self.product_plan_edit.text().strip() else None
        if plan_path is None or not plan_path.exists():
            self.selected_products_label.setText("Selected products: build a Product Plan first.")
            self.footprint_label.setText("Processing footprint: build a Product Plan to see expected outputs, raster size, bands, and storage.")
            self.processing_stage_label.setText("Stage: Not started")
            return
        try:
            payload = json.loads(plan_path.read_text(encoding="utf-8"))
            products = [item for item in payload.get("products", []) if isinstance(item, dict) and item.get("requested", True)]
            labels = [str(item.get("label") or item.get("product")) for item in products]
            footprint = footprint_from_plan_file(plan_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            self.selected_products_label.setText("Selected products: Product Plan could not be read.")
            self.footprint_label.setText(f"Processing footprint: unavailable ({exc})")
            return
        self.current_footprint = footprint
        self.selected_products_label.setText("Selected products: " + (", ".join(labels) if labels else "none"))
        self.footprint_label.setText(_processing_footprint_text(footprint))

    def set_project_summary(self, summary: ProjectSummary) -> None:
        """Display generated-product awareness before users rerun processing."""
        if summary.generated_products:
            labels = ", ".join(item.label for item in summary.generated_products)
            self.already_generated_label.setText(f"Already generated: {labels}")
        else:
            self.already_generated_label.setText("Already generated: None")

    def browse_product_plan(self) -> None:
        """Choose a Product Planner JSON report for advanced troubleshooting."""
        path, _ = QFileDialog.getOpenFileName(self, "Choose Product Planner JSON", "", "JSON reports (*.json);;All files (*.*)")
        if path:
            self.product_plan_edit.setText(path)
            self._refresh_plan_summary()

    def browse_output_folder(self) -> None:
        """Choose a job summary output folder for advanced troubleshooting."""
        path = QFileDialog.getExistingDirectory(self, "Choose job output folder")
        if path:
            self.job_output_folder_edit.setText(path)
            self.current_output_label.setText(f"Outputs: {path}")

    def start_job(self) -> None:
        """Start a processing job from the active Product Planner report."""
        plan_path = self.product_plan_edit.text().strip()
        output_folder = self.job_output_folder_edit.text().strip()
        summary_path = self.run_context.job_summary_json if self.run_context is not None else None
        if not plan_path:
            _set_status_badge(self.status_label, "WARNING", "Status: Needs review - build a product plan before starting.")
            self.log_text.setPlainText("Build a product plan before starting a processing job.")
            return
        if not Path(plan_path).exists():
            _set_status_badge(self.status_label, "WARNING", "Status: Needs review - build a product plan before starting.")
            self.log_text.setPlainText("Build a product plan before starting a processing job.")
            return
        if not output_folder:
            _set_status_badge(self.status_label, "WARNING", "Status: Needs review - choose an output folder before starting.")
            self.log_text.setPlainText("Choose an output folder for the job summary JSON.")
            return
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.processing_stage_label.setText("Stage: Preparing")
        self.progress_bar.setValue(5)
        self.log_text.clear()
        execution_backend = self.job_manager.execution_backend().replace("_", " ")
        self.execution_backend_label.setText(f"Execution backend: {execution_backend}")
        self.log_text.setPlainText(f"Execution backend: {execution_backend}.\n")
        try:
            job = self.job_manager.run_pipeline(
                Path(plan_path),
                Path(output_folder),
                self.job_title_edit.text().strip() or "Mission Control Product Job",
                summary_path=summary_path,
            )
        except JobExecutionError as exc:
            _set_status_badge(self.status_label, "FAILED", f"Status: Failed - processing job could not start: {exc}")
            self.log_text.setPlainText(f"Processing job could not start: {exc}")
            self.processing_stage_label.setText("Stage: Failed")
            self.start_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            return
        self.current_job_id = job.job_id
        self._on_job_update(job)
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(job.status in {JobStatus.PENDING, JobStatus.VALIDATING, JobStatus.RUNNING, JobStatus.CANCELLING})

    def cancel_current_job(self) -> None:
        """Request cancellation for the current job when it is still active."""
        if self.current_job_id is None:
            return
        job = self.job_manager.request_cancel(self.current_job_id)
        if job is not None:
            self._on_job_update(job)

    def _on_job_update(self, job: JobRecord) -> None:
        """Bridge core job progress into Qt widgets."""
        self.current_job_id = job.job_id
        _set_status_badge(self.status_label, job.status.value, f"Status: {status_display_word(job.status.value)} - {job.status.value}")
        self.progress_bar.setValue(int(job.progress.percent))
        self.processing_stage_label.setText(f"Stage: {_processing_lifecycle_stage(job)}")
        self.execution_backend_label.setText(f"Execution backend: {self.job_manager.execution_backend().replace('_', ' ')}")
        self.log_text.setPlainText("\n".join(f"{entry.level}: {entry.message}" for entry in job.logs))
        self.cancel_button.setEnabled(job.status in {JobStatus.PENDING, JobStatus.VALIDATING, JobStatus.RUNNING, JobStatus.CANCELLING})
        self._set_pipeline_results(job)
        self.jobUpdated.emit(job)

    def _set_pipeline_results(self, job: JobRecord) -> None:
        """Display pipeline stages for the current job."""
        self.pipeline_list.clear()
        for pipeline in job.pipeline_results:
            self.pipeline_list.addItem(f"{pipeline.label}")
            for step in pipeline.steps:
                self.pipeline_list.addItem(f"  {_pipeline_status_icon(step.status.value)} {step.label}: {step.message}")


class _BatchExecutionWorker(QObject):
    """Qt worker that runs BatchExecutor away from the UI thread."""

    itemReady = pyqtSignal(object)
    jobReady = pyqtSignal(object)
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, request: BatchRequest, control_callback: Callable[[], str | None]) -> None:
        """Store immutable batch request and cancellation callback."""
        super().__init__()
        self.request = request
        self.control_callback = control_callback

    def run(self) -> None:
        """Execute the batch and emit a final result or error message."""
        try:
            result = BatchExecutor(adapter_factory=PyForestScanAdapter).run(
                self.request,
                item_callback=self.itemReady.emit,
                job_callback=self.jobReady.emit,
                control_callback=self.control_callback,
            )
        except BatchExecutionError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - worker must report unexpected failures to UI.
            self.failed.emit(f"Unexpected batch failure: {exc}")
            return
        self.completed.emit(result)


class _BackendInstallWorker(QObject):
    """Qt worker that runs PBM installation away from the main QGIS UI thread."""

    progressUpdated = pyqtSignal(object)
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, service: BackendService) -> None:
        """Store the backend service used for the install transaction."""
        super().__init__()
        self.service = service

    def run(self) -> None:
        """Run backend installation and emit progress/result signals."""
        try:
            result = self.service.install_backend(progress_callback=self.progressUpdated.emit)
        except Exception as exc:  # noqa: BLE001 - worker must never crash QGIS UI.
            self.failed.emit(f"Unexpected backend installation failure: {exc}")
            return
        self.completed.emit(result)


class BatchPage(MissionPage):
    """Sequential folder-to-products batch workflow."""

    jobUpdated = pyqtSignal(object)
    batchCompleted = pyqtSignal(object)

    def __init__(self, adapter: PyForestScanAdapter, parent: QWidget | None = None) -> None:
        """Create the Batch page."""
        super().__init__("Batch", parent)
        self.adapter = adapter
        self.discovered_paths: list[Path] = []
        self.latest_result: object | None = None
        self.batch_items: list[object] = []
        self.cancel_requested = False
        self.pause_requested = False
        self.failed_paths: list[Path] = []
        self.active_workers = 0
        self.batch_thread: QThread | None = None
        self.batch_worker: _BatchExecutionWorker | None = None
        self.preflight_report: BatchPreflightReport | None = None

        source = self.add_section("1. Discover Files")
        folder_row = QHBoxLayout()
        self.input_folder_edit = QLineEdit()
        self.input_folder_edit.setPlaceholderText("Choose a folder containing LAS, LAZ, COPC, or EPT datasets")
        input_browse = QPushButton("Browse")
        input_browse.clicked.connect(self.browse_input_folder)
        folder_row.addWidget(self.input_folder_edit, 1)
        folder_row.addWidget(input_browse, 0)
        source.addLayout(folder_row)
        self.recursive_check = QCheckBox("Search subfolders")
        source.addWidget(self.recursive_check)
        discover_row = QHBoxLayout()
        self.discover_button = QPushButton("Discover Files")
        self.discover_button.clicked.connect(self.discover_files)
        _apply_button_role(self.discover_button, "primary")
        select_all = QPushButton("Select All")
        select_all.clicked.connect(lambda: self._set_all_files(True))
        _apply_button_role(select_all, "neutral")
        clear_all = QPushButton("Clear")
        clear_all.clicked.connect(lambda: self._set_all_files(False))
        _apply_button_role(clear_all, "neutral")
        discover_row.addWidget(self.discover_button)
        discover_row.addWidget(select_all)
        discover_row.addWidget(clear_all)
        discover_row.addStretch(1)
        source.addLayout(discover_row)
        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(COMPACT_LIST_HEIGHT)
        source.addWidget(self.file_list)

        output = self.add_section("Output")
        output_row = QHBoxLayout()
        self.output_folder_edit = QLineEdit()
        self.output_folder_edit.setPlaceholderText("Choose one output folder for the batch")
        output_browse = QPushButton("Browse")
        output_browse.clicked.connect(self.browse_output_folder)
        output_row.addWidget(self.output_folder_edit, 1)
        output_row.addWidget(output_browse, 0)
        output.addLayout(output_row)
        output.addWidget(_body_label("Mission Control creates one batch folder, then one organized run folder per selected dataset."))
        self.open_batch_folder_button = QPushButton("Open Batch Output Folder")
        self.open_batch_folder_button.setEnabled(False)
        self.open_batch_folder_button.clicked.connect(self.open_batch_output_folder)
        output.addWidget(self.open_batch_folder_button)

        products = self.add_section("Products and Shared Settings")
        self.product_checks: dict[ProductType, QCheckBox] = {}
        product_grid = QGridLayout()
        product_grid.setHorizontalSpacing(SPACING_XL)
        product_grid.setVerticalSpacing(SPACING_SM)
        for index, (product, label) in enumerate(PRODUCT_LABELS.items()):
            check = QCheckBox(label)
            check.setMinimumHeight(SECONDARY_BUTTON_HEIGHT)
            if product is ProductType.CHM:
                check.setChecked(True)
            self.product_checks[product] = check
            product_grid.addWidget(check, index // 2, index % 2)
        products.addLayout(product_grid)
        settings_form = QFormLayout()
        settings_form.setVerticalSpacing(SECTION_SPACING)
        self.resolution_spin = QDoubleSpinBox()
        self.resolution_spin.setDecimals(3)
        self.resolution_spin.setMinimum(0.01)
        self.resolution_spin.setValue(1.0)
        self.height_bin_spin = QDoubleSpinBox()
        self.height_bin_spin.setDecimals(3)
        self.height_bin_spin.setMinimum(0.0)
        self.height_bin_spin.setSpecialValueText("Not specified")
        self.height_bin_spin.setValue(1.0)
        self.canopy_threshold_spin = QDoubleSpinBox()
        self.canopy_threshold_spin.setDecimals(3)
        self.canopy_threshold_spin.setMinimum(0.0)
        self.canopy_threshold_spin.setValue(2.0)
        self.chm_interpolation_combo = QComboBox()
        self.chm_interpolation_combo.addItems(("linear", "nearest", "cubic"))
        settings_form.addRow("Grid resolution", self.resolution_spin)
        settings_form.addRow("Height bin size", self.height_bin_spin)
        settings_form.addRow("Canopy cover threshold", self.canopy_threshold_spin)
        settings_form.addRow("CHM interpolation", self.chm_interpolation_combo)
        products.addLayout(settings_form)
        advanced_batch_group, advanced_batch = _collapsible_section(self.content_layout, "Advanced Batch Options", checked=False)
        advanced_form = QFormLayout()
        advanced_form.setVerticalSpacing(SECTION_SPACING)
        self.execution_mode_combo = QComboBox()
        self.execution_mode_combo.addItem("Sequential", SEQUENTIAL_MODE)
        self.execution_mode_combo.addItem("Parallel safe mode", PARALLEL_SAFE_MODE)
        self.execution_mode_combo.currentIndexChanged.connect(lambda _index: self._refresh_footprint_label())
        self.max_workers_spin = QSpinBox()
        self.max_workers_spin.setMinimum(1)
        self.max_workers_spin.setMaximum(6)
        self.max_workers_spin.setValue(2)
        self.max_workers_spin.valueChanged.connect(lambda _value: self._refresh_footprint_label())
        advanced_form.addRow("Execution mode", self.execution_mode_combo)
        advanced_form.addRow("Max workers", self.max_workers_spin)
        advanced_batch.addLayout(advanced_form)
        mode_help = _details_label(
            "Sequential is safest. Parallel Safe is available with confirmation and guardrails. "
            "External Worker is disabled."
        )
        advanced_batch.addWidget(mode_help)
        self.stop_on_error_check = QCheckBox("Stop batch when a file fails")
        self.load_outputs_check = QCheckBox("Load generated outputs into QGIS")
        self.load_outputs_check.setToolTip("Leave off for large batches; load selected results from the Results page when ready.")
        self.confirm_parallel_check = QCheckBox("Allow parallel safe mode for this workload after reviewing warnings")
        self.confirm_parallel_check.toggled.connect(lambda _checked: self._refresh_footprint_label())
        self.skip_completed_check = QCheckBox("Skip already-completed files on resume")
        self.skip_completed_check.setChecked(True)
        self.retry_failed_only_check = QCheckBox("Retry failed files only")
        self.overwrite_existing_check = QCheckBox("Overwrite existing outputs")
        for check in (
            self.stop_on_error_check,
            self.load_outputs_check,
            self.confirm_parallel_check,
            self.skip_completed_check,
            self.retry_failed_only_check,
            self.overwrite_existing_check,
        ):
            advanced_batch.addWidget(check)
        _wire_collapsible_group(advanced_batch_group)
        for check in self.product_checks.values():
            check.toggled.connect(lambda _checked: self._refresh_footprint_label())
        self.resolution_spin.valueChanged.connect(lambda _value: self._refresh_footprint_label())
        self.height_bin_spin.valueChanged.connect(lambda _value: self._refresh_footprint_label())
        self.file_list.itemChanged.connect(lambda _item: self._refresh_footprint_label())

        footprint_group, footprint = _collapsible_section(self.content_layout, "Batch Footprint Estimate", checked=False)
        self.footprint_label = _body_label("Select files and products to review the batch footprint. Raster dimensions are estimated per file after Dataset Explorer runs.")
        footprint.addWidget(self.footprint_label)
        _wire_collapsible_group(footprint_group)

        preflight = self.add_section("2. Preflight")
        self.preflight_button = QPushButton("Run Preflight Check")
        self.preflight_button.setMinimumHeight(PRIMARY_BUTTON_HEIGHT)
        self.preflight_button.clicked.connect(self.run_preflight)
        _apply_button_role(self.preflight_button, "primary")
        preflight.addWidget(self.preflight_button)
        self.acknowledge_warnings_check = QCheckBox("I reviewed the warnings and want to run anyway")
        self.acknowledge_warnings_check.toggled.connect(lambda _checked: self._update_run_button_enabled())
        self.acknowledge_warnings_check.setEnabled(False)
        preflight.addWidget(self.acknowledge_warnings_check)
        self.preflight_text = QTextEdit()
        self.preflight_text.setReadOnly(True)
        self.preflight_text.setMinimumHeight(TECHNICAL_DETAIL_HEIGHT)
        self.preflight_text.setPlainText("Run preflight before starting a batch.")
        preflight.addWidget(self.preflight_text)

        run_section = self.add_section("3. Run Batch / Review Results")
        self.run_button = QPushButton(primary_action_label("batch"))
        self.run_button.setMinimumHeight(PRIMARY_BUTTON_HEIGHT)
        self.run_button.clicked.connect(self.run_batch)
        _apply_button_role(self.run_button, "primary")
        self.run_button.setEnabled(False)
        button_row = QHBoxLayout()
        button_row.addWidget(self.run_button)
        self.resume_button = QPushButton("Resume Batch")
        self.resume_button.setEnabled(False)
        self.resume_button.clicked.connect(self.run_batch)
        _apply_button_role(self.resume_button, "secondary")
        button_row.addWidget(self.resume_button)
        self.pause_button = QPushButton("Pause After Current File")
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.toggle_pause)
        _apply_button_role(self.pause_button, "secondary")
        self.cancel_button = QPushButton("Cancel Remaining")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_remaining)
        _apply_button_role(self.cancel_button, "danger")
        self.retry_failed_button = QPushButton("Retry Failed Files")
        self.retry_failed_button.setEnabled(False)
        self.retry_failed_button.clicked.connect(self.retry_failed_files)
        _apply_button_role(self.retry_failed_button, "secondary")
        button_row.addWidget(self.pause_button)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.retry_failed_button)
        button_row.addStretch(1)
        run_section.addLayout(button_row)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        run_section.addWidget(self.progress_bar)
        self.status_label = QLabel()
        _set_status_badge(self.status_label, "NOT CONFIGURED", "Status: Not set up - discover files and run preflight.")
        run_section.addWidget(self.status_label)
        self.worker_status_label = _body_label("Active workers: 0")
        run_section.addWidget(self.worker_status_label)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Show"))
        self.result_filter_combo = QComboBox()
        self.result_filter_combo.addItems(("All", "Failed", "Completed", "Skipped"))
        self.result_filter_combo.currentTextChanged.connect(lambda _value: self._refresh_batch_results())
        filter_row.addWidget(self.result_filter_combo)
        filter_row.addStretch(1)
        run_section.addLayout(filter_row)
        self.summary_label = _body_label("4. Review Results after the batch completes.")
        run_section.addWidget(self.summary_label)
        self.batch_results = QListWidget()
        self.batch_results.setMinimumHeight(COMPACT_LIST_HEIGHT)
        run_section.addWidget(self.batch_results)

    def set_default_output_folder(self, folder: Path | None) -> None:
        """Use configured default output folder when empty."""
        if folder is not None and not self.output_folder_edit.text().strip():
            self.output_folder_edit.setText(str(folder))

    def browse_input_folder(self) -> None:
        """Choose the folder to scan for lidar datasets."""
        path = QFileDialog.getExistingDirectory(self, "Choose input folder")
        if path:
            self.input_folder_edit.setText(path)

    def browse_output_folder(self) -> None:
        """Choose the batch output root folder."""
        path = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if path:
            self.output_folder_edit.setText(path)

    def discover_files(self) -> None:
        """Discover supported lidar datasets for batch selection."""
        folder = self.input_folder_edit.text().strip()
        if not folder:
            _set_status_badge(self.status_label, "WARNING", "Status: Needs review - choose an input folder before discovery.")
            return
        self.discover_button.setEnabled(False)
        _set_status_badge(self.status_label, "RUNNING", "Status: Running - discovering files.")
        QApplication.processEvents()
        try:
            datasets = discover_lidar_files(folder, self.recursive_check.isChecked())
        except ValueError as exc:
            _set_status_badge(self.status_label, "FAILED", f"Status: Failed - discovery failed: {exc}")
            self.discover_button.setEnabled(True)
            return
        finally:
            self.discover_button.setEnabled(True)
        self.discovered_paths = [item.path for item in datasets]
        self.file_list.clear()
        for item in datasets:
            row = QListWidgetItem(f"{item.path.name}\nStatus: {item.status}; bounds: {item.bounds_summary}\n{item.path}")
            row.setFlags(row.flags() | Qt.ItemIsUserCheckable)
            row.setCheckState(Qt.Checked if item.selected else Qt.Unchecked)
            row.setSizeHint(QSize(0, 72))
            self.file_list.addItem(row)
        _set_status_badge(self.status_label, "READY", f"Status: Ready - discovered {len(datasets)} supported dataset(s).")
        self._refresh_footprint_label()

    def run_preflight(self) -> None:
        """Run batch preflight and update readiness display."""
        self.preflight_button.setEnabled(False)
        self.preflight_text.setPlainText("Preparing preflight check...")
        QApplication.processEvents()
        try:
            request = self._build_batch_request()
        except BatchExecutionError as exc:
            self.preflight_text.setPlainText(f"BLOCKER: {exc}")
            self.preflight_report = None
            self._update_run_button_enabled()
            self.preflight_button.setEnabled(True)
            return
        try:
            report = run_batch_preflight(request, adapter=self.adapter)
        finally:
            self.preflight_button.setEnabled(True)
        self.preflight_report = report
        self.preflight_text.setPlainText(_format_preflight_report(report))
        self.acknowledge_warnings_check.setEnabled(report.has_warnings and not report.blockers)
        if not report.has_warnings:
            self.acknowledge_warnings_check.setChecked(False)
        self._update_run_button_enabled()

    def run_batch(self) -> None:
        """Run selected datasets through preflight-approved batch execution."""
        if self.preflight_report is None:
            _set_status_badge(self.status_label, "WARNING", "Status: Needs review - run preflight before starting the batch.")
            return
        if self.preflight_report.blockers:
            _set_status_badge(self.status_label, "FAILED", "Status: Failed - preflight blockers must be resolved before running.")
            return
        if self.preflight_report.warnings and not self.acknowledge_warnings_check.isChecked():
            _set_status_badge(self.status_label, "WARNING", "Status: Needs review - review and acknowledge preflight warnings before running.")
            return
        try:
            request = self._build_batch_request(self.preflight_report.batch_folder, self.preflight_report.files_to_process)
        except BatchExecutionError as exc:
            _set_status_badge(self.status_label, "FAILED", f"Status: Failed - batch could not start: {exc}")
            return
        selected = list(request.datasets)
        self.batch_items = []
        self.failed_paths = []
        self.cancel_requested = False
        self.pause_requested = False
        self._mark_selected_files_queued()
        self.batch_results.clear()
        self.progress_bar.setValue(0)
        self.run_button.setEnabled(False)
        self.resume_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.cancel_button.setEnabled(True)
        self.retry_failed_button.setEnabled(False)
        _set_status_badge(self.status_label, "RUNNING", f"Status: Running - {len(selected)} dataset(s).")
        self._processed_items = 0
        self._total_items = max(1, len(selected) + len(self.preflight_report.files_to_skip))
        executor = BatchExecutor(adapter_factory=PyForestScanAdapter)
        try:
            guardrail = executor.guardrails(request)
        except BatchExecutionError as exc:
            _set_status_badge(self.status_label, "FAILED", f"Status: Failed - batch could not start: {exc}")
            self._finish_batch_run()
            return
        self.active_workers = guardrail.max_workers if guardrail.is_parallel else 1
        mode_label = guardrail.effective_mode.replace("_", " ")
        self.worker_status_label.setText(f"Active workers: {self.active_workers} ({mode_label})")
        backend_label = PyForestScanAdapter().selected_execution_backend().replace("_", " ")
        _set_status_badge(self.status_label, "RUNNING", f"Status: Running - {len(selected)} dataset(s) in {mode_label}. Execution backend: {backend_label}.")
        self.batch_thread = QThread(self)
        self.batch_worker = _BatchExecutionWorker(request, self._batch_control_state)
        self.batch_worker.moveToThread(self.batch_thread)
        self.batch_thread.started.connect(self.batch_worker.run)
        self.batch_worker.itemReady.connect(self._on_batch_item)
        self.batch_worker.jobReady.connect(self._on_batch_job_update)
        self.batch_worker.completed.connect(self._on_batch_complete)
        self.batch_worker.failed.connect(self._on_batch_failed)
        self.batch_worker.completed.connect(self.batch_thread.quit)
        self.batch_worker.failed.connect(self.batch_thread.quit)
        self.batch_thread.finished.connect(self.batch_worker.deleteLater)
        self.batch_thread.finished.connect(self.batch_thread.deleteLater)
        self.batch_thread.finished.connect(self._clear_batch_thread)
        self.batch_thread.start()

    def _build_batch_request(self, batch_folder: Path | None = None, datasets: tuple[Path, ...] | None = None) -> BatchRequest:
        """Build a typed batch request from current UI state."""
        selected = tuple(datasets) if datasets is not None else tuple(self._selected_paths())
        output_folder = self.output_folder_edit.text().strip()
        if not selected:
            raise BatchExecutionError("Select at least one discovered file.")
        if not output_folder:
            raise BatchExecutionError("Choose an output folder.")
        products = tuple(product for product, check in self.product_checks.items() if check.isChecked())
        if not products:
            raise BatchExecutionError("Select at least one product.")
        settings = BatchProductSettings(
            products=products,
            grid_resolution=self.resolution_spin.value(),
            height_bin_size=self.height_bin_spin.value() if self.height_bin_spin.value() > 0 else None,
            chm_interpolation=self.chm_interpolation_combo.currentText(),
            canopy_cover_height_threshold=self.canopy_threshold_spin.value(),
            stop_on_error=self.stop_on_error_check.isChecked(),
            load_outputs_into_qgis=self.load_outputs_check.isChecked(),
            execution_mode=str(self.execution_mode_combo.currentData()),
            max_workers=self.max_workers_spin.value(),
            confirm_large_parallel=self.confirm_parallel_check.isChecked(),
            skip_completed=self.skip_completed_check.isChecked(),
            retry_failed_only=self.retry_failed_only_check.isChecked(),
            overwrite_existing=self.overwrite_existing_check.isChecked(),
            preflight_acknowledged=self.acknowledge_warnings_check.isChecked(),
        )
        return BatchRequest(
            input_folder=Path(self.input_folder_edit.text().strip()),
            output_folder=Path(output_folder),
            recursive=self.recursive_check.isChecked(),
            datasets=selected,
            settings=settings,
            title="PyForestScan Batch",
            batch_folder=batch_folder,
        )

    def _update_run_button_enabled(self) -> None:
        """Enable Run only after preflight passes or warnings are acknowledged."""
        report = self.preflight_report
        enabled = bool(report and report.files_to_process and not report.blockers and (not report.warnings or self.acknowledge_warnings_check.isChecked()))
        self.run_button.setEnabled(enabled)
        resumable = bool(report and report.manifest_path.exists() and (report.files_completed or report.files_to_retry or report.files_to_skip))
        self.resume_button.setEnabled(enabled and resumable)

    def _on_batch_complete(self, result: object) -> None:
        """Finalize UI state after a worker-thread batch completes."""
        self.latest_result = result
        self.progress_bar.setValue(100 if getattr(result, "items", ()) else 0)
        completion_badge = "READY" if getattr(result, "failure_count", 0) == 0 else "WARNING"
        _set_status_badge(
            self.status_label,
            completion_badge,
            f"Status: {status_display_word(completion_badge)} - batch complete. Completed {getattr(result, 'success_count', 0)}; failed {getattr(result, 'failure_count', 0)}. Summary: {getattr(result, 'summary_html', '')}",
        )
        self._set_batch_summary(result)
        self.open_batch_folder_button.setEnabled(True)
        self.retry_failed_button.setEnabled(bool(self.failed_paths))
        self.batchCompleted.emit(result)
        self._finish_batch_run()

    def _on_batch_failed(self, message: str) -> None:
        """Display an executor-level batch failure."""
        _set_status_badge(self.status_label, "FAILED", f"Status: Failed - batch could not start: {message}")
        self._finish_batch_run()

    def _finish_batch_run(self) -> None:
        """Restore controls after a batch worker exits."""
        self.run_button.setEnabled(True)
        self._update_run_button_enabled()
        self.pause_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.pause_requested = False
        self.pause_button.setText("Pause After Current File")
        self.active_workers = 0
        self.worker_status_label.setText("Active workers: 0")

    def _clear_batch_thread(self) -> None:
        """Clear worker references after Qt has cleaned up the thread."""
        self.batch_thread = None
        self.batch_worker = None

    def _mark_selected_files_queued(self) -> None:
        """Mark selected discovered files as queued before execution starts."""
        products = ", ".join(PRODUCT_LABELS[product] for product, check in self.product_checks.items() if check.isChecked()) or "none"
        for index, path in enumerate(self.discovered_paths):
            item = self.file_list.item(index)
            if item is not None and item.checkState() == Qt.Checked:
                item.setText(f"{path.name}\nStatus: queued; products: {products}\n{path}")

    def _update_file_row(self, path: Path, status: str, bounds: str, message: str) -> None:
        """Update one discovered file row with current batch status."""
        for index, candidate in enumerate(self.discovered_paths):
            if candidate == path:
                item = self.file_list.item(index)
                if item is not None:
                    item.setText(f"{path.name}\nStatus: {status}; bounds: {bounds}\nMessage: {message}\n{path}")
                return

    def _selected_paths(self) -> list[Path]:
        paths: list[Path] = []
        for index, path in enumerate(self.discovered_paths):
            item = self.file_list.item(index)
            if item is not None and item.checkState() == Qt.Checked:
                paths.append(path)
        return paths

    def _set_all_files(self, selected: bool) -> None:
        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            item.setCheckState(Qt.Checked if selected else Qt.Unchecked)
        self._refresh_footprint_label()

    def _refresh_footprint_label(self) -> None:
        selected_count = len(self._selected_paths())
        selected_products = [product for product, check in self.product_checks.items() if check.isChecked()]
        products = [PRODUCT_LABELS[product] for product in selected_products]
        warnings: list[str] = []
        if selected_count >= 10:
            warnings.append("Large batch: many files selected.")
        if selected_count * max(1, len(selected_products)) >= 30:
            warnings.append("Large workload: many file/product combinations selected.")
        if ProductType.PAD in selected_products:
            warnings.append("PAD storage depends on height-bin count and can be large.")
        warning_text = ("\nWarnings: " + " ".join(warnings)) if warnings else ""
        self.footprint_label.setText(
            f"Selected files: {selected_count}\n"
            f"Selected products: {', '.join(products) if products else 'none'}\n"
            f"Shared grid resolution: {self.resolution_spin.value():g}\n"
            "Raster dimensions and storage are estimated per file after inspection; summaries record observed output storage when files exist. "
            "Processing time depends on machine, storage speed, point density, and product selection."
            f"{warning_text}"
        )

    def _on_batch_item(self, item: object) -> None:
        self._processed_items = getattr(self, "_processed_items", 0) + 1
        total = max(1, getattr(self, "_total_items", 1))
        self.progress_bar.setValue(int((self._processed_items / total) * 100))
        dataset_name = Path(getattr(item, "dataset_path")).name
        status = getattr(item, "status")
        message = getattr(item, "message")
        run_folder = getattr(getattr(item, "run_context"), "run_folder")
        bounds = getattr(item, "bounds_summary", "Unavailable")
        self.batch_items.append(item)
        self._update_file_row(Path(getattr(item, "dataset_path")), status, getattr(item, "bounds_summary", "Unavailable"), message)
        if status == "failed":
            self.failed_paths.append(Path(getattr(item, "dataset_path")))
        self._refresh_batch_results()
        _set_status_badge(self.status_label, "RUNNING", f"Status: Running - {self._processed_items}/{total} dataset(s) processed.")
        QApplication.processEvents()

    def _on_batch_job_update(self, job: JobRecord) -> None:
        if self.load_outputs_check.isChecked():
            self.jobUpdated.emit(job)
        QApplication.processEvents()

    def _batch_control_state(self) -> str | None:
        """Return pause/cancel state for the core batch runner."""
        if self.cancel_requested:
            return "cancel"
        if self.pause_requested:
            return "pause"
        return None

    def toggle_pause(self) -> None:
        """Pause or resume between batch files."""
        self.pause_requested = not self.pause_requested
        self.pause_button.setText("Resume Batch" if self.pause_requested else "Pause After Current File")
        _set_status_badge(self.status_label, "RUNNING", "Status: Running - batch will pause after the current file." if self.pause_requested else "Status: Running - batch resumed.")

    def cancel_remaining(self) -> None:
        """Cancel files that have not started yet."""
        self.cancel_requested = True
        self.pause_requested = False
        self.pause_button.setText("Pause After Current File")
        _set_status_badge(self.status_label, "RUNNING", "Status: Running - cancelling remaining files after the current file.")

    def retry_failed_files(self) -> None:
        """Retry failed files from the last batch with current settings."""
        if not self.failed_paths:
            _set_status_badge(self.status_label, "WARNING", "Status: Needs review - no failed files are available to retry.")
            return
        self.discovered_paths = list(self.failed_paths)
        self.file_list.clear()
        for path in self.discovered_paths:
            row = QListWidgetItem(f"{path.name}\nStatus: retry queued; bounds: previous failure\n{path}")
            row.setFlags(row.flags() | Qt.ItemIsUserCheckable)
            row.setCheckState(Qt.Checked)
            row.setSizeHint(QSize(0, 72))
            self.file_list.addItem(row)
        self.failed_paths = []
        self.retry_failed_button.setEnabled(False)
        _set_status_badge(self.status_label, "WARNING", "Status: Needs review - failed files are queued for retry. Click Run Batch.")
        self._refresh_footprint_label()

    def open_batch_output_folder(self) -> None:
        """Open the latest batch folder, or the selected output root before a run."""
        folder = getattr(self.latest_result, "batch_folder", None)
        if folder is None:
            folder = Path(self.output_folder_edit.text().strip()) if self.output_folder_edit.text().strip() else None
        if folder is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _refresh_batch_results(self) -> None:
        """Refresh the visible batch result list using the selected filter."""
        selected_filter = self.result_filter_combo.currentText().lower() if hasattr(self, "result_filter_combo") else "all"
        self.batch_results.clear()
        products = ", ".join(PRODUCT_LABELS[product] for product, check in self.product_checks.items() if check.isChecked()) or "none"
        for item in self.batch_items:
            status = getattr(item, "status")
            if selected_filter != "all" and status != selected_filter:
                continue
            dataset_name = Path(getattr(item, "dataset_path")).name
            message = getattr(item, "message")
            run_folder = getattr(getattr(item, "run_context"), "run_folder")
            bounds = getattr(item, "bounds_summary", "Unavailable")
            progress = "100%" if status == "completed" else ("0%" if status == "skipped" else "needs review")
            output_count = len(getattr(item, "outputs", ()))
            self.batch_results.addItem(
                f"{status.upper()} - {dataset_name}\n"
                f"Products: {products}\n"
                f"Progress: {progress}; outputs: {output_count}\n"
                f"Output folder: {run_folder}\n"
                f"Bounds: {bounds}\n"
                f"Message: {message}"
            )

    def _set_batch_summary(self, result: object) -> None:
        """Display the completed batch summary."""
        total = len(getattr(result, "items", ()))
        completed = getattr(result, "success_count", 0)
        failed = getattr(result, "failure_count", 0)
        skipped = getattr(result, "skipped_count", 0)
        outputs = getattr(result, "total_output_count", 0)
        storage = _format_storage(getattr(result, "total_estimated_output_bytes", 0))
        self.summary_label.setText(
            f"Summary: total {total}; completed {completed}; failed {failed}; skipped {skipped}; "
            f"outputs {outputs}; observed output storage {storage}."
        )


class ResultsPage(MissionPage):
    """Friendly report links and job history page."""

    outputsLoaded = pyqtSignal(str, int, int)
    currentRunCleared = pyqtSignal()

    def __init__(self, iface: object | None = None, parent: QWidget | None = None) -> None:
        """Create the results page."""
        super().__init__("Results", parent)
        self.iface = iface
        self._friendly_paths: list[Path] = []
        self._advanced_paths: list[Path] = []
        self._job_result_paths: list[Path] = []
        self._job_result_types: dict[Path, str] = {}
        self._loaded_output_paths: set[Path] = set()
        self._current_output_folder: Path | None = None

        links = self.add_section("Generated Outputs")
        self.results_empty_label = _body_label(empty_state_message("results"))
        links.addWidget(self.results_empty_label)
        self.friendly_links = QListWidget()
        links.addWidget(self.friendly_links)
        self.friendly_links.setVisible(False)
        button_row = QHBoxLayout()
        self.open_output_folder_button = QPushButton("Open Output Folder")
        self.open_output_folder_button.setEnabled(False)
        self.open_output_folder_button.clicked.connect(self.open_output_folder)
        _apply_button_role(self.open_output_folder_button, "primary")
        self.load_outputs_button = QPushButton("Load Outputs")
        self.load_outputs_button.setEnabled(False)
        self.load_outputs_button.setToolTip("Load GeoTIFF and CSV outputs into the current QGIS project.")
        self.load_outputs_button.clicked.connect(self.load_outputs_to_qgis)
        _apply_button_role(self.load_outputs_button, "secondary")
        self.refresh_results_button = QPushButton("Refresh Results")
        self.refresh_results_button.clicked.connect(self.refresh_results)
        _apply_button_role(self.refresh_results_button, "neutral")
        self.clear_current_run_button = QPushButton("Clear Current Run")
        self.clear_current_run_button.setEnabled(False)
        self.clear_current_run_button.clicked.connect(self.clear_current_run)
        _apply_button_role(self.clear_current_run_button, "danger")
        button_row.addWidget(self.open_output_folder_button)
        button_row.addWidget(self.load_outputs_button)
        button_row.addWidget(self.refresh_results_button)
        button_row.addWidget(self.clear_current_run_button)
        button_row.addStretch(1)
        links.addLayout(button_row)
        self.product_status_label = _body_label("Generated Products: None\nLoaded Products: None\nAvailable Products: None")
        links.addWidget(self.product_status_label)
        self.load_message_label = _body_label("")
        self.load_message_label.setVisible(False)
        links.addWidget(self.load_message_label)

        jobs = self.add_section("Job History")
        self.jobs_section = jobs.parentWidget()
        self.job_history = QListWidget()
        jobs.addWidget(self.job_history)
        self.jobs_section.setVisible(False)

        advanced, advanced_layout = _collapsible_section(self.content_layout, "Run files and logs", checked=False)
        advanced_layout.addWidget(_details_label("Internal JSON, CSV, HTML reports, and logs are available here for reproducibility and troubleshooting."))
        row = QHBoxLayout()
        self.report_path_edit = QLineEdit()
        self.report_path_edit.setPlaceholderText("Choose JSON, CSV, or HTML report")
        browse = QPushButton("Browse")
        browse.clicked.connect(self.browse_report)
        open_button = QPushButton("Open")
        open_button.clicked.connect(self.open_report)
        row.addWidget(self.report_path_edit)
        row.addWidget(browse)
        row.addWidget(open_button)
        advanced_layout.addLayout(row)
        self.previous_reports = QListWidget()
        advanced_layout.addWidget(self.previous_reports)
        _wire_collapsible_group(advanced)

    def set_project_summary(self, summary: ProjectSummary) -> None:
        """Display generated, loaded, and available product state."""
        generated = ", ".join(item.label for item in summary.generated_products) or "None"
        loaded = ", ".join(item.label for item in summary.loaded_products) or "None"
        available = ", ".join(item.label for item in summary.available_products) or "None"
        missing = ", ".join(item.label for item in summary.missing_products) or "None"
        self.product_status_label.setText(
            f"Generated Products: {generated}\n"
            f"Loaded Products: {loaded}\n"
            f"Available Products: {available}\n"
            f"Missing Requested Products: {missing}"
        )

    def loaded_output_paths(self) -> tuple[Path, ...]:
        """Return outputs loaded through the Results page in this session."""
        return tuple(self._loaded_output_paths)

    def refresh_results(self) -> None:
        """Refresh Results button states from current paths without clearing outputs."""
        candidates = self._candidate_output_paths()
        loadable = collect_loadable_outputs(tuple(path for path in candidates if path.exists() and path.is_file()), self._job_result_types)
        has_paths = bool(candidates)
        self.friendly_links.setVisible(bool(self._friendly_paths))
        self.results_empty_label.setVisible(not self._friendly_paths)
        self.open_output_folder_button.setEnabled(self._current_output_folder is not None and self._current_output_folder.exists())
        self.load_outputs_button.setEnabled(bool(loadable))
        self.clear_current_run_button.setEnabled(has_paths or self._current_output_folder is not None)
        self._set_load_message("Results refreshed." if has_paths else "Results refreshed. No current outputs found.")

    def set_run_context(self, context: RunContext | None) -> None:
        """Display friendly run links for the active context."""
        self.friendly_links.clear()
        self.previous_reports.clear()
        self._friendly_paths = []
        self._advanced_paths = []
        self._job_result_paths = []
        self._job_result_types = {}
        self._current_output_folder = None
        self.open_output_folder_button.setEnabled(False)
        self.load_outputs_button.setEnabled(False)
        self.clear_current_run_button.setEnabled(False)
        self.friendly_links.setVisible(False)
        self.results_empty_label.setVisible(True)
        self.load_message_label.setVisible(False)
        if context is None:
            self._loaded_output_paths = set()
            return
        self._current_output_folder = context.outputs_dir
        self.clear_current_run_button.setEnabled(True)
        for label, path in context.friendly_links:
            self._friendly_paths.append(path)
            self.friendly_links.addItem(f"{label}: {path}")
        has_outputs = bool(self._friendly_paths)
        self.friendly_links.setVisible(has_outputs)
        self.results_empty_label.setVisible(not has_outputs)
        self.open_output_folder_button.setEnabled(has_outputs)
        self.load_outputs_button.setEnabled(has_outputs)
        for label, path in context.advanced_paths:
            self._advanced_paths.append(path)
            self.previous_reports.addItem(f"{label}: {path}")

    def browse_report(self) -> None:
        """Choose a report file."""
        path, _ = QFileDialog.getOpenFileName(self, "Choose report", "", "Reports (*.json *.csv *.html);;All files (*.*)")
        if path:
            self.report_path_edit.setText(path)
            self.previous_reports.addItem(path)
            self._advanced_paths.append(Path(path))

    def set_report_paths(self, paths: tuple[Path, ...]) -> None:
        """Display recently recorded report paths in advanced details."""
        for path in paths:
            text = str(path)
            if _is_friendly_result_path(path) and path not in self._friendly_paths:
                self._friendly_paths.append(path)
                label = _friendly_result_label(path)
                self.friendly_links.addItem(f"{label}: {path}")
                self.friendly_links.setVisible(True)
                self.results_empty_label.setVisible(False)
                self.open_output_folder_button.setEnabled(self._current_output_folder is not None)
                self.load_outputs_button.setEnabled(True)
                self.clear_current_run_button.setEnabled(True)
            if not any(self.previous_reports.item(index).text().endswith(text) for index in range(self.previous_reports.count())):
                self.previous_reports.addItem(text)
                self._advanced_paths.append(path)

    def set_jobs(self, jobs: tuple[JobRecord, ...]) -> None:
        """Display job history."""
        self.job_history.clear()
        self._job_result_paths = []
        self._job_result_types = {}
        self.jobs_section.setVisible(bool(jobs))
        for job in jobs:
            detail = f"{job.title} - {job.status.value} - {job.progress.percent:.0f}%"
            for result in job.results:
                self._job_result_paths.append(result.path)
                self._job_result_types[result.path] = result.result_type
            if job.results:
                detail = f"{detail} - {job.results[-1].path}"
            self.job_history.addItem(detail)
        self.load_outputs_button.setEnabled(bool(self._candidate_output_paths()))

    def load_outputs_to_qgis(self) -> None:
        """Load current run GeoTIFF and CSV outputs into QGIS without duplicates."""
        self.load_outputs_button.setEnabled(False)
        self._set_load_message("Loading outputs into QGIS...")
        QApplication.processEvents()
        paths = [path for path in self._candidate_output_paths() if path.exists() and path.is_file()]
        all_candidates = collect_loadable_outputs(paths, self._job_result_types)
        existing_sources = tuple(self._loaded_output_paths) + self._project_layer_sources()
        candidates = collect_loadable_outputs(paths, self._job_result_types, existing_sources)
        if not candidates:
            message = output_loading_summary(0, len(all_candidates))
            self._set_load_message(message)
            self.load_outputs_button.setEnabled(bool(all_candidates))
            self.outputsLoaded.emit(message, 0, len(all_candidates))
            return
        if self.iface is None:
            self._set_load_message("QGIS interface unavailable.")
            self.load_outputs_button.setEnabled(True)
            self.outputsLoaded.emit("QGIS interface unavailable.", 0, len(candidates))
            return
        loaded = 0
        for output in candidates:
            if self._load_output(output):
                self._loaded_output_paths.add(output.path)
                loaded += 1
        message = output_loading_summary(loaded, len(candidates))
        self._set_load_message(message)
        self.load_outputs_button.setEnabled(bool(self._candidate_output_paths()))
        self.outputsLoaded.emit(message, loaded, len(candidates))

    def _candidate_output_paths(self) -> tuple[Path, ...]:
        """Return current run, report, and job paths that may be loadable."""
        paths: list[Path] = []
        paths.extend(self._friendly_paths)
        paths.extend(self._advanced_paths)
        paths.extend(self._job_result_paths)
        if self._current_output_folder is not None and self._current_output_folder.exists():
            paths.extend(path for path in self._current_output_folder.rglob("*") if path.is_file())
        return tuple(paths)

    def _project_layer_sources(self) -> tuple[str, ...]:
        """Return existing QGIS layer source paths, if QGIS APIs are available."""
        try:
            from qgis.core import QgsProject

            layers = QgsProject.instance().mapLayers().values()
        except Exception:  # noqa: BLE001 - tests and some QGIS states may not expose QgsProject.
            return ()
        sources: list[str] = []
        for layer in layers:
            source = getattr(layer, "source", None)
            if callable(source):
                try:
                    sources.append(str(source()))
                except Exception:  # noqa: BLE001 - one bad layer should not block loading.
                    continue
        return tuple(sources)

    def _load_output(self, output: LoadableOutput) -> bool:
        """Load one output into QGIS and apply product styling when relevant."""
        layer_name = self._output_layer_name(output)
        try:
            if output.layer_kind == "raster":
                layer = self.iface.addRasterLayer(str(output.path), layer_name)
                if layer is not None:
                    apply_generated_raster_renderer(layer, output.result_type)
            else:
                layer = self.iface.addVectorLayer(str(output.path), layer_name, "ogr")
        except Exception:  # noqa: BLE001 - loading feedback should stay concise.
            return False
        return layer is not None

    def _output_layer_name(self, output: LoadableOutput) -> str:
        """Return a readable QGIS layer name for a loadable output."""
        if output.layer_kind == "raster":
            dataset_stem = output.path.parent.parent.name if output.path.parent.name == "outputs" else output.path.stem
            return layer_display_name(output.result_type, dataset_stem)
        return _friendly_result_label(output.path)

    def _set_load_message(self, message: str) -> None:
        self.load_message_label.setText(message)
        self.load_message_label.setVisible(True)

    def open_selected_link(self) -> None:
        """Open the selected friendly result link."""
        row = self.friendly_links.currentRow()
        if 0 <= row < len(self._friendly_paths):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._friendly_paths[row])))

    def open_output_folder(self) -> None:
        """Open the current run output folder."""
        if self._current_output_folder is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._current_output_folder)))

    def clear_current_run(self) -> None:
        """Clear current run links from the Results page."""
        self.friendly_links.clear()
        self.previous_reports.clear()
        self.job_history.clear()
        self._friendly_paths = []
        self._advanced_paths = []
        self._job_result_paths = []
        self._job_result_types = {}
        self._loaded_output_paths = set()
        self._current_output_folder = None
        self.open_output_folder_button.setEnabled(False)
        self.load_outputs_button.setEnabled(False)
        self.clear_current_run_button.setEnabled(False)
        self.friendly_links.setVisible(False)
        self.results_empty_label.setVisible(True)
        self.jobs_section.setVisible(False)
        self.currentRunCleared.emit()

    def open_report(self) -> None:
        """Open the selected advanced report with the desktop handler."""
        path = self.report_path_edit.text().strip()
        if not path and self.previous_reports.currentItem() is not None:
            text = self.previous_reports.currentItem().text()
            path = text.split(": ", 1)[-1]
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))


class SettingsPage(MissionPage):
    """Plugin settings page."""

    defaultOutputFolderChanged = pyqtSignal(object)
    backendStateChanged = pyqtSignal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the settings page."""
        super().__init__("Settings", parent)
        defaults = self.add_section("Defaults")
        form = QFormLayout()
        self.default_output_folder = QLineEdit()
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.default_output_folder)
        browse = QPushButton("Browse")
        browse.clicked.connect(self.browse_default_output_folder)
        folder_row.addWidget(browse)
        form.addRow("Default output folder", folder_row)
        defaults.addLayout(form)
        apply_button = QPushButton("Use This Folder")
        apply_button.clicked.connect(self.emit_default_output_folder)
        defaults.addWidget(apply_button)

        workspace = self.add_section("Workspace Defaults")
        workspace_form = QFormLayout()
        self.remember_workspace_check = QCheckBox("Remember last workspace")
        self.remember_workspace_check.setChecked(True)
        self.remember_dataset_check = QCheckBox("Remember last dataset")
        self.remember_dataset_check.setChecked(True)
        self.remember_output_folder_check = QCheckBox("Remember last output folder")
        self.remember_output_folder_check.setChecked(True)
        self.auto_save_workspace_check = QCheckBox("Auto-save workspace state")
        self.auto_save_workspace_check.setChecked(True)
        self.maximum_recent_items_spin = QSpinBox()
        self.maximum_recent_items_spin.setMinimum(1)
        self.maximum_recent_items_spin.setMaximum(50)
        self.maximum_recent_items_spin.setValue(10)
        workspace_form.addRow("Workspace", self.remember_workspace_check)
        workspace_form.addRow("Dataset", self.remember_dataset_check)
        workspace_form.addRow("Output folder", self.remember_output_folder_check)
        workspace_form.addRow("Auto-save", self.auto_save_workspace_check)
        workspace_form.addRow("Recent item limit", self.maximum_recent_items_spin)
        workspace.addLayout(workspace_form)

        backend = self.add_section("Backend")
        backend.addWidget(_body_label("Windows beta builds can install a user-local backend. This does not modify QGIS Python, system Python, PATH, shell profiles, or QGIS folders."))
        self.backend_service = BackendService()
        self.backend_install_running = False
        self.backend_install_thread: QThread | None = None
        self.backend_install_worker: _BackendInstallWorker | None = None
        self.backend_install_started_at: float | None = None
        self.backend_install_timer = QTimer(self)
        self.backend_install_timer.setInterval(1000)
        self.backend_install_timer.timeout.connect(self._refresh_backend_install_elapsed)
        self.backend_status_label = _body_label("")
        _set_status_badge(self.backend_status_label, "NOT CONFIGURED", readiness_status_text("NOT CONFIGURED", "Backend Status: Not set up - verify backend."))
        self.backend_location_label = _body_label("Backend Location: Unknown")
        self.backend_environment_label = _body_label("Environment Location: Unknown")
        self.backend_installed_version_label = _body_label("Installed Version: Not installed")
        self.backend_plugin_version_label = _body_label("Plugin Version: Unknown")
        self.backend_manifest_version_label = _body_label("Backend recipe version: Unknown")
        self.backend_python_label = _body_label("Python Version: Not detected")
        self.backend_pdal_label = _body_label("PDAL Version: Not detected")
        self.backend_dependency_label = _body_label("Verification: Not checked")
        self.zip_install_ready_label = _body_label("Plugin ZIP: not checked")
        self.backend_auto_install_ready_label = _body_label("Backend installer: Not checked")
        self.manual_dependency_setup_label = _body_label("Manual setup: Required until the backend is ready")
        self.qgis_compatibility_label = _body_label("QGIS compatibility: Not checked")
        self.backend_install_readiness_label = _body_label("Backend setup: Not checked")
        for label in (
            self.backend_status_label,
            self.backend_dependency_label,
            self.zip_install_ready_label,
            self.backend_auto_install_ready_label,
            self.manual_dependency_setup_label,
            self.qgis_compatibility_label,
            self.backend_install_readiness_label,
        ):
            backend.addWidget(label)

        backend_detail_group, backend_detail_layout = _collapsible_section(self.content_layout, "Advanced / Troubleshooting: backend details", checked=False)
        for label in (
            self.backend_location_label,
            self.backend_environment_label,
            self.backend_installed_version_label,
            self.backend_plugin_version_label,
            self.backend_manifest_version_label,
            self.backend_python_label,
            self.backend_pdal_label,
        ):
            backend_detail_layout.addWidget(label)
        _wire_collapsible_group(backend_detail_group)

        self.backend_install_progress_bar = QProgressBar()
        self.backend_install_progress_bar.setRange(0, 100)
        self.backend_install_progress_bar.setValue(0)
        backend.addWidget(self.backend_install_progress_bar)
        self.backend_install_stage_label = _body_label("Stage: Not running")
        self.backend_install_action_label = _body_label("Current step: None")
        self.backend_install_elapsed_label = _body_label("Elapsed time: 00:00")
        self.backend_install_message_label = _body_label("Latest message: No backend install is running.")
        self.backend_install_estimate_label = _body_label("Step progress is estimated.")
        for label in (
            self.backend_install_stage_label,
            self.backend_install_action_label,
            self.backend_install_elapsed_label,
            self.backend_install_message_label,
            self.backend_install_estimate_label,
        ):
            backend.addWidget(label)
        self._set_backend_progress_visible(False)

        install_availability = self.backend_service.install_availability()
        self.verify_backend_button = QPushButton(primary_action_label("settings"))
        self.verify_backend_button.clicked.connect(self.verify_backend)
        _apply_button_role(self.verify_backend_button, "primary")
        self.install_backend_button = QPushButton(install_availability.button_label)
        self.install_backend_button.setEnabled(install_availability.enabled)
        _apply_button_role(self.install_backend_button, "primary" if install_availability.enabled else "neutral")
        if install_availability.enabled:
            self.install_backend_button.clicked.connect(self.install_backend_internal_beta)
        self.repair_backend_button = QPushButton("Repair")
        self.repair_backend_button.clicked.connect(self.repair_backend_preview)
        _apply_button_role(self.repair_backend_button, "secondary")
        self.preview_install_plan_button = QPushButton("Preview Install Plan")
        self.preview_install_plan_button.clicked.connect(self.preview_install_plan)
        _apply_button_role(self.preview_install_plan_button, "secondary")
        self.verify_qgis_button = QPushButton("Verify QGIS Compatibility")
        self.verify_qgis_button.clicked.connect(self.verify_qgis_compatibility)
        _apply_button_role(self.verify_qgis_button, "neutral")
        self.manual_setup_button = QPushButton("Manual Setup Instructions")
        self.manual_setup_button.clicked.connect(self.show_manual_setup_instructions)
        _apply_button_role(self.manual_setup_button, "secondary")
        self.open_backend_folder_button = QPushButton("Open Backend Folder")
        self.open_backend_folder_button.clicked.connect(self.open_backend_folder)
        _apply_button_role(self.open_backend_folder_button, "secondary")
        self.view_backend_logs_button = QPushButton("View Logs")
        self.view_backend_logs_button.clicked.connect(self.view_backend_logs)
        _apply_button_role(self.view_backend_logs_button, "secondary")
        self.advanced_backend_button = QPushButton("Advanced")
        self.advanced_backend_button.clicked.connect(self.show_backend_advanced)
        _apply_button_role(self.advanced_backend_button, "secondary")
        self.developer_mode_button = QPushButton("Internal Beta Install: On" if install_availability.enabled else "Internal Beta Install: Off")
        self.developer_mode_button.setEnabled(False)
        self.developer_mode_button.setVisible(False)
        _apply_button_role(self.developer_mode_button, "neutral")

        self.backend_primary_buttons = QHBoxLayout()
        self.backend_primary_buttons.setSpacing(ACTION_ROW_SPACING)
        for button in (self.verify_backend_button, self.install_backend_button, self.repair_backend_button):
            self.backend_primary_buttons.addWidget(button)
        self.backend_primary_buttons.addStretch(1)
        backend.addLayout(self.backend_primary_buttons)

        self.backend_secondary_buttons = QHBoxLayout()
        self.backend_secondary_buttons.setSpacing(ACTION_ROW_SPACING)
        for button in (
            self.preview_install_plan_button,
            self.verify_qgis_button,
            self.manual_setup_button,
            self.open_backend_folder_button,
            self.view_backend_logs_button,
            self.advanced_backend_button,
            self.developer_mode_button,
        ):
            self.backend_secondary_buttons.addWidget(button)
        self.backend_secondary_buttons.addStretch(1)
        backend.addLayout(self.backend_secondary_buttons)

        self.backend_details = QTextEdit()
        self.backend_details.setReadOnly(True)
        self.backend_details.setMinimumHeight(TECHNICAL_DETAIL_HEIGHT)
        self.backend_details.setPlainText("Verify or install the user-local backend from this page. Technical reports and logs stay under Advanced / Troubleshooting.")
        backend.addWidget(self.backend_details)
        self.backend_technical_log_group = QGroupBox("Troubleshooting: technical log")
        self.backend_technical_log_group.setCheckable(True)
        self.backend_technical_log_group.setChecked(False)
        technical_layout = QVBoxLayout()
        self.backend_technical_log = QTextEdit()
        self.backend_technical_log.setReadOnly(True)
        self.backend_technical_log.setVisible(False)
        self.backend_technical_log_group.toggled.connect(self.backend_technical_log.setVisible)
        technical_layout.addWidget(self.backend_technical_log)
        self.backend_technical_log_group.setLayout(technical_layout)
        backend.addWidget(self.backend_technical_log_group)
        self.refresh_backend_summary()

    def set_workspace_session(self, session: WorkspaceSession) -> None:
        """Display persisted workspace session preferences."""
        self.remember_workspace_check.setChecked(session.remember_last_workspace)
        self.remember_dataset_check.setChecked(session.remember_last_dataset)
        self.remember_output_folder_check.setChecked(session.remember_last_output_folder)
        self.auto_save_workspace_check.setChecked(session.auto_save_enabled)
        self.maximum_recent_items_spin.setValue(session.maximum_recent_items)

    def workspace_session_preferences(self, session: WorkspaceSession) -> WorkspaceSession:
        """Return session with settings-page workspace preferences applied."""
        return WorkspaceSession(
            last_opened_workspace=session.last_opened_workspace,
            last_selected_dataset=session.last_selected_dataset,
            last_output_folder=session.last_output_folder,
            last_planner_settings=session.last_planner_settings,
            last_selected_products=session.last_selected_products,
            last_page=session.last_page,
            window_geometry=session.window_geometry,
            floating=session.floating,
            docked=session.docked,
            remember_last_workspace=self.remember_workspace_check.isChecked(),
            remember_last_dataset=self.remember_dataset_check.isChecked(),
            remember_last_output_folder=self.remember_output_folder_check.isChecked(),
            maximum_recent_items=self.maximum_recent_items_spin.value(),
            auto_save_enabled=self.auto_save_workspace_check.isChecked(),
        )

    def browse_default_output_folder(self) -> None:
        """Choose the default output folder for Mission Control runs."""
        path = QFileDialog.getExistingDirectory(self, "Choose default output folder")
        if path:
            self.default_output_folder.setText(path)
            self.emit_default_output_folder()

    def emit_default_output_folder(self) -> None:
        """Emit the configured default output folder."""
        value = self.default_output_folder.text().strip()
        self.defaultOutputFolderChanged.emit(Path(value) if value else None)

    def refresh_backend_summary(self) -> None:
        """Display backend path, install-plan readiness, and detected state."""
        state = self.backend_service.detect_backend()
        paths = self.backend_service.paths
        registry = self.backend_service.get_registry()
        plan = self.backend_service.preview_install_plan()
        manifest = self.backend_service.backend_manifest()
        version = self.backend_service.version_compatibility()
        compatibility = build_qgis_compatibility_report()
        availability = self.backend_service.install_availability()
        _set_status_badge(self.backend_status_label, state.status.value, readiness_status_text(state.status.value, f"Backend Status: {status_badge_label(state.status.value)} - {state.message}"))
        self.backend_location_label.setText(f"Storage Location: {paths.backend_root}")
        self.backend_environment_label.setText(f"Environment Location: {paths.environment_path}")
        self.backend_installed_version_label.setText(f"Installed Version: {'configured' if state.config_exists else 'Not installed'}")
        self.backend_plugin_version_label.setText(f"Plugin Version: {self.backend_service.plugin_version}")
        self.backend_manifest_version_label.setText(f"Backend recipe version: {manifest.backend_version if manifest else 'Unavailable'}")
        required_count = len(registry.required_dependencies())
        total_count = len(registry.dependencies)
        self.backend_dependency_label.setText(f"Verification: {required_count} required checks; {total_count - required_count} optional checks")
        self.zip_install_ready_label.setText("Plugin ZIP: ready for QGIS Plugin Manager installs")
        auto_ready = "available on Windows beta builds" if availability.enabled else f"not available; {availability.reason}"
        self.backend_auto_install_ready_label.setText(f"Backend installer: {auto_ready}")
        if state.status.value == "Ready":
            manual_text = "Manual setup: not required for PBM-routed products"
        else:
            manual_text = "Manual setup: not required after PBM is ready; QGIS-Python-only tools still show their own requirements"
        self.manual_dependency_setup_label.setText(manual_text)
        compat_text = version.message if version else "Backend recipe unavailable"
        self.qgis_compatibility_label.setText(f"QGIS compatibility: {compatibility.summary()}; backend {compat_text}")
        self.backend_install_readiness_label.setText(f"Backend setup: {availability.reason}; {len(plan.required_package_names())} packages planned")
        if not self.backend_install_running:
            self.install_backend_button.setText(availability.button_label)
            self.install_backend_button.setEnabled(availability.enabled)
        self.developer_mode_button.setText("Internal Beta Install: On" if availability.enabled else "Internal Beta Install: Off")
        if self.backend_install_running:
            return
        self.backend_details.setPlainText(
            f"{state.message}\n\n"
            "Normal beta path: install or verify PBM, then run Environment Check. "
            "PBM writes only to the user-local PyForestScan backend folder and does not modify QGIS Python, system Python, PATH, shell profiles, or QGIS folders. "
            "Technical plans and logs are available from Preview Install, Advanced, or View Logs."
        )

    def verify_backend(self) -> None:
        """Run safe PBM verification and display dependency results."""
        self.verify_backend_button.setEnabled(False)
        _set_status_badge(self.backend_status_label, "RUNNING", readiness_status_text("RUNNING", "Backend Status: Running - verifying backend."))
        QApplication.processEvents()
        try:
            result = self.backend_service.verify_backend()
        finally:
            self.verify_backend_button.setEnabled(True)
        _set_status_badge(self.backend_status_label, result.status.value, readiness_status_text(result.status.value, f"Backend Status: {status_badge_label(result.status.value)}"))
        python_dependency = _find_backend_dependency(result, "python")
        pdal_dependency = _find_backend_dependency(result, "pdal")
        self.backend_python_label.setText(f"Python Version: {python_dependency.detected_version if python_dependency and python_dependency.detected_version else 'Not detected'}")
        self.backend_pdal_label.setText(f"PDAL Version: {pdal_dependency.detected_version if pdal_dependency and pdal_dependency.detected_version else 'Not detected'}")
        required = result.registry.required_dependencies()
        verified_required = sum(1 for dependency in required if dependency.verification_status.value == "pass")
        self.refresh_backend_summary()
        _set_status_badge(self.backend_status_label, result.status.value, readiness_status_text(result.status.value, f"Backend Status: {status_badge_label(result.status.value)}"))
        self.backend_dependency_label.setText(f"Verification: {verified_required}/{len(required)} required checks passed")
        self.backend_details.setPlainText(self.backend_service.format_verification_report(result))
        self.backendStateChanged.emit(result.status.value, "Backend verification complete.")

    def verify_qgis_compatibility(self) -> None:
        """Display defensive QGIS compatibility details."""
        report = build_qgis_compatibility_report()
        self.qgis_compatibility_label.setText(f"QGIS compatibility: {report.summary()}")
        self.backend_details.setPlainText(format_qgis_compatibility_report(report))

    def preview_install_plan(self) -> None:
        """Display the dry-run backend installation plan."""
        plan = self.backend_service.preview_install_plan()
        availability = self.backend_service.install_availability()
        self.backend_install_readiness_label.setText(f"Backend setup: {availability.reason}; {len(plan.required_package_names())} packages planned")
        self.backend_details.setPlainText(self.backend_service.format_install_plan(plan))

    def install_backend_internal_beta(self) -> None:
        """Confirm and run the Windows internal beta backend installer."""
        availability = self.backend_service.install_availability()
        if not availability.enabled:
            self.backend_details.setPlainText(f"Install Backend is not available for this platform.\n\n{availability.reason}")
            return
        message = (
            "This will install PyForestScan backend packages into your user-local PyForestScan folder. "
            "It will not modify QGIS or system Python.\n\n"
            f"Backend folder: {self.backend_service.paths.backend_root}\n"
            "The installer downloads Micromamba, creates the backend, verifies it, and writes settings only under that folder."
        )
        reply = QMessageBox.question(
            self,
            "Install PyForestScan Backend",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            self.backend_details.setPlainText("Backend installation canceled before any installer action was started.")
            return
        self._start_backend_install_worker()

    def _start_backend_install_worker(self) -> None:
        """Start PBM installation on a background Qt worker thread."""
        if self.backend_install_running:
            self.backend_details.setPlainText("Installation is running. Please wait for this step to finish.")
            return
        self.backend_install_thread = QThread(self)
        self.backend_install_worker = _BackendInstallWorker(self.backend_service)
        self.backend_install_worker.moveToThread(self.backend_install_thread)
        self.backend_install_thread.started.connect(self.backend_install_worker.run)
        self.backend_install_worker.progressUpdated.connect(self._on_backend_install_progress)
        self.backend_install_worker.completed.connect(self._on_backend_install_complete)
        self.backend_install_worker.failed.connect(self._on_backend_install_failed)
        self.backend_install_worker.completed.connect(self.backend_install_thread.quit)
        self.backend_install_worker.failed.connect(self.backend_install_thread.quit)
        self.backend_install_thread.finished.connect(self.backend_install_worker.deleteLater)
        self.backend_install_thread.finished.connect(self.backend_install_thread.deleteLater)
        self.backend_install_thread.finished.connect(self._clear_backend_install_thread)
        self._set_backend_install_running(True)
        self.backend_install_thread.start()

    def _set_backend_install_running(self, running: bool) -> None:
        """Disable install/repair/update-style controls while PBM installation runs."""
        self.backend_install_running = running
        if running:
            self._set_backend_progress_visible(True)
            self.backend_install_started_at = time.monotonic()
            self.backend_install_timer.start()
            _set_status_badge(self.backend_status_label, "RUNNING", readiness_status_text("RUNNING", "Backend Status: Running - installation in progress."))
            self.backend_install_progress_bar.setValue(5)
            self.backend_install_stage_label.setText("Stage: Preparing")
            self.backend_install_action_label.setText("Current step: preparing files")
            self.backend_install_message_label.setText("Latest message: Installation is running. Please wait for this step to finish.")
            self.backend_install_estimate_label.setText("Step progress is estimated.")
            self.backend_details.setPlainText(
                "Backend installation is running in the background.\n\n"
                "Installation is running. Please wait for this step to finish.\n"
                "Step progress is estimated. Technical logs are hidden under Troubleshooting."
            )
        else:
            self.backend_install_timer.stop()
            self.backend_install_started_at = None
        availability = self.backend_service.install_availability()
        for button in self._backend_install_action_buttons():
            button.setEnabled(not running)
        if not running:
            self.install_backend_button.setText(availability.button_label)
            self.install_backend_button.setEnabled(availability.enabled)

    def _set_backend_progress_visible(self, visible: bool) -> None:
        """Show PBM progress UI only while it is useful."""
        for widget in (
            self.backend_install_progress_bar,
            self.backend_install_stage_label,
            self.backend_install_action_label,
            self.backend_install_elapsed_label,
            self.backend_install_message_label,
            self.backend_install_estimate_label,
        ):
            widget.setVisible(visible)

    def _backend_install_action_buttons(self) -> tuple[QPushButton, ...]:
        """Return controls disabled while install is running."""
        return (
            self.verify_backend_button,
            self.verify_qgis_button,
            self.preview_install_plan_button,
            self.install_backend_button,
            self.repair_backend_button,
            self.manual_setup_button,
        )

    def _on_backend_install_progress(self, update: object) -> None:
        """Update visible staged progress from worker-thread installer updates."""
        percentage = getattr(update, "percentage", None)
        if percentage is not None:
            self.backend_install_progress_bar.setValue(int(percentage))
        stage = getattr(getattr(update, "stage", None), "value", getattr(update, "stage", "Unknown"))
        current = getattr(update, "current_package", "") or "current step"
        message = getattr(update, "message", "") or "Working..."
        estimate = getattr(update, "estimated_remaining_step", "") or "Step progress is estimated."
        self.backend_install_stage_label.setText(f"Stage: {stage}")
        self.backend_install_action_label.setText(f"Current step: {current}")
        self.backend_install_message_label.setText(f"Latest message: {message}")
        self.backend_install_estimate_label.setText(estimate)
        self._refresh_backend_install_elapsed()

    def _on_backend_install_complete(self, result: object) -> None:
        """Render final PBM install state after background worker completion."""
        self._set_backend_install_running(False)
        self._set_backend_progress_visible(True)
        self.refresh_backend_summary()
        status_value = getattr(getattr(result, "status", None), "value", str(getattr(result, "status", "Unknown")))
        success = bool(getattr(result, "success", False))
        if success:
            final_state = "Backend Ready"
            self.backend_install_progress_bar.setValue(100)
        elif status_value == "Repair Required":
            final_state = "Repair Required"
        else:
            final_state = "Install Failed"
        _set_status_badge(self.backend_status_label, final_state, readiness_status_text(final_state, f"Backend Status: {status_badge_label(final_state)} - {final_state}"))
        self.backend_install_stage_label.setText(f"Stage: {final_state}")
        self.backend_install_message_label.setText(f"Latest message: {getattr(result, 'message', '')}")
        self.backend_details.setPlainText(
            "PBM Backend Install Result\n\n"
            f"Final state: {final_state}\n"
            f"Operation: {getattr(result, 'operation', 'install_backend')}\n"
            f"Success: {success}\n"
            f"Status: {status_value}\n"
            f"Modified user-local backend files: {getattr(result, 'modified_system', False)}\n"
            f"Log path: {getattr(result, 'log_path', None) or self.backend_service.paths.install_log}\n"
            f"Message: {getattr(result, 'message', '')}\n\n"
            "Use Repair if installation failed. Technical logs are available under Troubleshooting or View Logs."
        )
        self._refresh_backend_technical_log()
        notice = "Backend installed successfully." if success else "Backend installation needs review."
        self.backendStateChanged.emit(status_value, notice)

    def _on_backend_install_failed(self, message: str) -> None:
        """Display unexpected installer worker failure."""
        self._set_backend_install_running(False)
        self._set_backend_progress_visible(True)
        _set_status_badge(self.backend_status_label, "FAILED", readiness_status_text("FAILED", "Backend Status: Failed - install failed."))
        self.backend_install_stage_label.setText("Stage: Install Failed")
        self.backend_install_message_label.setText(f"Latest message: {message}")
        self.backend_details.setPlainText(
            "PBM Backend Install Result\n\n"
            "Final state: Install Failed\n"
            f"Message: {message}\n\n"
            "Use View Logs for details. Technical logs are hidden under Troubleshooting."
        )
        self._refresh_backend_technical_log()
        self.backendStateChanged.emit("Failed", "Backend installation failed. Use View Logs for details.")

    def _refresh_backend_install_elapsed(self) -> None:
        """Update elapsed install time without implying exact step duration."""
        if self.backend_install_started_at is None:
            return
        elapsed = max(0, int(time.monotonic() - self.backend_install_started_at))
        minutes, seconds = divmod(elapsed, 60)
        self.backend_install_elapsed_label.setText(f"Elapsed time: {minutes:02d}:{seconds:02d}")

    def _refresh_backend_technical_log(self) -> None:
        """Load recent install logs into the hidden advanced log panel."""
        logs = self.backend_service.get_logs().get("install", ())
        self.backend_technical_log.setPlainText("\n".join(logs[-60:]) if logs else "No install log entries yet.")

    def _clear_backend_install_thread(self) -> None:
        """Clear backend install worker references after Qt cleanup."""
        self.backend_install_thread = None
        self.backend_install_worker = None

    def install_backend_experimental(self) -> None:
        """Backward-compatible wrapper for older tests and docs."""
        self.install_backend_internal_beta()


    def repair_backend_preview(self) -> None:
        """Display the non-mutating backend repair plan."""
        result = self.backend_service.repair_backend()
        plan = self.backend_service.preview_repair_plan()
        self.refresh_backend_summary()
        _set_status_badge(self.backend_status_label, result.status.value, readiness_status_text(result.status.value, f"Backend Status: {status_badge_label(result.status.value)}"))
        self.backend_details.setPlainText(self.backend_service.format_repair_plan(plan))
        self.backendStateChanged.emit(result.status.value, "Backend repair plan updated.")

    def show_backend_advanced(self) -> None:
        """Display advanced PBM architecture details."""
        modules = self.backend_service.module_registry()
        manifest = self.backend_service.backend_manifest()
        version = self.backend_service.version_compatibility()
        lines = [
            "Backend Technical Details",
            f"Installer availability: {'enabled' if self.backend_service.backend_install_enabled() else 'off'}",
            f"Manifest backend version: {manifest.backend_version if manifest else 'Unavailable'}",
            f"Manifest environment version: {manifest.environment_version if manifest else 'Unavailable'}",
            f"Version compatibility: {version.message if version else 'Unavailable'}",
            "",
            "Logs:",
            f"- Install: {self.backend_service.paths.install_log}",
            f"- Download: {self.backend_service.paths.download_log}",
            f"- Verify: {self.backend_service.paths.verify_log}",
            f"- Repair: {self.backend_service.paths.repair_log}",
            "",
            "Planned modules:",
            *[f"- {name}" for name in modules.names()],
        ]
        if version and version.warnings:
            lines.extend(("", "Warnings:"))
            lines.extend(f"- {warning}" for warning in version.warnings)
        self.backend_details.setPlainText("\n".join(lines))


    def show_manual_setup_instructions(self) -> None:
        """Display current dependency setup guidance for clean ZIP installs."""
        self.backend_details.setPlainText(
            "Manual Setup Instructions\n\n"
            "ZIP installation installs only the QGIS plugin. PBM backend installation creates an isolated, user-local PyForestScan backend and does not install packages into QGIS Python, system Python, PATH, shell profiles, or QGIS folders.\n\n"
            "Current release status:\n"
            "- Plugin ZIP: ready for QGIS Plugin Manager installs.\n"
            "- Backend installer: available on Windows beta builds after confirmation.\n"
            "- Manual setup: not required after PBM backend installation verifies successfully; QGIS-Python-only tools still show their own requirements.\n\n"
            "Next steps:\n"
            "1. Install the ZIP through QGIS Plugin Manager.\n"
            "2. Open Mission Control and run Environment Check.\n"
            "3. Open Backend settings and click Install Backend on Windows beta builds.\n"
            "4. Verify Backend until status is Ready before running Guided, Advanced, or Batch workflows.\n\n"
            "Reference docs: docs/INSTALLATION_STRATEGY.md, docs/releases/CLEAN_MACHINE_SMOKE_TEST.md, and docs/releases/PBM_INTERNAL_BETA_SMOKE_TEST.md."
        )

    def open_backend_folder(self) -> None:
        """Open the backend folder if it already exists, otherwise show the planned path."""
        folder = self.backend_service.open_backend_folder_path()
        if folder.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        else:
            self.backend_details.setPlainText(
                f"Backend folder does not exist yet: {folder}\n\n"
                "Backend installation will create only this user-local directory after confirmation. "
                "Use Preview Install to review the backend layout before installing."
            )

    def view_backend_logs(self) -> None:
        """Display recent PBM log lines if logs exist."""
        logs = self.backend_service.get_logs()
        lines = []
        for operation, entries in logs.items():
            lines.append(f"[{operation}]")
            lines.extend(entries or ("No log entries.",))
            lines.append("")
        self.backend_details.setPlainText("\n".join(lines).strip())

def _processing_lifecycle_stage(job: JobRecord) -> str:
    """Return the common user-facing processing lifecycle stage."""
    if job.status in {JobStatus.PENDING, JobStatus.VALIDATING}:
        return "Preparing"
    if job.status is JobStatus.RUNNING:
        return "Generating Outputs" if job.results else "Running"
    if job.status is JobStatus.COMPLETED:
        return "Complete"
    if job.status is JobStatus.FAILED:
        return "Failed"
    if job.status is JobStatus.CANCELLING:
        return "Cancelling"
    if job.status is JobStatus.CANCELLED:
        return "Cancelled"
    return status_display_word(job.status.value)


def _find_backend_dependency(result: object, name: str):
    """Return one backend dependency from a verification result by name."""
    for dependency in result.registry.dependencies:
        if dependency.name == name:
            return dependency
    return None


def _format_preflight_report(report: BatchPreflightReport) -> str:
    """Format a batch preflight report for Mission Control."""
    lines = [
        "Ready to run: " + ("YES" if report.ready else "NO"),
        f"Batch folder: {report.batch_folder}",
        f"Execution mode: {report.execution_mode}; max workers: {report.max_workers}; recommended workers: {report.recommended_workers}",
        f"Files to process: {len(report.files_to_process)}",
        f"Files already completed: {len(report.files_completed)}",
        f"Files to skip: {len(report.files_to_skip)}",
        f"Files to retry: {len(report.files_to_retry)}",
        f"Estimated output storage: {_format_storage(report.estimated_output_bytes)}",
        f"Free disk space: {_format_storage(report.free_disk_bytes)}",
        f"Manifest: {report.manifest_path}",
        "",
        "Blockers:",
    ]
    lines.extend(f"- {item}" for item in report.blockers)
    if not report.blockers:
        lines.append("- None")
    lines.append("")
    lines.append("Warnings:")
    lines.extend(f"- {item}" for item in report.warnings)
    if not report.warnings:
        lines.append("- None")
    return "\n".join(lines)


def _format_storage(value: int) -> str:
    """Return a compact storage label."""
    amount = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024 or unit == "TB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{amount:.1f} TB"


def _next_home_action(environment: str, dataset: str | None, batch_status: str) -> str:
    """Return a concise next action for the Home dashboard."""
    if environment == "Unknown":
        return "open Environment and refresh dependency checks."
    if environment == "NOT READY":
        return "review Environment warnings before processing."
    if "Running" in batch_status:
        return "monitor the Batch page until the current run finishes."
    if not dataset:
        return "start a single dataset workflow or open Batch for multiple files."
    return "build a Product Plan or run selected products from Processing."


def _processing_footprint_text(footprint: ProcessingFootprint) -> str:
    """Return concise user-facing processing footprint text."""
    product_lines = ", ".join(footprint.selected_products) or "none"
    warnings = "\n".join(f"Warning: {item}" for item in footprint.warnings)
    details = [
        f"Processing footprint: {product_lines}",
        f"Output folder: {footprint.output_folder or 'Unknown'}",
        f"Raster dimensions: {footprint.display_dimensions}",
        f"Raster bands: {footprint.total_bands}",
        f"Estimated output storage: {footprint.display_storage} ({footprint.confidence} confidence)",
        footprint.caveat,
    ]
    if warnings:
        details.append(warnings)
    return "\n".join(details)


def _apply_button_role(button: QPushButton, role: str | None = None) -> QPushButton:
    """Apply design-system button role metadata and native action icons."""
    requested = (role or button_role_for_label(button.text())).strip().lower()
    if requested not in {"primary", "secondary", "neutral", "danger"}:
        requested = button_role_for_label(button.text())
    if requested not in {"primary", "secondary", "neutral", "danger"}:
        requested = "secondary"
    button.setProperty("buttonRole", requested)
    _apply_action_icon(button)
    style = button.style()
    if style is not None:
        style.unpolish(button)
        style.polish(button)
    return button


def _apply_action_icon(button: QPushButton) -> None:
    """Prefer QGIS theme icons, then Qt standard icons for important actions."""
    intent = action_icon_intent(button.text())
    if not intent:
        return
    icon = _qgis_theme_icon(intent) or _qt_standard_icon(button, intent)
    if icon is not None and not icon.isNull():
        button.setIcon(icon)
        button.setIconSize(QSize(16, 16))


def _qgis_theme_icon(intent: str):
    """Return a QGIS theme icon when QGIS exposes one for the action intent."""
    candidates = {
        "cancel": ("/mActionCancel.svg", "/mIconClose.svg"),
        "clear": ("/mActionDeleteSelected.svg", "/mIconClearText.svg"),
        "folder": ("/mActionFileOpen.svg", "/mIconFolder.svg"),
        "forward": ("/mActionArrowRight.svg", "/mIconForward.svg"),
        "help": ("/mActionHelpContents.svg", "/mIconHelp.svg"),
        "install": ("/mActionInstallPlugin.svg", "/mIconPlugin.svg"),
        "load": ("/mActionAddRasterLayer.svg", "/mActionAddLayer.svg"),
        "log": ("/mActionOpenTable.svg", "/mIconTableLayer.svg"),
        "open": ("/mActionFileOpen.svg",),
        "preview": ("/mActionShowAllLayers.svg", "/mActionIdentify.svg"),
        "refresh": ("/mActionRefresh.svg",),
        "repair": ("/mActionToggleEditing.svg", "/mIconWarning.svg"),
        "run": ("/mActionStart.svg", "/mIconRun.svg"),
        "save": ("/mActionFileSave.svg",),
        "search": ("/mActionZoomIn.svg", "/mActionIdentify.svg"),
        "select": ("/mActionSelect.svg",),
        "settings": ("/mActionOptions.svg", "/mIconProperties.svg"),
        "verify": ("/mIconSuccess.svg", "/mActionIdentify.svg"),
        "inspect": ("/mActionIdentify.svg",),
    }.get(intent, ())
    try:
        from qgis.core import QgsApplication

        for name in candidates:
            icon = QgsApplication.getThemeIcon(name)
            if icon is not None and not icon.isNull():
                return icon
    except Exception:  # noqa: BLE001 - tests and non-QGIS contexts fall back to Qt icons.
        return None
    return None


def _qt_standard_icon(button: QPushButton, intent: str):
    """Return a Qt standard icon for action intents not covered by QGIS."""
    style = button.style()
    if style is None:
        return None
    pixmap_name = {
        "cancel": "SP_DialogCancelButton",
        "clear": "SP_DialogDiscardButton",
        "folder": "SP_DirOpenIcon",
        "forward": "SP_ArrowForward",
        "help": "SP_DialogHelpButton",
        "install": "SP_DriveHDIcon",
        "load": "SP_FileDialogNewFolder",
        "log": "SP_FileIcon",
        "open": "SP_DialogOpenButton",
        "preview": "SP_FileDialogContentsView",
        "refresh": "SP_BrowserReload",
        "repair": "SP_MessageBoxWarning",
        "run": "SP_MediaPlay",
        "save": "SP_DialogSaveButton",
        "search": "SP_FileDialogContentsView",
        "select": "SP_DialogApplyButton",
        "settings": "SP_FileDialogDetailedView",
        "verify": "SP_DialogApplyButton",
        "inspect": "SP_MessageBoxInformation",
    }.get(intent)
    pixmap = getattr(QStyle, pixmap_name, None) if pixmap_name else None
    return style.standardIcon(pixmap) if pixmap is not None else None


def _set_status_badge(label: QLabel, status: str, text: str | None = None) -> QLabel:
    """Apply design-system status badge metadata for stylesheet selectors."""
    badge = status_badge_label(status)
    label.setObjectName("statusBadge")
    label.setProperty("tone", status_badge_tone(badge))
    label.setWordWrap(True)
    label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
    label.setText(text or f"Status: {badge}")
    style = label.style()
    if style is not None:
        style.unpolish(label)
        style.polish(label)
    return label


def _collapsible_section(parent: QVBoxLayout, title: str, checked: bool = False) -> tuple[QGroupBox, QVBoxLayout]:
    """Add a checkable section whose contents are hidden until expanded."""
    group = QGroupBox(title)
    group.setCheckable(True)
    group.setChecked(checked)
    group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
    layout = QVBoxLayout(group)
    layout.setContentsMargins(*SECTION_MARGINS)
    layout.setSpacing(SECTION_SPACING)
    parent.addWidget(group)
    return group, layout


def _wire_collapsible_group(group: QGroupBox) -> None:
    """Connect and apply visibility for a checkable section's content widgets."""
    _set_collapsible_content_visible(group, group.isChecked())
    group.toggled.connect(lambda checked: _set_collapsible_content_visible(group, checked))


def _set_collapsible_content_visible(group: QGroupBox, visible: bool) -> None:
    layout = group.layout()
    if layout is None:
        return
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.setVisible(visible)
        if child_layout is not None:
            _set_layout_visible(child_layout, visible)


def _set_layout_visible(layout: object, visible: bool) -> None:
    if not hasattr(layout, "count"):
        return
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.setVisible(visible)
        if child_layout is not None:
            _set_layout_visible(child_layout, visible)

def _readable_list() -> QListWidget:
    """Return a list widget tuned for wrapped Advisor recommendation summaries."""
    widget = QListWidget()
    widget.setObjectName("advisorList")
    widget.setWordWrap(True)
    widget.setSpacing(6)
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
    return widget


def _add_advisor_item(widget: QListWidget, text: str, height: int = 58) -> None:
    """Add a wrapped Advisor list item with enough vertical space to read."""
    item = QListWidgetItem(text)
    item.setSizeHint(QSize(0, height))
    widget.addItem(item)


def _body_label(text: str) -> QLabel:
    """Return a readable wrapped Advisor body label."""
    label = QLabel(text)
    label.setObjectName("advisorBodyText")
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
    label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
    return label


def _details_label(text: str) -> QLabel:
    """Return a visually quieter wrapped label for long Advisor detail text."""
    label = _body_label(text)
    label.setObjectName("advisorDetailsText")
    return label


def _advisor_metric_card(title: str, value: str) -> QLabel:
    """Return a large metric card label for the Advisor health summary."""
    label = QLabel(f"<b>{escape(title)}</b><br>{escape(value)}")
    label.setObjectName("advisorMetric")
    label.setWordWrap(True)
    label.setMinimumHeight(SECONDARY_BUTTON_HEIGHT + SPACING_XL)
    label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
    return label


def _product_explanation_card(item: object) -> QFrame:
    """Create a readable product explanation card."""
    frame = QFrame()
    frame.setObjectName("advisorNestedCard")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_MD)
    layout.setSpacing(SPACING_SM)
    title = QLabel(getattr(item, "label"))
    title.setObjectName("advisorCardTitle")
    title.setWordWrap(True)
    layout.addWidget(title)
    summary = _body_label(f"Measures: {getattr(item, 'measures')}")
    layout.addWidget(summary)
    details = _details_label(
        _html_lines(
            (
                f"Use when: {getattr(item, 'use_when')}",
                f"Caution: {getattr(item, 'be_cautious_when')}",
                f"QGIS QA: {getattr(item, 'qgis_inspection')}",
            )
        )
    )
    layout.addWidget(details)
    return frame



def _html_lines(lines: tuple[str, ...] | list[str]) -> str:
    """Format plain lines as simple wrapped rich text for QLabel."""
    return "<br>".join(escape(line) if line else "<br>" for line in lines)


def _stars(value: int) -> str:
    count = max(0, min(5, value))
    return "*" * count + "-" * (5 - count)


def _product_label(product_id: str) -> str:
    for item in PRODUCT_EXPLANATIONS:
        if item.product_id == product_id:
            return item.label
    return product_id


def _product_cards_text() -> str:
    sections = []
    for item in PRODUCT_EXPLANATIONS:
        sections.append(
            f"{item.label}\n"
            f"Measures: {item.measures}\n"
            f"Use when: {item.use_when}\n"
            f"Be cautious when: {item.be_cautious_when}\n"
            f"Inspect in QGIS: {item.qgis_inspection}"
        )
    return "\n\n".join(sections)


def _tool_instruction_text() -> str:
    return "\n\n".join(
        f"{item.tool_name}\nOpen: {item.how_to_open}\nUse for: {item.use_for}"
        for item in QGIS_TOOL_INSTRUCTIONS
    )


def _selected_layer(iface: object | None) -> object | None:
    if iface is None:
        return None
    layer_tree = getattr(iface, "layerTreeView", None)
    if not callable(layer_tree):
        return None
    try:
        view = layer_tree()
        current_layer = getattr(view, "currentLayer", None)
        return current_layer() if callable(current_layer) else None
    except Exception:  # noqa: BLE001 - UI helper must degrade to instructions.
        return None

def _status_icon(status: str) -> str:
    return status_display_word(status)


def _format_bounds(report: DatasetExplorerReport) -> str:
    if report.bounds is None:
        return "Unknown"
    return (
        f"X {report.bounds.min_x:g} to {report.bounds.max_x:g}; "
        f"Y {report.bounds.min_y:g} to {report.bounds.max_y:g}; "
        f"Z {report.bounds.min_z if report.bounds.min_z is not None else 'Unknown'} "
        f"to {report.bounds.max_z if report.bounds.max_z is not None else 'Unknown'}"
    )


def _pipeline_status_icon(status: str) -> str:
    return status_display_word(status)


def _friendly_result_label(path: Path) -> str:
    """Return a friendly label for generated raster outputs."""
    stem = path.stem.lower()
    if "canopy_cover" in stem:
        return "Canopy Cover Output"
    if stem == "pad" or "pad" in stem:
        return "PAD Output"
    if stem == "pai" or "pai" in stem:
        return "PAI Output"
    if stem == "fhd" or "fhd" in stem:
        return "FHD Output"
    if "rumple" in stem:
        return "Rumple Summary"
    if stem == "job_summary":
        return "Final Run Summary" if path.suffix.lower() == ".html" else "Job Summary"
    if stem == "batch_summary":
        return "Batch Summary"
    return "CHM Output"


def _is_friendly_result_path(path: Path) -> bool:
    """Return whether a generated result should be shown as a friendly link."""
    suffix = path.suffix.lower()
    stem = path.stem.lower()
    if suffix in {".tif", ".tiff"}:
        return True
    if suffix == ".csv" and "rumple" in stem:
        return True
    if suffix == ".html" and stem in {"job_summary", "batch_summary"}:
        return True
    if suffix in {".csv", ".json"} and stem == "batch_summary":
        return True
    return False
