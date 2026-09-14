"""Processing algorithms for the PyForestScan provider.

Environment Check remains registered in the Processing Toolbox. The guided
Dataset Explorer and Product Planner classes are retained for compatibility with
older imports, but Mission Control owns those user workflows.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingOutputString,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon

from ..core.adapter import PyForestScanAdapter
from ..core.dataset_report import (
    DatasetExplorerReport,
    build_dataset_explorer_report,
    format_count_for_display,
    format_crs_for_display,
    format_density_for_display,
    render_json_report,
    write_csv_summary,
    write_html_report,
    write_json_report,
)
from ..core.dependency_check import (
    CheckStatus,
    collect_environment_report,
    format_environment_report,
)
from ..core.exceptions import AdapterError
from ..core.product_plan import (
    PRODUCT_LABELS,
    ProductPlanError,
    ProductPlannerReport,
    ProductPlannerRequest,
    build_product_plan,
    load_dataset_explorer_json,
    render_plan_json,
    write_plan_csv,
    write_plan_html,
    write_plan_json,
)
from ..core.types import ProductType
from ..resources import plugin_icon, plugin_root


NOT_IMPLEMENTED_MESSAGE = "Not yet implemented."


class PyForestScanAlgorithm(QgsProcessingAlgorithm):
    """Base class for PyForestScan Processing algorithms."""

    OUTPUT_MESSAGE = "OUTPUT_MESSAGE"

    def tr(self, text: str) -> str:
        """Translate user-facing Processing text."""
        return QCoreApplication.translate("PyForestScan", text)

    def group(self) -> str:
        """Return the Processing group display name."""
        return self.tr("PyForestScan")

    def groupId(self) -> str:
        """Return the stable Processing group identifier."""
        return "pyforestscan"

    def icon(self) -> QIcon:
        """Return the algorithm icon."""
        return plugin_icon()


class PlaceholderAlgorithm(PyForestScanAlgorithm):
    """Base class for unregistered compatibility algorithms."""

    def shortHelpString(self) -> str:
        """Return Processing help text for unregistered compatibility algorithms."""
        return self.tr(
            "This compatibility algorithm is not registered in the current "
            "Processing Toolbox. Use Mission Control or the expert PyForestScan "
            "toolbox groups for active workflows."
        )

    def createInstance(self) -> "PlaceholderAlgorithm":
        """Create a new instance for the QGIS Processing registry."""
        return self.__class__()

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, str]:
        """Report compatibility status and return a successful Processing result."""
        if feedback.isCanceled():
            raise QgsProcessingException(self.tr("Processing was canceled."))

        feedback.pushInfo(self.tr(NOT_IMPLEMENTED_MESSAGE))
        feedback.setProgress(100)
        return {self.OUTPUT_MESSAGE: NOT_IMPLEMENTED_MESSAGE}


class EnvironmentCheckAlgorithm(PyForestScanAlgorithm):
    """Validate the active QGIS Python environment for PyForestScan QGIS."""

    CHECK_PYFORESTSCAN = "CHECK_PYFORESTSCAN"
    CHECK_QGIS = "CHECK_QGIS"
    REPORT_FILE = "REPORT_FILE"

    def name(self) -> str:
        """Return the stable algorithm identifier."""
        return "environment_check"

    def displayName(self) -> str:
        """Return the Processing display name."""
        return self.tr("Environment Check")

    def group(self) -> str:
        """Return the Processing group display name."""
        return self.tr("PyForestScan / Diagnostics")

    def groupId(self) -> str:
        """Return the stable Processing group identifier."""
        return "pyforestscan_diagnostics"

    def shortHelpString(self) -> str:
        """Return Processing help text for environment diagnostics."""
        return self.tr(
            "Checks the active QGIS Python runtime and required scientific "
            "dependencies. This algorithm reports diagnostics only and does not "
            "install packages or run PyForestScan processing."
        )

    def createInstance(self) -> "EnvironmentCheckAlgorithm":
        """Create a new instance for the QGIS Processing registry."""
        return EnvironmentCheckAlgorithm()

    def initAlgorithm(self, configuration: dict[str, Any] | None = None) -> None:
        """Declare Processing parameters and outputs."""
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.CHECK_PYFORESTSCAN,
                self.tr("Check PyForestScan availability"),
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.CHECK_QGIS,
                self.tr("Check QGIS Processing environment"),
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.REPORT_FILE,
                self.tr("Optional diagnostic report"),
                fileFilter=self.tr("Text files (*.txt)"),
                optional=True,
            )
        )
        self.addOutput(
            QgsProcessingOutputString(
                self.OUTPUT_MESSAGE,
                self.tr("Diagnostic report"),
            )
        )

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, str]:
        """Run environment diagnostics and return the rendered report."""
        if feedback.isCanceled():
            raise QgsProcessingException(self.tr("Processing was canceled."))

        report = collect_environment_report(plugin_path=plugin_root())
        rendered_report = format_environment_report(report)
        self._push_report_to_feedback(rendered_report, feedback)

        report_file = self.parameterAsFileOutput(parameters, self.REPORT_FILE, context)
        if report_file:
            Path(report_file).write_text(rendered_report + "\n", encoding="utf-8")
            feedback.pushInfo(self.tr(f"Diagnostic report written to: {report_file}"))

        feedback.setProgress(100)
        return {self.OUTPUT_MESSAGE: rendered_report}

    def _push_report_to_feedback(
        self,
        rendered_report: str,
        feedback: QgsProcessingFeedback,
    ) -> None:
        """Render diagnostics through QGIS Processing feedback channels."""
        push_warning = getattr(feedback, "pushWarning", None)
        report_error = getattr(feedback, "reportError", None)

        for line in rendered_report.splitlines():
            if line.startswith(f"[{CheckStatus.WARNING.value}]"):
                if callable(push_warning):
                    push_warning(line)
                else:
                    feedback.pushInfo(line)
            elif line.startswith(f"[{CheckStatus.FAIL.value}]"):
                if "optional when PBM backend is READY" in line:
                    feedback.pushInfo(line)
                elif callable(report_error):
                    report_error(line, fatalError=False)
                else:
                    feedback.pushInfo(line)
            else:
                feedback.pushInfo(line)


class DatasetExplorerAlgorithm(PyForestScanAlgorithm):
    """Inspect a lidar dataset and generate planning reports."""

    INPUT_DATASET = "INPUT_DATASET"
    PROJECT_TITLE = "PROJECT_TITLE"
    OUTPUT_JSON = "OUTPUT_JSON"
    OUTPUT_CSV = "OUTPUT_CSV"
    OUTPUT_HTML = "OUTPUT_HTML"
    OUTPUT_JSON_TEXT = "OUTPUT_JSON_TEXT"

    def name(self) -> str:
        """Return the stable algorithm identifier."""
        return "dataset_explorer"

    def displayName(self) -> str:
        """Return the Processing display name."""
        return self.tr("Dataset Explorer")

    def shortHelpString(self) -> str:
        """Return Processing help text for Dataset Explorer."""
        return self.tr(
            "Inspects a LAS, LAZ, COPC, or EPT dataset with the PyForestScan "
            "adapter and generates JSON, CSV, and HTML planning reports. This "
            "workflow does not generate CHM, rasters, or scientific products."
        )

    def createInstance(self) -> "DatasetExplorerAlgorithm":
        """Create a new instance for the QGIS Processing registry."""
        return DatasetExplorerAlgorithm()

    def initAlgorithm(self, configuration: dict[str, Any] | None = None) -> None:
        """Declare Processing parameters and outputs."""
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_DATASET,
                self.tr("Input lidar dataset"),
                behavior=QgsProcessingParameterFile.File,
                fileFilter=self.tr(
                    "Point cloud datasets (*.las *.laz *.copc *.copc.laz *ept.json);;All files (*.*)"
                ),
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.PROJECT_TITLE,
                self.tr("Project title"),
                defaultValue="PyForestScan Dataset Explorer",
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_JSON,
                self.tr("Output JSON report"),
                fileFilter=self.tr("JSON files (*.json)"),
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_CSV,
                self.tr("Optional CSV summary"),
                fileFilter=self.tr("CSV files (*.csv)"),
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_HTML,
                self.tr("Optional HTML report"),
                fileFilter=self.tr("HTML files (*.html)"),
                optional=True,
            )
        )
        self.addOutput(
            QgsProcessingOutputString(
                self.OUTPUT_MESSAGE,
                self.tr("Dataset Explorer summary"),
            )
        )
        self.addOutput(
            QgsProcessingOutputString(
                self.OUTPUT_JSON_TEXT,
                self.tr("Structured JSON report"),
            )
        )

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, str]:
        """Inspect the dataset and write Dataset Explorer reports."""
        if feedback.isCanceled():
            raise QgsProcessingException(self.tr("Processing was canceled."))

        dataset_path = self.parameterAsFile(parameters, self.INPUT_DATASET, context)
        project_title = self.parameterAsString(parameters, self.PROJECT_TITLE, context)
        json_output = self.parameterAsFileOutput(parameters, self.OUTPUT_JSON, context)
        if not dataset_path:
            raise QgsProcessingException(self.tr("Input lidar dataset is required."))
        if not json_output:
            raise QgsProcessingException(self.tr("Output JSON report is required."))

        csv_output = self.parameterAsFileOutput(parameters, self.OUTPUT_CSV, context)
        html_output = self.parameterAsFileOutput(parameters, self.OUTPUT_HTML, context)
        if not csv_output:
            csv_output = str(Path(json_output).with_suffix(".csv"))
        if not html_output:
            html_output = str(Path(json_output).with_suffix(".html"))

        feedback.pushInfo(self.tr("Validating dataset..."))
        feedback.setProgress(10)
        adapter = PyForestScanAdapter()

        try:
            validation = adapter.validate_dataset(dataset_path)
            for message in validation.messages:
                feedback.pushInfo(message)
            if not validation.is_valid:
                raise QgsProcessingException(self.tr("Dataset validation failed."))

            if feedback.isCanceled():
                raise QgsProcessingException(self.tr("Processing was canceled."))

            feedback.pushInfo(self.tr("Inspecting dataset metadata and point structure..."))
            feedback.setProgress(35)
            inspection = adapter.inspect_dataset(dataset_path)

            if feedback.isCanceled():
                raise QgsProcessingException(self.tr("Processing was canceled."))

            feedback.pushInfo(self.tr("Building Dataset Explorer report..."))
            feedback.setProgress(65)
            report = build_dataset_explorer_report(
                inspection,
                title=project_title or "PyForestScan Dataset Explorer",
            )
            json_text = render_json_report(report)

            feedback.pushInfo(self.tr("Writing JSON, CSV, and HTML reports..."))
            feedback.setProgress(80)
            write_json_report(report, json_output)
            write_csv_summary(report, csv_output)
            write_html_report(report, html_output)
        except AdapterError as exc:
            raise QgsProcessingException(str(exc)) from exc
        except OSError as exc:
            raise QgsProcessingException(self.tr(f"Failed to write report output: {exc}")) from exc

        self._push_report_to_feedback(report, feedback)
        self._load_csv_table(csv_output, context, feedback)

        feedback.setProgress(100)
        return {
            self.OUTPUT_MESSAGE: self._summary_message(report),
            self.OUTPUT_JSON_TEXT: json_text,
            self.OUTPUT_JSON: str(json_output),
            self.OUTPUT_CSV: str(csv_output),
            self.OUTPUT_HTML: str(html_output),
        }

    def _push_report_to_feedback(
        self,
        report: DatasetExplorerReport,
        feedback: QgsProcessingFeedback,
    ) -> None:
        """Render the report summary through QGIS Processing feedback."""
        feedback.pushInfo(self.tr("Dataset Summary"))
        feedback.pushInfo(self.tr(f"Source: {report.source_path}"))
        feedback.pushInfo(self.tr(f"Format: {report.source_format.upper()}"))
        feedback.pushInfo(self.tr(f"Point count: {format_count_for_display(report.point_count)}"))
        feedback.pushInfo(self.tr(f"CRS: {format_crs_for_display(report.crs)}"))
        feedback.pushInfo(self.tr(f"Estimated density: {format_density_for_display(report.estimated_density)}"))
        feedback.pushInfo(self.tr(f"Dimensions: {', '.join(report.dimensions) or 'None reported'}"))

        push_warning = getattr(feedback, "pushWarning", None)
        for warning in report.warnings:
            line = f"{warning.severity}: {warning.code} - {warning.message}"
            if warning.severity == "ERROR":
                report_error = getattr(feedback, "reportError", None)
                if callable(report_error):
                    report_error(line, fatalError=False)
                else:
                    feedback.pushInfo(line)
            elif callable(push_warning):
                push_warning(line)
            else:
                feedback.pushInfo(line)

        feedback.pushInfo(self.tr("Supported PyForestScan products"))
        for product in report.products:
            feedback.pushInfo(self.tr(f"{product.label}: {product.status} - {product.reason}"))

    def _load_csv_table(
        self,
        csv_output: str,
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> None:
        """Load the CSV summary into the active QGIS project when possible."""
        layer = QgsVectorLayer(csv_output, self.tr("PyForestScan Dataset Explorer Summary"), "ogr")
        if not layer.isValid():
            push_warning = getattr(feedback, "pushWarning", None)
            message = self.tr(f"CSV summary was written but could not be loaded as a QGIS table: {csv_output}")
            if callable(push_warning):
                push_warning(message)
            else:
                feedback.pushInfo(message)
            return

        project = context.project()
        if project is not None:
            project.addMapLayer(layer)
            feedback.pushInfo(self.tr(f"CSV summary loaded as QGIS table: {csv_output}"))
        else:
            feedback.pushInfo(self.tr(f"CSV summary written: {csv_output}"))

    def _summary_message(self, report: DatasetExplorerReport) -> str:
        """Return a compact Processing result message."""
        available = [product.label for product in report.products if product.status == "Available"]
        warnings = len(report.warnings)
        if available:
            products = ", ".join(available)
        else:
            products = "No products marked fully available"
        return self.tr(f"Dataset Explorer complete. Available products: {products}. Warnings: {warnings}.")


class ProductPlannerAlgorithm(PyForestScanAlgorithm):
    """Create a non-computing product generation plan from Dataset Explorer JSON."""

    INPUT_REPORT = "INPUT_REPORT"
    DESIRED_PRODUCTS = "DESIRED_PRODUCTS"
    OUTPUT_FOLDER = "OUTPUT_FOLDER"
    GRID_RESOLUTION = "GRID_RESOLUTION"
    HEIGHT_BIN_SIZE = "HEIGHT_BIN_SIZE"
    PLAN_TITLE = "PLAN_TITLE"
    NOTES = "NOTES"
    OUTPUT_JSON = "OUTPUT_JSON"
    OUTPUT_CSV = "OUTPUT_CSV"
    OUTPUT_HTML = "OUTPUT_HTML"
    OUTPUT_JSON_TEXT = "OUTPUT_JSON_TEXT"

    PRODUCT_OPTIONS = [
        PRODUCT_LABELS[ProductType.CHM],
        PRODUCT_LABELS[ProductType.PAI],
        PRODUCT_LABELS[ProductType.PAD],
        PRODUCT_LABELS[ProductType.FHD],
        PRODUCT_LABELS[ProductType.CANOPY_COVER],
        PRODUCT_LABELS[ProductType.RUMPLE],
    ]
    PRODUCT_TYPES = (
        ProductType.CHM,
        ProductType.PAI,
        ProductType.PAD,
        ProductType.FHD,
        ProductType.CANOPY_COVER,
        ProductType.RUMPLE,
    )

    def name(self) -> str:
        """Return the stable algorithm identifier."""
        return "product_planner"

    def displayName(self) -> str:
        """Return the Processing display name."""
        return self.tr("Product Planner")

    def shortHelpString(self) -> str:
        """Return Processing help text for Product Planner."""
        return self.tr(
            "Reads a Dataset Explorer JSON report and creates JSON, CSV, and "
            "HTML planning reports for selected PyForestScan products. "
            "This algorithm does not run PyForestScan calculations or create rasters."
        )

    def createInstance(self) -> "ProductPlannerAlgorithm":
        """Create a new instance for the QGIS Processing registry."""
        return ProductPlannerAlgorithm()

    def initAlgorithm(self, configuration: dict[str, Any] | None = None) -> None:
        """Declare Processing parameters and outputs."""
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_REPORT,
                self.tr("Dataset Explorer JSON report"),
                behavior=QgsProcessingParameterFile.File,
                fileFilter=self.tr("JSON files (*.json);;All files (*.*)"),
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.DESIRED_PRODUCTS,
                self.tr("Desired products"),
                options=self.PRODUCT_OPTIONS,
                allowMultiple=True,
                defaultValue=[0],
            )
        )
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                self.OUTPUT_FOLDER,
                self.tr("Output folder for plan and generated products"),
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.GRID_RESOLUTION,
                self.tr("Grid resolution"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=1.0,
                minValue=0.01,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.HEIGHT_BIN_SIZE,
                self.tr("Optional height bin size"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=None,
                minValue=0.01,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.PLAN_TITLE,
                self.tr("Plan title"),
                defaultValue="PyForestScan Product Planner",
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.NOTES,
                self.tr("Optional notes"),
                defaultValue="",
                optional=True,
                multiLine=True,
            )
        )
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_MESSAGE, self.tr("Product plan summary")))
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_JSON, self.tr("Product plan JSON path")))
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_CSV, self.tr("Product plan CSV path")))
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_HTML, self.tr("Product plan HTML path")))
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_JSON_TEXT, self.tr("Structured product plan JSON")))

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, str]:
        """Create a Product Planner report without running scientific processing."""
        if feedback.isCanceled():
            raise QgsProcessingException(self.tr("Processing was canceled."))

        report_path = self.parameterAsFile(parameters, self.INPUT_REPORT, context)
        output_folder = self.parameterAsString(parameters, self.OUTPUT_FOLDER, context)
        grid_resolution = self.parameterAsDouble(parameters, self.GRID_RESOLUTION, context)
        height_bin_size = self.parameterAsDouble(parameters, self.HEIGHT_BIN_SIZE, context)
        title = self.parameterAsString(parameters, self.PLAN_TITLE, context)
        notes = self.parameterAsString(parameters, self.NOTES, context)
        product_indexes = self.parameterAsEnums(parameters, self.DESIRED_PRODUCTS, context)

        if not report_path:
            raise QgsProcessingException(self.tr("Dataset Explorer JSON report is required."))
        if not output_folder:
            raise QgsProcessingException(self.tr("Output folder is required."))
        requested_products = tuple(self.PRODUCT_TYPES[index] for index in product_indexes)
        if not requested_products:
            raise QgsProcessingException(self.tr("Select at least one desired product."))
        height_bin_value = height_bin_size if height_bin_size > 0 else None
        output_dir = Path(output_folder)

        feedback.pushInfo(self.tr("Reading Dataset Explorer report..."))
        feedback.setProgress(20)
        try:
            explorer_report = load_dataset_explorer_json(report_path)
            request = ProductPlannerRequest(
                explorer_report_path=Path(report_path),
                requested_products=requested_products,
                output_folder=output_dir,
                grid_resolution=grid_resolution,
                height_bin_size=height_bin_value,
                title=title or "PyForestScan Product Planner",
                notes=notes or "",
            )
            feedback.pushInfo(self.tr("Building product plan..."))
            feedback.setProgress(55)
            report = build_product_plan(explorer_report, request)
            json_text = render_plan_json(report)

            feedback.pushInfo(self.tr("Writing product plan reports..."))
            feedback.setProgress(80)
            output_dir.mkdir(parents=True, exist_ok=True)
            json_path = write_plan_json(report, output_dir / "product_plan.json")
            csv_path = write_plan_csv(report, output_dir / "product_plan.csv")
            html_path = write_plan_html(report, output_dir / "product_plan.html")
        except ProductPlanError as exc:
            raise QgsProcessingException(str(exc)) from exc
        except OSError as exc:
            raise QgsProcessingException(self.tr(f"Failed to write product plan output: {exc}")) from exc

        self._push_plan_to_feedback(report, feedback)
        feedback.setProgress(100)
        return {
            self.OUTPUT_MESSAGE: self._summary_message(report),
            self.OUTPUT_JSON_TEXT: json_text,
            self.OUTPUT_JSON: str(json_path),
            self.OUTPUT_CSV: str(csv_path),
            self.OUTPUT_HTML: str(html_path),
        }

    def _push_plan_to_feedback(
        self,
        report: ProductPlannerReport,
        feedback: QgsProcessingFeedback,
    ) -> None:
        """Render product plan decisions through Processing feedback."""
        feedback.pushInfo(self.tr("Product Plan Summary"))
        feedback.pushInfo(self.tr(f"Dataset: {report.source_dataset or 'Unknown'}"))
        feedback.pushInfo(self.tr(f"Grid resolution: {report.grid_resolution:g}"))
        if report.estimated_cells is not None:
            feedback.pushInfo(self.tr(f"Estimated grid cells: {report.estimated_cells:,}"))
        if report.estimated_height_bins is not None:
            feedback.pushInfo(self.tr(f"Estimated height bins: {report.estimated_height_bins:,}"))

        push_warning = getattr(feedback, "pushWarning", None)
        report_error = getattr(feedback, "reportError", None)
        for warning in report.warnings:
            line = f"{warning.severity}: {warning.code} - {warning.message}"
            if warning.severity.upper() == "ERROR" and callable(report_error):
                report_error(line, fatalError=False)
            elif callable(push_warning):
                push_warning(line)
            else:
                feedback.pushInfo(line)

        for item in report.products:
            feedback.pushInfo(self.tr(f"{item.label}: {item.plan_status} - {item.reason}"))
            for warning in item.warnings:
                line = f"{warning.severity}: {warning.code} - {warning.message}"
                if warning.severity.upper() == "ERROR" and callable(report_error):
                    report_error(line, fatalError=False)
                elif callable(push_warning):
                    push_warning(line)
                else:
                    feedback.pushInfo(line)

    def _summary_message(self, report: ProductPlannerReport) -> str:
        """Return a compact Product Planner result message."""
        ready = sum(1 for product in report.products if product.plan_status == "Ready")
        review = sum(1 for product in report.products if product.plan_status == "Needs review")
        blocked = sum(1 for product in report.products if product.plan_status == "Blocked")
        return self.tr(
            f"Product Planner complete. Ready: {ready}. Needs review: {review}. Blocked: {blocked}."
        )



class ForestMetricsPackAlgorithm(PlaceholderAlgorithm):
    """Unregistered compatibility shell for legacy forest-metric toolbox entries."""

    INPUT_LIDAR = "INPUT_LIDAR"
    SUMMARY_POLYGONS = "SUMMARY_POLYGONS"
    RESOLUTION = "RESOLUTION"
    METRICS = "METRICS"
    OUTPUT_FOLDER = "OUTPUT_FOLDER"

    METRIC_OPTIONS = [
        "Plant Area Index (PAI)",
        "Plant Area Density (PAD)",
        "Foliage Height Diversity (FHD)",
        "Canopy Cover",
        "Rumple Index",
        "Forest Structural Complexity",
    ]

    def name(self) -> str:
        """Return the stable algorithm identifier."""
        return "forest_metrics_pack"

    def displayName(self) -> str:
        """Return the Processing display name."""
        return self.tr("Forest Metrics Pack")

    def initAlgorithm(self, configuration: dict[str, Any] | None = None) -> None:
        """Declare Processing parameters and outputs."""
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_LIDAR,
                self.tr("Input lidar point cloud"),
                behavior=QgsProcessingParameterFile.File,
                fileFilter=self.tr("Point cloud files (*.las *.laz);;All files (*.*)"),
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.SUMMARY_POLYGONS,
                self.tr("Optional summary polygons"),
                types=[QgsProcessing.TypeVectorPolygon],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.RESOLUTION,
                self.tr("Output cell size"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=1.0,
                minValue=0.01,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.METRICS,
                self.tr("Metrics to prepare"),
                options=self.METRIC_OPTIONS,
                allowMultiple=True,
                defaultValue=[0, 1, 2, 3],
            )
        )
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                self.OUTPUT_FOLDER,
                self.tr("Output folder"),
            )
        )
        self.addOutput(
            QgsProcessingOutputString(
                self.OUTPUT_MESSAGE,
                self.tr("Status message"),
            )
        )
