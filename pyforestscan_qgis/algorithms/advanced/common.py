"""Shared helpers for Advanced PyForestScan Processing algorithms."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterCrs,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterNumber,
    QgsRasterLayer,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon

from ...core.advanced_processing import CSV_FILTER, GEOTIFF_FILTER, LAS_FILTER, POINT_CLOUD_FILTER, VALID_INTERPOLATION
from ...core.exceptions import AdapterError
from ...resources import plugin_icon
from ...ui.raster_styling import apply_generated_raster_renderer, layer_display_name


class AdvancedPyForestScanAlgorithm(QgsProcessingAlgorithm):
    """Base class for expert Processing Toolbox algorithms."""

    ADVANCED_GROUP = "Metrics"
    INPUT_DATASET = "INPUT_DATASET"
    CRS = "CRS"
    X_RESOLUTION = "X_RESOLUTION"
    Y_RESOLUTION = "Y_RESOLUTION"
    OUTPUT = "OUTPUT"
    ADD_TO_PROJECT = "ADD_TO_PROJECT"
    OUTPUT_MESSAGE = "OUTPUT_MESSAGE"

    def tr(self, text: str) -> str:
        """Translate user-facing Processing text."""
        return QCoreApplication.translate("PyForestScan", text)

    def group(self) -> str:
        """Return the Processing group display name."""
        return self.tr(f"PyForestScan / {self.ADVANCED_GROUP}")

    def groupId(self) -> str:
        """Return the stable Processing group identifier."""
        return "pyforestscan_" + self.ADVANCED_GROUP.lower().replace(" / ", "_").replace(" ", "_")

    def icon(self) -> QIcon:
        """Return the provider icon."""
        return plugin_icon()

    def createInstance(self) -> "AdvancedPyForestScanAlgorithm":
        """Create a new instance for QGIS Processing."""
        return self.__class__()

    def add_input_dataset(self) -> None:
        """Add common lidar input parameter."""
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_DATASET,
                self.tr("Input LiDAR dataset (LAS, LAZ, COPC, or EPT)"),
                behavior=QgsProcessingParameterFile.File,
                fileFilter=self.tr(POINT_CLOUD_FILTER),
            )
        )

    def add_crs(self) -> None:
        """Add common CRS parameter."""
        self.addParameter(QgsProcessingParameterCrs(self.CRS, self.tr("Dataset CRS / SRS"), defaultValue="EPSG:4326"))

    def add_xy_resolution(self, default: float = 1.0) -> None:
        """Add X/Y raster resolution parameters."""
        self.addParameter(
            QgsProcessingParameterNumber(
                self.X_RESOLUTION,
                self.tr("X resolution (map units)"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=default,
                minValue=0.01,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.Y_RESOLUTION,
                self.tr("Y resolution (map units)"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=default,
                minValue=0.01,
            )
        )

    def add_geotiff_output(self, label: str) -> None:
        """Add GeoTIFF output and load-to-project parameter."""
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT, self.tr(label), fileFilter=self.tr(GEOTIFF_FILTER)))
        self.addParameter(QgsProcessingParameterBoolean(self.ADD_TO_PROJECT, self.tr("Add output to project"), defaultValue=True))

    def add_csv_output(self, label: str, add_label: str = "Add CSV to project as table") -> None:
        """Add CSV output and optional table loading parameter."""
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT, self.tr(label), fileFilter=self.tr(CSV_FILTER)))
        self.addParameter(QgsProcessingParameterBoolean(self.ADD_TO_PROJECT, self.tr(add_label), defaultValue=True))

    def parameter_crs_text(self, parameters: dict[str, Any], context: QgsProcessingContext) -> str:
        """Return CRS as an auth id or WKT string."""
        crs = self.parameterAsCrs(parameters, self.CRS, context)
        if crs.isValid():
            return crs.authid() or crs.toWkt()
        return str(parameters.get(self.CRS) or "").strip()

    def common_values(self, parameters: dict[str, Any], context: QgsProcessingContext) -> tuple[str, str, Path, float, float, bool]:
        """Return common dataset, CRS, output, resolution, and loading values."""
        dataset = self.parameterAsFile(parameters, self.INPUT_DATASET, context)
        output = self.parameterAsFileOutput(parameters, self.OUTPUT, context)
        if not dataset:
            raise QgsProcessingException(self.tr("Input lidar dataset is required."))
        if not output:
            raise QgsProcessingException(self.tr("Output path is required."))
        return (
            dataset,
            self.parameter_crs_text(parameters, context),
            Path(output),
            self.parameterAsDouble(parameters, self.X_RESOLUTION, context),
            self.parameterAsDouble(parameters, self.Y_RESOLUTION, context),
            self.parameterAsBool(parameters, self.ADD_TO_PROJECT, context),
        )

    def optional_double(self, parameters: dict[str, Any], name: str, context: QgsProcessingContext) -> float | None:
        """Return an optional Processing double parameter."""
        value = parameters.get(name)
        if value in (None, ""):
            return None
        return self.parameterAsDouble(parameters, name, context)

    def add_interpolation(self, name: str, label: str, default_index: int = 2) -> None:
        """Add interpolation enum parameter."""
        self.addParameter(QgsProcessingParameterEnum(name, self.tr(label), options=list(VALID_INTERPOLATION), defaultValue=default_index))

    def interpolation_value(self, parameters: dict[str, Any], name: str, context: QgsProcessingContext) -> str:
        """Return selected interpolation option."""
        return VALID_INTERPOLATION[self.parameterAsEnum(parameters, name, context)]

    def push_result(self, feedback: QgsProcessingFeedback, output_path: Path, result_label: str) -> dict[str, str]:
        """Return common result payload after progress completion."""
        feedback.setProgress(100)
        message = self.tr(f"{result_label} created: {output_path}")
        feedback.pushInfo(message)
        return {self.OUTPUT_MESSAGE: message, self.OUTPUT: str(output_path)}


def add_voxel_parameters(algorithm: AdvancedPyForestScanAlgorithm, *, include_beer: bool = True, min_default: float = 0.0) -> None:
    """Add common voxel/PAD integration parameters."""
    algorithm.addParameter(
        QgsProcessingParameterNumber(
            "VOXEL_HEIGHT",
            algorithm.tr("voxel_height / height bin size (map units)"),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=1.0,
            minValue=0.01,
        )
    )
    algorithm.addParameter(
        QgsProcessingParameterNumber(
            "MIN_HEIGHT",
            algorithm.tr("min_height (map units)"),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=min_default,
            minValue=0.0,
        )
    )
    algorithm.addParameter(
        QgsProcessingParameterNumber(
            "MAX_HEIGHT",
            algorithm.tr("max_height (map units, optional)"),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=None,
            minValue=0.0,
            optional=True,
        )
    )
    if include_beer:
        algorithm.addParameter(
            QgsProcessingParameterNumber(
                "BEER_LAMBERT_CONSTANT",
                algorithm.tr("beer_lambert_constant"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=1.0,
                minValue=0.000001,
            )
        )
        algorithm.addParameter(QgsProcessingParameterBoolean("DROP_GROUND", algorithm.tr("drop_ground"), defaultValue=True))


def load_raster_if_requested(path: Path, result_type: str, context: QgsProcessingContext, feedback: QgsProcessingFeedback, add_to_project: bool) -> None:
    """Best-effort load and style a generated raster output."""
    if not add_to_project:
        return
    project = context.project()
    if project is None:
        feedback.pushInfo(f"Raster written but no QGIS project is available for loading: {path}")
        return
    layer = QgsRasterLayer(str(path), layer_display_name(result_type, path.stem))
    if not layer.isValid():
        _warn(feedback, f"Raster was written but could not be loaded: {path}")
        return
    project.addMapLayer(layer)
    try:
        apply_generated_raster_renderer(layer, result_type)
    except Exception as exc:  # noqa: BLE001 - styling should not fail processing.
        _warn(feedback, f"Raster loaded but styling failed: {exc}")
    feedback.pushInfo(f"Raster loaded into QGIS: {path}")


def load_csv_if_requested(path: Path, context: QgsProcessingContext, feedback: QgsProcessingFeedback, add_to_project: bool, name: str) -> None:
    """Best-effort load a CSV output as a QGIS table."""
    if not add_to_project:
        return
    project = context.project()
    if project is None:
        feedback.pushInfo(f"CSV written but no QGIS project is available for loading: {path}")
        return
    layer = QgsVectorLayer(str(path), name, "ogr")
    if not layer.isValid():
        _warn(feedback, f"CSV was written but could not be loaded as a QGIS table: {path}")
        return
    project.addMapLayer(layer)
    feedback.pushInfo(f"CSV loaded as QGIS table: {path}")


def run_adapter_call(feedback: QgsProcessingFeedback, label: str, function: Any) -> Any:
    """Run an adapter call and convert plugin errors to QGIS errors."""
    if feedback.isCanceled():
        raise QgsProcessingException("Processing was canceled.")
    feedback.pushInfo(f"Running {label} through PyForestScan adapter...")
    feedback.setProgress(15)
    try:
        result = function()
    except AdapterError as exc:
        raise QgsProcessingException(str(exc)) from exc
    if feedback.isCanceled():
        raise QgsProcessingException("Processing was canceled.")
    feedback.setProgress(85)
    return result


def _warn(feedback: QgsProcessingFeedback, message: str) -> None:
    push_warning = getattr(feedback, "pushWarning", None)
    if callable(push_warning):
        push_warning(message)
    else:
        feedback.pushInfo(message)
