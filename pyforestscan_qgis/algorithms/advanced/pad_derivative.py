"""PAD derivative raster Processing algorithm."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qgis.core import (
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingOutputString,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterNumber,
)

from ...core.advanced_processing import GEOTIFF_FILTER
from ...core.adapter import PyForestScanAdapter
from ...core.types import PadDerivativeRequest
from .common import AdvancedPyForestScanAlgorithm, run_adapter_call


class PadDerivativeRasterAlgorithm(AdvancedPyForestScanAlgorithm):
    """Create a 2D visualization raster from an authoritative PAD volume."""

    ADVANCED_GROUP = "Metrics"

    INPUT_PAD = "INPUT_PAD"
    DERIVATIVE_TYPE = "DERIVATIVE_TYPE"
    MIN_HEIGHT = "MIN_HEIGHT"
    MAX_HEIGHT = "MAX_HEIGHT"
    SLICE_HEIGHT = "SLICE_HEIGHT"
    BAND_INDEX = "BAND_INDEX"
    VOXEL_HEIGHT = "VOXEL_HEIGHT"
    OUTPUT_DERIVATIVE = "OUTPUT_DERIVATIVE"
    TYPES = ("slice", "maximum", "mean", "integrated")

    def name(self) -> str:
        return "pad_derivative_raster"

    def displayName(self) -> str:
        return self.tr("PAD Derivative Raster")

    def shortHelpString(self) -> str:
        return self.tr(
            "Creates a plugin-derived single-band visualization from a complete PAD multiband volume. "
            "This does not replace the authoritative PAD output; it derives a height slice, maximum, mean, "
            "or integrated PAD projection over selected height bins."
        )

    def initAlgorithm(self, configuration: dict[str, Any] | None = None) -> None:
        self.addParameter(QgsProcessingParameterFile(self.INPUT_PAD, self.tr("Authoritative PAD multiband GeoTIFF"), behavior=QgsProcessingParameterFile.File, fileFilter=self.tr(GEOTIFF_FILTER)))
        self.addParameter(QgsProcessingParameterEnum(self.DERIVATIVE_TYPE, self.tr("Derivative type"), options=list(self.TYPES), defaultValue=0))
        self.addParameter(QgsProcessingParameterNumber(self.VOXEL_HEIGHT, self.tr("voxel_height"), type=QgsProcessingParameterNumber.Double, defaultValue=1.0, minValue=0.000001))
        self.addParameter(QgsProcessingParameterNumber(self.SLICE_HEIGHT, self.tr("slice height"), type=QgsProcessingParameterNumber.Double, defaultValue=10.0, minValue=0.0, optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.BAND_INDEX, self.tr("band index"), type=QgsProcessingParameterNumber.Integer, defaultValue=None, minValue=1, optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.MIN_HEIGHT, self.tr("minimum height"), type=QgsProcessingParameterNumber.Double, defaultValue=None, minValue=0.0, optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.MAX_HEIGHT, self.tr("maximum height"), type=QgsProcessingParameterNumber.Double, defaultValue=None, minValue=0.0, optional=True))
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT_DERIVATIVE, self.tr("PAD derivative output GeoTIFF"), fileFilter=self.tr(GEOTIFF_FILTER)))
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_MESSAGE, self.tr("Status message")))
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_DERIVATIVE, self.tr("PAD derivative output path")))

    def processAlgorithm(self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback) -> dict[str, str]:
        input_pad = self.parameterAsFile(parameters, self.INPUT_PAD, context)
        output = self.parameterAsFileOutput(parameters, self.OUTPUT_DERIVATIVE, context)
        if not input_pad or not output:
            raise QgsProcessingException(self.tr("Input PAD and output GeoTIFF are required."))
        derivative_type = self.TYPES[self.parameterAsEnum(parameters, self.DERIVATIVE_TYPE, context)]
        request = PadDerivativeRequest(
            input_path=Path(input_pad),
            derivative_type=derivative_type,  # type: ignore[arg-type]
            output_path=Path(output),
            voxel_height=self.parameterAsDouble(parameters, self.VOXEL_HEIGHT, context),
            min_height=self.optional_double(parameters, self.MIN_HEIGHT, context),
            max_height=self.optional_double(parameters, self.MAX_HEIGHT, context),
            slice_height=self.optional_double(parameters, self.SLICE_HEIGHT, context),
            band_index=int(self.parameterAsInt(parameters, self.BAND_INDEX, context)) if parameters.get(self.BAND_INDEX) not in (None, "") else None,
        )
        result = run_adapter_call(
            feedback,
            "PAD Derivative",
            lambda: PyForestScanAdapter(execution_mode="pbm_backend").create_pad_derivative(request),
        )
        message = self.tr(f"PAD {result.derivative_type} derivative created: {result.output_path}")
        feedback.pushInfo(message)
        feedback.setProgress(100)
        return {self.OUTPUT_MESSAGE: message, self.OUTPUT_DERIVATIVE: str(result.output_path)}
