"""Mission Control page widgets.

These widgets orchestrate existing adapter-backed workflows. They do not call
PyForestScan directly and do not create scientific products.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from qgis.PyQt.QtCore import QUrl, pyqtSignal
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.adapter import PyForestScanAdapter
from ..core.dataset_report import (
    DatasetExplorerReport,
    build_dataset_explorer_report,
    format_count_for_display,
    format_crs_for_display,
    format_density_for_display,
    report_to_dict,
)
from ..core.dependency_check import CheckStatus, EnvironmentReport
from ..core.exceptions import AdapterError
from ..core.product_plan import (
    PRODUCT_LABELS,
    ProductPlanError,
    ProductPlannerReport,
    ProductPlannerRequest,
    build_product_plan,
)
from ..core.types import ProductType

ActivityCallback = Callable[[str, str], None]


class MissionPage(QWidget):
    """Base class for Mission Control pages."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        """Create a page with a title and scrollable content."""
        super().__init__(parent)
        self.title = title
        self.main_layout = QVBoxLayout(self)
        heading = QLabel(title)
        heading.setObjectName("pageHeading")
        self.main_layout.addWidget(heading)
        self.content_layout = QVBoxLayout()
        self.main_layout.addLayout(self.content_layout)
        self.main_layout.addStretch(1)

    def add_section(self, title: str) -> QVBoxLayout:
        """Add a titled section and return its layout."""
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        self.content_layout.addWidget(group)
        return layout


class HomePage(MissionPage):
    """Mission Control home page."""

    openDocumentationRequested = pyqtSignal()

    def __init__(self, plugin_version: str, parent: QWidget | None = None) -> None:
        """Create the home page."""
        super().__init__("Home", parent)
        summary = self.add_section("Project")
        self.plugin_version_label = QLabel(f"Plugin version: {plugin_version}")
        self.pyforestscan_version_label = QLabel("PyForestScan version: Unknown")
        self.environment_label = QLabel("Environment: Unknown")
        self.dataset_label = QLabel("Latest dataset: None")
        self.project_label = QLabel("Latest project: None")
        for widget in (
            self.plugin_version_label,
            self.pyforestscan_version_label,
            self.environment_label,
            self.dataset_label,
            self.project_label,
        ):
            summary.addWidget(widget)

        quick = self.add_section("Quick Start")
        quick.addWidget(QLabel("1. Check the environment.\n2. Inspect a dataset.\n3. Plan products.\n4. Return when scientific processing is available."))
        docs = QPushButton("Open Documentation")
        docs.clicked.connect(self.openDocumentationRequested.emit)
        quick.addWidget(docs)

        activity = self.add_section("Recent Activity")
        self.activity_list = QListWidget()
        activity.addWidget(self.activity_list)

    def set_versions(self, pyforestscan_version: str | None) -> None:
        """Update version labels."""
        self.pyforestscan_version_label.setText(f"PyForestScan version: {pyforestscan_version or 'Unknown'}")

    def set_summary(self, environment: str, dataset: str | None, project: str | None) -> None:
        """Update home summary labels."""
        self.environment_label.setText(f"Environment: {environment}")
        self.dataset_label.setText(f"Latest dataset: {dataset or 'None'}")
        self.project_label.setText(f"Latest project: {project or 'None'}")

    def set_activities(self, activities: tuple[tuple[str, str], ...]) -> None:
        """Display recent activity."""
        self.activity_list.clear()
        for label, detail in activities:
            self.activity_list.addItem(f"{label}: {detail}" if detail else label)


class EnvironmentPage(MissionPage):
    """Environment diagnostics page."""

    environmentChanged = pyqtSignal(str)

    def __init__(self, adapter: PyForestScanAdapter, parent: QWidget | None = None) -> None:
        """Create the environment page."""
        super().__init__("Environment", parent)
        self.adapter = adapter
        controls = self.add_section("Runtime")
        self.refresh_button = QPushButton("Refresh Environment")
        self.refresh_button.clicked.connect(self.refresh)
        controls.addWidget(self.refresh_button)
        self.status_label = QLabel("Status: Unknown")
        controls.addWidget(self.status_label)
        self.checks_list = QListWidget()
        controls.addWidget(self.checks_list)

    def refresh(self) -> None:
        """Run adapter-backed environment validation."""
        report = self.adapter.check_environment()
        self.set_report(report)

    def set_report(self, report: EnvironmentReport) -> None:
        """Display an environment report."""
        self.status_label.setText(f"Status: {report.readiness.value}")
        self.checks_list.clear()
        for check in report.checks:
            icon = _status_icon(check.status.value)
            version = f" ({check.version})" if check.version else ""
            self.checks_list.addItem(f"{icon} {check.name}{version}: {check.message}")
        self.environmentChanged.emit(report.readiness.value)


class DatasetPage(MissionPage):
    """Dataset inspection page."""

    datasetExplored = pyqtSignal(object, str)

    def __init__(self, adapter: PyForestScanAdapter, parent: QWidget | None = None) -> None:
        """Create the dataset page."""
        super().__init__("Dataset", parent)
        self.adapter = adapter
        picker = self.add_section("Dataset")
        row = QHBoxLayout()
        self.dataset_path_edit = QLineEdit()
        self.dataset_path_edit.setPlaceholderText("Choose LAS, LAZ, COPC, or ept.json")
        browse = QPushButton("Browse")
        browse.clicked.connect(self.browse_dataset)
        row.addWidget(self.dataset_path_edit)
        row.addWidget(browse)
        picker.addLayout(row)
        run = QPushButton("Run Dataset Explorer")
        run.clicked.connect(self.run_explorer)
        picker.addWidget(run)

        summary = self.add_section("Summary")
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        summary.addWidget(self.summary_text)

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

    def run_explorer(self) -> None:
        """Run adapter-backed dataset inspection without writing outputs."""
        path = self.dataset_path_edit.text().strip()
        if not path:
            self.summary_text.setPlainText("Choose a dataset before running Dataset Explorer.")
            return
        try:
            inspection = self.adapter.inspect_dataset(path)
            report = build_dataset_explorer_report(inspection)
        except AdapterError as exc:
            self.summary_text.setPlainText(f"Dataset inspection failed: {exc}")
            return
        self.set_report(report)
        self.datasetExplored.emit(report, path)

    def set_report(self, report: DatasetExplorerReport) -> None:
        """Display a Dataset Explorer report summary."""
        products = "\n".join(f"- {item.label}: {item.status}" for item in report.products)
        warnings = "\n".join(f"- {warning.code}: {warning.message}" for warning in report.warnings) or "None"
        text = (
            f"Point count: {format_count_for_display(report.point_count)}\n"
            f"CRS: {format_crs_for_display(report.crs)}\n"
            f"Density: {format_density_for_display(report.estimated_density)}\n"
            f"Bounds: {_format_bounds(report)}\n"
            f"Dimensions: {', '.join(report.dimensions) or 'None reported'}\n\n"
            f"Warnings:\n{warnings}\n\n"
            f"Available products:\n{products}"
        )
        self.summary_text.setPlainText(text)


class PlanningPage(MissionPage):
    """Product planning page."""

    planningChanged = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the planning page."""
        super().__init__("Planning", parent)
        self.dataset_report: DatasetExplorerReport | None = None
        controls = self.add_section("Product Planner")
        self.product_checks: dict[ProductType, QCheckBox] = {}
        for product, label in PRODUCT_LABELS.items():
            check = QCheckBox(label)
            if product is ProductType.CHM:
                check.setChecked(True)
            self.product_checks[product] = check
            controls.addWidget(check)
        form = QFormLayout()
        self.resolution_spin = QDoubleSpinBox()
        self.resolution_spin.setDecimals(3)
        self.resolution_spin.setMinimum(0.01)
        self.resolution_spin.setValue(1.0)
        self.height_bin_spin = QDoubleSpinBox()
        self.height_bin_spin.setDecimals(3)
        self.height_bin_spin.setMinimum(0.0)
        self.height_bin_spin.setSpecialValueText("Not specified")
        self.height_bin_spin.setValue(1.0)
        self.output_folder_edit = QLineEdit()
        folder_button = QPushButton("Browse")
        folder_button.clicked.connect(self.browse_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.output_folder_edit)
        folder_row.addWidget(folder_button)
        form.addRow("Grid resolution", self.resolution_spin)
        form.addRow("Height bin size", self.height_bin_spin)
        form.addRow("Output folder", folder_row)
        controls.addLayout(form)
        build = QPushButton("Build Plan")
        build.clicked.connect(self.build_plan)
        controls.addWidget(build)

        summary = self.add_section("Plan Summary")
        self.plan_text = QTextEdit()
        self.plan_text.setReadOnly(True)
        summary.addWidget(self.plan_text)

    def set_dataset_report(self, report: DatasetExplorerReport) -> None:
        """Store latest Dataset Explorer report for planning."""
        self.dataset_report = report
        self.plan_text.setPlainText("Dataset report loaded. Choose products and build a plan.")

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
        output_folder = Path(self.output_folder_edit.text().strip() or "planned_outputs")
        height_bin_size = self.height_bin_spin.value() if self.height_bin_spin.value() > 0 else None
        request = ProductPlannerRequest(
            explorer_report_path=Path("mission_control_dataset_report.json"),
            requested_products=selected,
            output_folder=output_folder,
            grid_resolution=self.resolution_spin.value(),
            height_bin_size=height_bin_size,
            title="Mission Control Product Plan",
        )
        try:
            plan = build_product_plan(report_to_dict(self.dataset_report), request)
        except ProductPlanError as exc:
            self.plan_text.setPlainText(f"Product plan failed: {exc}")
            self.planningChanged.emit("Needs review")
            return
        ready = sum(1 for product in plan.products if product.plan_status == "Ready")
        review = sum(1 for product in plan.products if product.plan_status == "Needs review")
        blocked = sum(1 for product in plan.products if product.plan_status == "Blocked")
        lines = [
            f"Ready: {ready}",
            f"Needs review: {review}",
            f"Blocked: {blocked}",
            f"Estimated cells: {plan.estimated_cells if plan.estimated_cells is not None else 'Unknown'}",
            "Estimated runtime: Not available until scientific processing is implemented.",
            "Estimated storage: Not available until product writers are implemented.",
            "",
        ]
        lines.extend(f"- {item.label}: {item.plan_status}" for item in plan.products)
        self.plan_text.setPlainText("\n".join(lines))
        self.planningChanged.emit("Ready" if blocked == 0 else "Needs review")


