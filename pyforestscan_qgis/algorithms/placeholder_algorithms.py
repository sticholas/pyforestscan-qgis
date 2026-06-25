"""Processing algorithms for the PyForestScan provider.

Phase 2 implements the Environment Check algorithm. Scientific algorithms remain
safe placeholders until later phases introduce PyForestScan-backed runners.
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
    QgsProcessingParameterRasterDestination,
)
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon

from ..core.dependency_check import (
    CheckStatus,
    collect_environment_report,
    format_environment_report,
)
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
    """Base class for future scientific algorithms that are not implemented yet."""

    def shortHelpString(self) -> str:
        """Return Processing help text for Phase 1/2 placeholders."""
        return self.tr(
            "This algorithm is reserved for a future PyForestScan workflow. "
            "It reports 'Not yet implemented.' and performs no PyForestScan, "
            "lidar, or PDAL computation."
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
        """Report placeholder status and return a successful Processing result."""
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
                if callable(report_error):
                    report_error(line, fatalError=False)
                else:
                    feedback.pushInfo(line)
            else:
                feedback.pushInfo(line)


class CreateCanopyHeightModelAlgorithm(PlaceholderAlgorithm):
    """Placeholder for future Canopy Height Model generation."""

    INPUT_LIDAR = "INPUT_LIDAR"
    GROUND_CLASS = "GROUND_CLASS"
    VEGETATION_CLASS = "VEGETATION_CLASS"
    RESOLUTION = "RESOLUTION"
    HEIGHT_PERCENTILE = "HEIGHT_PERCENTILE"
    OUTPUT_CHM = "OUTPUT_CHM"

    def name(self) -> str:
        """Return the stable algorithm identifier."""
        return "create_canopy_height_model"

    def displayName(self) -> str:
        """Return the Processing display name."""
        return self.tr("Create Canopy Height Model")

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
            QgsProcessingParameterNumber(
                self.GROUND_CLASS,
                self.tr("Ground classification value"),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=2,
                minValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.VEGETATION_CLASS,
                self.tr("Vegetation classification value"),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=5,
                minValue=0,
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
            QgsProcessingParameterNumber(
                self.HEIGHT_PERCENTILE,
                self.tr("Canopy height percentile"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=95.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT_CHM,
                self.tr("Output canopy height model"),
            )
        )
        self.addOutput(
            QgsProcessingOutputString(
                self.OUTPUT_MESSAGE,
                self.tr("Status message"),
            )
        )


class ForestMetricsPackAlgorithm(PlaceholderAlgorithm):
    """Placeholder for future forest structural metric product generation."""

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
