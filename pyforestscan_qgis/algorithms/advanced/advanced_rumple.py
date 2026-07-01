"""Rumple Processing algorithm."""

from __future__ import annotations

from typing import Any

from qgis.core import QgsProcessingContext, QgsProcessingFeedback, QgsProcessingOutputString, QgsProcessingParameterBoolean, QgsProcessingParameterNumber

from ...core.adapter import PyForestScanAdapter
from ...core.advanced_processing import AdvancedRumpleParameters, build_rumple_request
from .common import AdvancedPyForestScanAlgorithm, load_csv_if_requested, run_adapter_call


class AdvancedRumpleAlgorithm(AdvancedPyForestScanAlgorithm):
    """Generate an expert-configured rumple CSV summary through the adapter."""

    INTERPOLATION = "INTERPOLATION"
    INTERP_VALID_REGION = "INTERP_VALID_REGION"
    CLEAN_EDGES = "CLEAN_EDGES"
    MIN_HEIGHT = "MIN_HEIGHT"

    def name(self) -> str:
        return "advanced_rumple"

    def displayName(self) -> str:
        return self.tr("Rumple")

    def shortHelpString(self) -> str:
        return self.tr("Calculates a scalar Rumple Index from an internally generated CHM and writes a CSV summary. Use it for whole-dataset canopy surface complexity. Key parameters are CHM resolution, interpolation, edge handling, and optional min_height. The output is a table, not a raster.")

    def initAlgorithm(self, configuration: dict[str, Any] | None = None) -> None:
        self.add_input_dataset(); self.add_crs(); self.add_xy_resolution(); self.add_csv_output("Output rumple CSV summary")
        self.add_interpolation(self.INTERPOLATION, "CHM interpolation", default_index=2)
        self.addParameter(QgsProcessingParameterBoolean(self.INTERP_VALID_REGION, self.tr("Interpolate valid region only"), defaultValue=False))
        self.addParameter(QgsProcessingParameterBoolean(self.CLEAN_EDGES, self.tr("Clean interpolation edges"), defaultValue=False))
        self.addParameter(QgsProcessingParameterNumber(self.MIN_HEIGHT, self.tr("Optional minimum height"), type=QgsProcessingParameterNumber.Double, defaultValue=None, minValue=0.0, optional=True))
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_MESSAGE, self.tr("Status message")))

    def processAlgorithm(self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback) -> dict[str, str]:
        dataset, crs, output, xres, yres, add = self.common_values(parameters, context)
        params = AdvancedRumpleParameters(dataset, output, crs, xres, yres, self.interpolation_value(parameters, self.INTERPOLATION, context), self.parameterAsBool(parameters, self.INTERP_VALID_REGION, context), self.parameterAsBool(parameters, self.CLEAN_EDGES, context), self.optional_double(parameters, self.MIN_HEIGHT, context), add)
        request = build_rumple_request(params)
        result = run_adapter_call(feedback, "Rumple", lambda: PyForestScanAdapter().create_rumple(request))
        load_csv_if_requested(result.output_path, context, feedback, add, "PyForestScan Rumple Summary")
        return self.push_result(feedback, result.output_path, "Rumple")
