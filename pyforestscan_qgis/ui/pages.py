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
from ..core.exceptions import AdapterError
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
from .qgis_footprint import FootprintPreview, add_footprint_layer, preview_from_report, zoom_to_footprint
from .ux_summary import backend_summary_from_environment, button_role_for_label, design_spacing_tokens, empty_state_message, environment_headline, primary_action_label, qgis_fallback_summary, routed_products_summary, status_badge_label, status_badge_tone, workflow_action_labels

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
COMPACT_LIST_HEIGHT = 128
TECHNICAL_DETAIL_HEIGHT = 112


class MissionPage(QWidget):
    """Base class for Mission Control pages with one full-page scroll region."""

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


class HomePage(MissionPage):
    """Mission Control workflow dashboard."""

    startSingleDatasetRequested = pyqtSignal()
    startBatchRequested = pyqtSignal()
    continueLastRequested = pyqtSignal()

    def __init__(self, plugin_version: str, parent: QWidget | None = None) -> None:
        """Create the home dashboard."""
        super().__init__("Home", parent)
        dashboard = self.add_section("Workflow Dashboard")
        self.backend_label = _body_label("Backend status: unknown")
        self.environment_label = _body_label("Environment status: Unknown")
        self.dataset_label = _body_label("Current dataset/batch: None")
        self.output_label = _body_label("Last output folder: None")
        self.next_action_label = QLabel("Next: check backend, then start a dataset or batch workflow.")
        self.next_action_label.setObjectName("advisorMetric")
        self.next_action_label.setWordWrap(True)
        for label in (self.backend_label, self.environment_label, self.dataset_label, self.output_label, self.next_action_label):
            dashboard.addWidget(label)

        single_label, batch_label, continue_label = workflow_action_labels()
        actions = QHBoxLayout()
        self.start_single_button = QPushButton(single_label)
        self.start_single_button.setMinimumHeight(PRIMARY_BUTTON_HEIGHT)
        self.start_single_button.clicked.connect(self.startSingleDatasetRequested.emit)
        _apply_button_role(self.start_single_button, "primary")
        self.start_batch_button = QPushButton(batch_label)
        self.start_batch_button.setMinimumHeight(PRIMARY_BUTTON_HEIGHT)
        self.start_batch_button.clicked.connect(self.startBatchRequested.emit)
        _apply_button_role(self.start_batch_button, "secondary")
        self.continue_last_button = QPushButton(continue_label)
        self.continue_last_button.setMinimumHeight(PRIMARY_BUTTON_HEIGHT)
        self.continue_last_button.setEnabled(False)
        self.continue_last_button.clicked.connect(self.continueLastRequested.emit)
        _apply_button_role(self.continue_last_button, "secondary")
        actions.addWidget(self.start_single_button)
        actions.addWidget(self.start_batch_button)
        actions.addWidget(self.continue_last_button)
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

    def set_summary(self, environment: str, dataset: str | None, project: str | None, batch_status: str = "Not started", recent_run: str | None = None) -> None:
        """Update dashboard labels."""
        current = Path(dataset).name if dataset else ("Batch ready" if batch_status != "Not started" else "None")
        self.backend_label.setText(backend_summary_from_environment(environment))
        self.environment_label.setText(f"Environment status: {environment}")
        self.dataset_label.setText(f"Current dataset/batch: {current}")
        self.output_label.setText(f"Last output folder: {recent_run or 'None'}")
        self.next_action_label.setText(f"Next: {_next_home_action(environment, dataset, batch_status)}")

    def set_workspace(self, workspace: Workspace | None) -> None:
        """Display active workspace status on Home."""
        if workspace is None:
            self.continue_last_button.setEnabled(False)
            return
        session = workspace.session
        self.continue_last_button.setEnabled(True)
        self.dataset_label.setText(f"Current dataset/batch: {Path(session.last_selected_dataset).name if session.last_selected_dataset else workspace.name}")
        self.output_label.setText(f"Last output folder: {session.last_output_folder or workspace.output_root}")
        self.next_action_label.setText(f"Next: {workspace_primary_action(workspace)}")

    def set_continue_available(self, available: bool) -> None:
        """Enable Continue Last Run when a current or recent workspace exists."""
        self.continue_last_button.setEnabled(available)

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
        for label in (self.current_step_label, self.completion_label, self.dataset_label, self.output_label, self.primary_action_label):
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
        controls = self.add_section("Runtime")
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
        _set_status_badge(self.status_label, "NOT CONFIGURED", "Status: NOT CONFIGURED - refresh to check readiness.")
        self.pbm_status_label = _body_label("PBM backend status: not checked")
        self.execution_label = _body_label("Execution backend: not checked")
        self.scope_label = _body_label(routed_products_summary())
        self.next_step_label = _body_label("Recommended next step: refresh environment.")
        for label in (self.status_label, self.pbm_status_label, self.execution_label, self.scope_label, self.next_step_label):
            controls.addWidget(label)

        fallback_group, fallback = _collapsible_section(self.content_layout, "QGIS Python fallback environment", checked=False)
        fallback.addWidget(_details_label("Optional when PBM backend is READY. Expand only for QGIS-Python-only tools or troubleshooting."))
        self.fallback_checks_list = QListWidget()
        fallback.addWidget(self.fallback_checks_list)
        _wire_collapsible_group(fallback_group)

        technical_group, technical = _collapsible_section(self.content_layout, "Technical dependency details", checked=False)
        self.checks_list = QListWidget()
        technical.addWidget(self.checks_list)
        _wire_collapsible_group(technical_group)

    def refresh(self) -> None:
        """Run adapter-backed environment validation."""
        report = self.adapter.check_environment()
        self.set_report(report)

    def set_report(self, report: EnvironmentReport) -> None:
        """Display an environment report."""
        _set_status_badge(self.status_label, report.readiness.value, environment_headline(report.readiness.value))
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
        browse = QPushButton("Browse")
        browse.clicked.connect(self.browse_dataset)
        row.addWidget(self.dataset_path_edit)
        row.addWidget(browse)
        picker.addLayout(row)

        output_row = QHBoxLayout()
        self.output_folder_edit = QLineEdit()
        self.output_folder_edit.setPlaceholderText("Choose output folder")
        output_browse = QPushButton("Browse")
        output_browse.clicked.connect(self.browse_output_folder)
        output_row.addWidget(self.output_folder_edit)
        output_row.addWidget(output_browse)
        picker.addLayout(output_row)

        run = QPushButton(primary_action_label("dataset"))
        run.clicked.connect(self.run_explorer)
        _apply_button_role(run, "primary")
        picker.addWidget(run)

        summary = self.add_section("Dataset Summary")
        self.summary_section = summary.parentWidget()
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMinimumHeight(COMPACT_LIST_HEIGHT)
        summary.addWidget(self.summary_text)
        self.summary_section.setVisible(False)

        metadata_group, metadata = _collapsible_section(self.content_layout, "Technical Metadata", checked=False)
        self.dataset_technical_text = QTextEdit()
        self.dataset_technical_text.setReadOnly(True)
        self.dataset_technical_text.setMinimumHeight(TECHNICAL_DETAIL_HEIGHT)
        self.dataset_technical_text.setPlainText("Dataset technical metadata appears after analysis.")
        metadata.addWidget(self.dataset_technical_text)
        _wire_collapsible_group(metadata_group)

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
            self.dataset_path_edit.setText(path)

    def browse_output_folder(self) -> None:
        """Choose the root output folder for Mission Control runs."""
        path = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if path:
            self.output_folder_edit.setText(path)

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
        self.active_run = context
        self.set_report(report, context)
        self.set_footprint_preview(report, path, context)
        self.datasetExplored.emit(report, path, context)

    def set_report(self, report: DatasetExplorerReport, context: RunContext | None = None) -> None:
        """Display a Dataset Explorer report summary."""
        lines = [
            f"Point count: {format_count_for_display(report.point_count)}",
            f"CRS: {format_crs_for_display(report.crs)}",
            f"Density: {format_density_for_display(report.estimated_density)}",
            f"Bounds: {_format_bounds(report)}",
        ]
        if report.warnings:
            lines.append(f"Warnings: {len(report.warnings)} item(s). Expand Technical Metadata for details.")
        self.summary_text.setPlainText("\n".join(lines))
        technical_lines = []
        if report.dimensions:
            technical_lines.append(f"Dimensions: {', '.join(report.dimensions)}")
        if report.warnings:
            technical_lines.extend(("Warnings:", *[f"- {warning.code}: {warning.message}" for warning in report.warnings], ""))
        if report.products:
            technical_lines.extend(("Available products:", *[f"- {item.label}: {item.status}" for item in report.products], ""))
        if context:
            technical_lines.extend((f"Run folder: {context.run_folder}", f"Dataset Report: {context.dataset_report_html}"))
        self.dataset_technical_text.setPlainText("\n".join(technical_lines).strip() or "No technical metadata warnings.")
        self.summary_section.setVisible(True)

    def _set_dataset_message(self, message: str) -> None:
        """Show a compact Dataset page empty or warning state."""
        self.summary_text.setPlainText(message)
        self.summary_section.setVisible(True)

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
        executive.addWidget(self.executive_summary_label)

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
        self.qgis_tools_summary = _body_label("After processing, inspect generated layers in QGIS Layer Styling and Histogram before publication or interpretation.")
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
                "Next: inspect loaded layers with Layer Styling and Histogram, compare extents/CRS, open the final job summary, and only then prepare layouts or derived analyses."
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
            text = "Start here: build a Product Planner report using the recommended products and parameter notes, then run one small validation workflow before production use."
        self.next_steps_label.setText(text + "\n\nUse QGIS QA tools after processing rather than treating outputs as publication-ready immediately.")


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
        output.addWidget(_body_label("Mission Control normally uses the active run folder automatically. Advanced users can override the output folder before building a plan."))
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

        summary = self.add_section("Run Summary")
        build = QPushButton("Build Plan")
        build.setMinimumHeight(PRIMARY_BUTTON_HEIGHT)
        build.clicked.connect(self.build_plan)
        _apply_button_role(build, "primary")
        summary.addWidget(build)
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
        self.plan_text.setPlainText("Dataset report loaded. Choose products and build a plan.")

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
            self.planningChanged.emit("Needs review", None)
            return
        try:
            if self.run_context is not None:
                write_plan_json(plan, self.run_context.product_plan_json)
                write_plan_csv(plan, self.run_context.product_plan_csv)
                write_plan_html(plan, self.run_context.product_plan_html)
        except OSError as exc:
            self.plan_text.setPlainText(f"Product plan reports could not be written: {exc}")
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
        self.status_label = QLabel()
        _set_status_badge(self.status_label, "NOT CONFIGURED", "Status: NOT CONFIGURED - build a Product Plan first.")
        overview.addWidget(self.selected_products_label)
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
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.cancel_button)
        button_row.addStretch(1)
        overview.addLayout(button_row)

        progress = self.add_section("Current Progress")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress.addWidget(self.progress_bar)
        progress.addWidget(_body_label("All implemented products can run together. Keep QGIS open until the job completes or fails cleanly."))

        technical_group, technical = _collapsible_section(self.content_layout, "Technical Details", checked=False)
        technical.addWidget(_details_label("Run files, Product Planner JSON paths, pipeline stages, and logs are shown here for troubleshooting and reproducibility."))
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

    def set_run_context(self, context: RunContext | None) -> None:
        """Use the active Mission Control run context."""
        self.run_context = context
        if context is None:
            self.current_plan_label.setText("Product plan file: none")
            self.selected_products_label.setText("Selected products: build a Product Plan first.")
            self.current_output_label.setText("Outputs: choose a dataset and output folder, then build a Product Plan.")
            self.footprint_label.setText("Processing footprint: build a Product Plan to see expected outputs, raster size, bands, and storage.")
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
            _set_status_badge(self.status_label, "WARNING", "Status: WARNING - build a product plan before starting.")
            self.log_text.setPlainText("Build a product plan before starting a processing job.")
            return
        if not Path(plan_path).exists():
            _set_status_badge(self.status_label, "WARNING", "Status: WARNING - build a product plan before starting.")
            self.log_text.setPlainText("Build a product plan before starting a processing job.")
            return
        if not output_folder:
            _set_status_badge(self.status_label, "WARNING", "Status: WARNING - choose an output folder before starting.")
            self.log_text.setPlainText("Choose an output folder for the job summary JSON.")
            return
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
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
            _set_status_badge(self.status_label, "FAILED", f"Status: FAILED - processing job could not start: {exc}")
            self.log_text.setPlainText(f"Processing job could not start: {exc}")
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
        _set_status_badge(self.status_label, job.status.value, f"Status: {status_badge_label(job.status.value)} - {job.status.value}")
        self.progress_bar.setValue(int(job.progress.percent))
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
        self.load_outputs_check.setToolTip("Off by default for batches so QGIS is not overwhelmed by many layers.")
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
        _set_status_badge(self.status_label, "NOT CONFIGURED", "Status: NOT CONFIGURED - discover files and run preflight.")
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
            _set_status_badge(self.status_label, "WARNING", "Status: WARNING - choose an input folder before discovery.")
            return
        try:
            datasets = discover_lidar_files(folder, self.recursive_check.isChecked())
        except ValueError as exc:
            _set_status_badge(self.status_label, "FAILED", f"Status: FAILED - discovery failed: {exc}")
            return
        self.discovered_paths = [item.path for item in datasets]
        self.file_list.clear()
        for item in datasets:
            row = QListWidgetItem(f"{item.path.name}\nStatus: {item.status}; bounds: {item.bounds_summary}\n{item.path}")
            row.setFlags(row.flags() | Qt.ItemIsUserCheckable)
            row.setCheckState(Qt.Checked if item.selected else Qt.Unchecked)
            row.setSizeHint(QSize(0, 72))
            self.file_list.addItem(row)
        _set_status_badge(self.status_label, "READY", f"Status: READY - discovered {len(datasets)} supported dataset(s).")
        self._refresh_footprint_label()

    def run_preflight(self) -> None:
        """Run batch preflight and update readiness display."""
        try:
            request = self._build_batch_request()
        except BatchExecutionError as exc:
            self.preflight_text.setPlainText(f"BLOCKER: {exc}")
            self.preflight_report = None
            self._update_run_button_enabled()
            return
        report = run_batch_preflight(request, adapter=self.adapter)
        self.preflight_report = report
        self.preflight_text.setPlainText(_format_preflight_report(report))
        self.acknowledge_warnings_check.setEnabled(report.has_warnings and not report.blockers)
        if not report.has_warnings:
            self.acknowledge_warnings_check.setChecked(False)
        self._update_run_button_enabled()

    def run_batch(self) -> None:
        """Run selected datasets through preflight-approved batch execution."""
        if self.preflight_report is None:
            _set_status_badge(self.status_label, "WARNING", "Status: WARNING - run preflight before starting the batch.")
            return
        if self.preflight_report.blockers:
            _set_status_badge(self.status_label, "FAILED", "Status: FAILED - preflight blockers must be resolved before running.")
            return
        if self.preflight_report.warnings and not self.acknowledge_warnings_check.isChecked():
            _set_status_badge(self.status_label, "WARNING", "Status: WARNING - review and acknowledge preflight warnings before running.")
            return
        try:
            request = self._build_batch_request(self.preflight_report.batch_folder, self.preflight_report.files_to_process)
        except BatchExecutionError as exc:
            _set_status_badge(self.status_label, "FAILED", f"Status: FAILED - batch could not start: {exc}")
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
        _set_status_badge(self.status_label, "RUNNING", f"Status: RUNNING - {len(selected)} dataset(s).")
        self._processed_items = 0
        self._total_items = max(1, len(selected) + len(self.preflight_report.files_to_skip))
        executor = BatchExecutor(adapter_factory=PyForestScanAdapter)
        try:
            guardrail = executor.guardrails(request)
        except BatchExecutionError as exc:
            _set_status_badge(self.status_label, "FAILED", f"Status: FAILED - batch could not start: {exc}")
            self._finish_batch_run()
            return
        self.active_workers = guardrail.max_workers if guardrail.is_parallel else 1
        mode_label = guardrail.effective_mode.replace("_", " ")
        self.worker_status_label.setText(f"Active workers: {self.active_workers} ({mode_label})")
        backend_label = PyForestScanAdapter().selected_execution_backend().replace("_", " ")
        _set_status_badge(self.status_label, "RUNNING", f"Status: RUNNING - {len(selected)} dataset(s) in {mode_label}. Execution backend: {backend_label}.")
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
            f"Status: {completion_badge} - batch complete. Completed {getattr(result, 'success_count', 0)}; failed {getattr(result, 'failure_count', 0)}. Summary: {getattr(result, 'summary_html', '')}",
        )
        self._set_batch_summary(result)
        self.open_batch_folder_button.setEnabled(True)
        self.retry_failed_button.setEnabled(bool(self.failed_paths))
        self.batchCompleted.emit(result)
        self._finish_batch_run()

    def _on_batch_failed(self, message: str) -> None:
        """Display an executor-level batch failure."""
        _set_status_badge(self.status_label, "FAILED", f"Status: FAILED - batch could not start: {message}")
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
        _set_status_badge(self.status_label, "RUNNING", f"Status: RUNNING - {self._processed_items}/{total} dataset(s) processed.")
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
        _set_status_badge(self.status_label, "RUNNING", "Status: RUNNING - batch will pause after the current file." if self.pause_requested else "Status: RUNNING - batch resumed.")

    def cancel_remaining(self) -> None:
        """Cancel files that have not started yet."""
        self.cancel_requested = True
        self.pause_requested = False
        self.pause_button.setText("Pause After Current File")
        _set_status_badge(self.status_label, "RUNNING", "Status: RUNNING - cancelling remaining files after the current file.")

    def retry_failed_files(self) -> None:
        """Retry failed files from the last batch with current settings."""
        if not self.failed_paths:
            _set_status_badge(self.status_label, "WARNING", "Status: WARNING - no failed files are available to retry.")
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
        _set_status_badge(self.status_label, "WARNING", "Status: WARNING - failed files are queued for retry. Click Run Batch.")
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

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the results page."""
        super().__init__("Results", parent)
        self._friendly_paths: list[Path] = []
        self._advanced_paths: list[Path] = []
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
        self.load_outputs_button.setToolTip("Select an output link, then load/open it for review.")
        self.load_outputs_button.clicked.connect(self.open_selected_link)
        _apply_button_role(self.load_outputs_button, "secondary")
        self.clear_current_run_button = QPushButton("Clear Current Run")
        self.clear_current_run_button.setEnabled(False)
        self.clear_current_run_button.clicked.connect(self.clear_current_run)
        _apply_button_role(self.clear_current_run_button, "danger")
        button_row.addWidget(self.open_output_folder_button)
        button_row.addWidget(self.load_outputs_button)
        button_row.addWidget(self.clear_current_run_button)
        button_row.addStretch(1)
        links.addLayout(button_row)

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

    def set_run_context(self, context: RunContext | None) -> None:
        """Display friendly run links for the active context."""
        self.friendly_links.clear()
        self.previous_reports.clear()
        self._friendly_paths = []
        self._advanced_paths = []
        self._current_output_folder = None
        self.open_output_folder_button.setEnabled(False)
        self.load_outputs_button.setEnabled(False)
        self.clear_current_run_button.setEnabled(False)
        self.friendly_links.setVisible(False)
        self.results_empty_label.setVisible(True)
        if context is None:
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
        self.jobs_section.setVisible(bool(jobs))
        for job in jobs:
            detail = f"{job.title} - {job.status.value} - {job.progress.percent:.0f}%"
            if job.results:
                detail = f"{detail} - {job.results[-1].path}"
            self.job_history.addItem(detail)

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
        self._current_output_folder = None
        self.open_output_folder_button.setEnabled(False)
        self.load_outputs_button.setEnabled(False)
        self.clear_current_run_button.setEnabled(False)
        self.friendly_links.setVisible(False)
        self.results_empty_label.setVisible(True)
        self.jobs_section.setVisible(False)

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

        backend = self.add_section("PyForestScan Backend Manager")
        backend.addWidget(_body_label("Windows internal beta builds can install a user-local backend. PBM does not modify QGIS Python, the QGIS installation, system Python, PATH, or user environment variables."))
        self.backend_service = BackendService()
        self.backend_install_running = False
        self.backend_install_thread: QThread | None = None
        self.backend_install_worker: _BackendInstallWorker | None = None
        self.backend_install_started_at: float | None = None
        self.backend_install_timer = QTimer(self)
        self.backend_install_timer.setInterval(1000)
        self.backend_install_timer.timeout.connect(self._refresh_backend_install_elapsed)
        self.backend_status_label = _body_label("")
        _set_status_badge(self.backend_status_label, "NOT CONFIGURED", "Backend Status: NOT CONFIGURED - verify backend.")
        self.backend_location_label = _body_label("Backend Location: Unknown")
        self.backend_environment_label = _body_label("Environment Location: Unknown")
        self.backend_installed_version_label = _body_label("Installed Version: Not installed")
        self.backend_plugin_version_label = _body_label("Plugin Version: Unknown")
        self.backend_manifest_version_label = _body_label("Manifest Version: Unknown")
        self.backend_python_label = _body_label("Python Version: Not detected")
        self.backend_pdal_label = _body_label("PDAL Version: Not detected")
        self.backend_dependency_label = _body_label("Dependency summary: Not verified")
        self.zip_install_ready_label = _body_label("ZIP install ready: pending clean-machine smoke test")
        self.backend_auto_install_ready_label = _body_label("Backend auto-install ready: No")
        self.manual_dependency_setup_label = _body_label("Manual dependency setup required: Yes, unless QGIS Python already has required dependencies")
        self.qgis_compatibility_label = _body_label("QGIS Compatibility: Not checked")
        self.backend_install_readiness_label = _body_label("Install readiness: Platform check pending")
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
        self.backend_install_stage_label = _body_label("Install stage: Not running")
        self.backend_install_action_label = _body_label("Current package/action: None")
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
        self.backend_details.setPlainText("Verify or install PBM from this page. Advanced reports and logs stay under Advanced / Troubleshooting.")
        backend.addWidget(self.backend_details)
        self.backend_technical_log_group = QGroupBox("Advanced / Troubleshooting: technical log")
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
        _set_status_badge(self.backend_status_label, state.status.value, f"Backend Status: {status_badge_label(state.status.value)} - {state.message}")
        self.backend_location_label.setText(f"Storage Location: {paths.backend_root}")
        self.backend_environment_label.setText(f"Environment Location: {paths.environment_path}")
        self.backend_installed_version_label.setText(f"Installed Version: {'configured' if state.config_exists else 'Not installed'}")
        self.backend_plugin_version_label.setText(f"Plugin Version: {self.backend_service.plugin_version}")
        self.backend_manifest_version_label.setText(f"Manifest Version: {manifest.backend_version if manifest else 'Unavailable'}")
        required_count = len(registry.required_dependencies())
        total_count = len(registry.dependencies)
        self.backend_dependency_label.setText(f"Dependencies: {required_count} required, {total_count - required_count} optional/future")
        self.zip_install_ready_label.setText("ZIP install ready: yes for plugin loading; clean Windows/QGIS smoke test still required before broad distribution")
        auto_ready = "yes, Windows internal beta" if availability.enabled else f"no; {availability.reason}"
        self.backend_auto_install_ready_label.setText(f"Backend auto-install ready: {auto_ready}")
        if state.status.value == "Ready":
            manual_text = "Manual dependency setup required: no for backend verification; processing integration is reported per workflow"
        else:
            manual_text = "Manual dependency setup required: no after a successful PBM install; workflows not routed through PBM still require QGIS Python dependencies"
        self.manual_dependency_setup_label.setText(manual_text)
        compat_text = version.message if version else "Manifest unavailable"
        self.qgis_compatibility_label.setText(f"Compatibility: QGIS {compatibility.summary()}; backend {compat_text}")
        self.backend_install_readiness_label.setText(f"Install readiness: {availability.reason}; manifest includes {len(plan.required_package_names())} packages")
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
            "Advanced install plans, module registry, and logs are available from Preview Install, Advanced, or View Logs."
        )

    def verify_backend(self) -> None:
        """Run safe PBM verification and display dependency results."""
        result = self.backend_service.verify_backend()
        _set_status_badge(self.backend_status_label, result.status.value, f"Backend Status: {status_badge_label(result.status.value)}")
        python_dependency = _find_backend_dependency(result, "python")
        pdal_dependency = _find_backend_dependency(result, "pdal")
        self.backend_python_label.setText(f"Python Version: {python_dependency.detected_version if python_dependency and python_dependency.detected_version else 'Not detected'}")
        self.backend_pdal_label.setText(f"PDAL Version: {pdal_dependency.detected_version if pdal_dependency and pdal_dependency.detected_version else 'Not detected'}")
        required = result.registry.required_dependencies()
        verified_required = sum(1 for dependency in required if dependency.verification_status.value == "pass")
        self.backend_dependency_label.setText(f"Dependency summary: {verified_required}/{len(required)} required dependencies verified")
        self.backend_details.setPlainText(self.backend_service.format_verification_report(result))

    def verify_qgis_compatibility(self) -> None:
        """Display defensive QGIS compatibility details."""
        report = build_qgis_compatibility_report()
        self.qgis_compatibility_label.setText(f"QGIS Compatibility: {report.summary()}")
        self.backend_details.setPlainText(format_qgis_compatibility_report(report))

    def preview_install_plan(self) -> None:
        """Display the dry-run backend installation plan."""
        plan = self.backend_service.preview_install_plan()
        availability = self.backend_service.install_availability()
        self.backend_install_readiness_label.setText(f"Install readiness: {availability.reason}; manifest includes {len(plan.required_package_names())} packages")
        self.backend_details.setPlainText(self.backend_service.format_install_plan(plan))

    def install_backend_internal_beta(self) -> None:
        """Confirm and run the Windows internal beta backend installer."""
        availability = self.backend_service.install_availability()
        if not availability.enabled:
            self.backend_details.setPlainText(f"Install Backend is not available on this platform/build.\n\n{availability.reason}")
            return
        message = (
            "This will install PyForestScan backend packages into your user-local PyForestScan folder. "
            "It will not modify QGIS or system Python.\n\n"
            f"Backend folder: {self.backend_service.paths.backend_root}\n"
            "The installer downloads Micromamba, creates a managed environment, verifies imports/executables, and writes PBM config only under that folder."
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
            _set_status_badge(self.backend_status_label, "RUNNING", "Backend Status: RUNNING - installation in progress.")
            self.backend_install_progress_bar.setValue(5)
            self.backend_install_stage_label.setText("Install stage: Preparing")
            self.backend_install_action_label.setText("Current package/action: staging")
            self.backend_install_message_label.setText("Latest message: Installation is running. Please wait for this step to finish.")
            self.backend_install_estimate_label.setText("Step progress is estimated.")
            self.backend_details.setPlainText(
                "Backend installation is running in the background.\n\n"
                "Installation is running. Please wait for this step to finish.\n"
                "Step progress is estimated. Technical logs are hidden under Advanced / Troubleshooting."
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
        self.backend_install_stage_label.setText(f"Install stage: {stage}")
        self.backend_install_action_label.setText(f"Current package/action: {current}")
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
        _set_status_badge(self.backend_status_label, final_state, f"Backend Status: {status_badge_label(final_state)} - {final_state}")
        self.backend_install_stage_label.setText(f"Install stage: {final_state}")
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
            "Use Repair if installation failed. Technical logs are available under Advanced / Troubleshooting or View Logs."
        )
        self._refresh_backend_technical_log()

    def _on_backend_install_failed(self, message: str) -> None:
        """Display unexpected installer worker failure."""
        self._set_backend_install_running(False)
        self._set_backend_progress_visible(True)
        _set_status_badge(self.backend_status_label, "FAILED", "Backend Status: FAILED - install failed.")
        self.backend_install_stage_label.setText("Install stage: Install Failed")
        self.backend_install_message_label.setText(f"Latest message: {message}")
        self.backend_details.setPlainText(
            "PBM Backend Install Result\n\n"
            "Final state: Install Failed\n"
            f"Message: {message}\n\n"
            "Use View Logs for details. Technical logs are hidden under Advanced / Troubleshooting."
        )
        self._refresh_backend_technical_log()

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
        _set_status_badge(self.backend_status_label, result.status.value, f"Backend Status: {status_badge_label(result.status.value)}")
        self.backend_details.setPlainText(self.backend_service.format_repair_plan(plan))

    def show_backend_advanced(self) -> None:
        """Display advanced PBM architecture details."""
        modules = self.backend_service.module_registry()
        manifest = self.backend_service.backend_manifest()
        version = self.backend_service.version_compatibility()
        lines = [
            "PBM Advanced",
            f"Internal beta install: {'enabled' if self.backend_service.backend_install_enabled() else 'off'}",
            f"Manifest backend version: {manifest.backend_version if manifest else 'Unavailable'}",
            f"Manifest environment version: {manifest.environment_version if manifest else 'Unavailable'}",
            f"Version compatibility: {version.message if version else 'Unavailable'}",
            "",
            "Structured logs:",
            f"- Install: {self.backend_service.paths.install_log}",
            f"- Download: {self.backend_service.paths.download_log}",
            f"- Verify: {self.backend_service.paths.verify_log}",
            f"- Repair: {self.backend_service.paths.repair_log}",
            "",
            "Future modules:",
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
            "- ZIP install ready: yes for plugin loading and diagnostics; clean Windows/QGIS smoke testing remains required before broad distribution.\n"
            "- Backend auto-install ready: yes for Windows internal beta builds after confirmation.\n"
            "- Manual dependency setup required: no after PBM backend installation verifies successfully; workflows not routed through PBM still report QGIS Python requirements clearly.\n\n"
            "Next steps:\n"
            "1. Install the ZIP through QGIS Plugin Manager.\n"
            "2. Open Mission Control and run Environment Check.\n"
            "3. Open Backend settings and click Install Backend on Windows internal beta builds.\n"
            "4. Verify Backend until status is Ready before trying Guided, Advanced, or Batch workflows.\n\n"
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
                "Windows internal beta installation will create only this user-local directory after confirmation. "
                "Use Preview Install to review the manifest-driven backend layout before installing."
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
    """Apply design-system button role metadata for stylesheet selectors."""
    requested = (role or button_role_for_label(button.text())).strip().lower()
    if requested not in {"primary", "secondary", "neutral", "danger"}:
        requested = button_role_for_label(button.text())
    if requested not in {"primary", "secondary", "neutral", "danger"}:
        requested = "secondary"
    button.setProperty("buttonRole", requested)
    style = button.style()
    if style is not None:
        style.unpolish(button)
        style.polish(button)
    return button


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
    if status == CheckStatus.PASS.value:
        return "PASS"
    if status == CheckStatus.FAIL.value:
        return "FAIL"
    return "WARN"


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
    if status == "passed":
        return "PASS"
    if status == "warning":
        return "WARN"
    if status == "failed":
        return "FAIL"
    if status == "skipped":
        return "TODO"
    if status == "not_implemented":
        return "TODO"
    return "WAIT"


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