class ProcessingPage(MissionPage):
    """Future scientific processing placeholder page."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the processing placeholder page."""
        super().__init__("Processing", parent)
        section = self.add_section("Phase 7")
        section.addWidget(QLabel("Scientific processing will appear here in Phase 7."))


class ResultsPage(MissionPage):
    """Results placeholder and report opener page."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the results page."""
        super().__init__("Results", parent)
        reports = self.add_section("Reports")
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
        reports.addLayout(row)
        self.previous_reports = QListWidget()
        reports.addWidget(self.previous_reports)
        reports.addWidget(QLabel("Previous reports can be opened here. Full result management is a future phase."))

    def browse_report(self) -> None:
        """Choose a report file."""
        path, _ = QFileDialog.getOpenFileName(self, "Choose report", "", "Reports (*.json *.csv *.html);;All files (*.*)")
        if path:
            self.report_path_edit.setText(path)
            self.previous_reports.addItem(path)

    def set_report_paths(self, paths: tuple[Path, ...]) -> None:
        """Display recently recorded report paths."""
        self.previous_reports.clear()
        for path in paths:
            self.previous_reports.addItem(str(path))

    def open_report(self) -> None:
        """Open the selected report with the desktop handler."""
        path = self.report_path_edit.text().strip()
        if not path and self.previous_reports.currentItem() is not None:
            path = self.previous_reports.currentItem().text()
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))


class SettingsPage(MissionPage):
    """Plugin settings placeholder page."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the settings page."""
        super().__init__("Settings", parent)
        defaults = self.add_section("Defaults")
        form = QFormLayout()
        self.default_output_folder = QLineEdit()
        self.logging_enabled = QCheckBox("Enable workflow logging when implemented")
        form.addRow("Default output folder", self.default_output_folder)
        form.addRow("Logging", self.logging_enabled)
        defaults.addLayout(form)
        defaults.addWidget(QLabel("Settings are placeholders for future persistent preferences."))


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
