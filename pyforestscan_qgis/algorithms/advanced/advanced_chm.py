"""CHM Processing algorithm."""

from __future__ import annotations

from typing import Any

from qgis.core import QgsProcessingContext, QgsProcessingFeedback, QgsProcessingOutputString, QgsProcessingParameterBoolean

from ...core.adapter import PyForestScanAdapter
from ...core.advanced_processing import AdvancedChmParameters, build_chm_request
from .common import AdvancedPyForestScanAlgorithm, load_raster_if_requested, run_adapter_call


class AdvancedChmAlgorithm(AdvancedPyForestScanAlgorithm):
    """Generate an expert-configured CHM through the adapter."""

    INTERPOLATION = "INTERPOLATION"
    INTERP_VALID_REGION = "INTERP_VALID_REGION"
    CLEAN_EDGES = "CLEAN_EDGES"

    def name(self) -> str:
        return "advanced_chm"

    def displayName(self) -> str:
        return self.tr("CHM")

    def shortHelpString(self) -> str:
        return self.tr("Creates a Canopy Height Model GeoTIFF from a LiDAR dataset using PyForestScan calculate_chm. Use it when the dataset has reliable height-above-ground support. Key parameters are X/Y resolution, interpolation, valid-region interpolation, and edge cleaning. Verify CRS, extent, and height values in QGIS before interpretation.")

    def initAlgorithm(self, configuration: dict[str, Any] | None = None) -> None:
        self.add_input_dataset(); self.add_crs(); self.add_xy_resolution(); self.add_geotiff_output("Output CHM GeoTIFF")
        self.add_interpolation(self.INTERPOLATION, "Interpolation", default_index=2)
        self.addParameter(QgsProcessingParameterBoolean(self.INTERP_VALID_REGION, self.tr("Interpolate valid region only"), defaultValue=False))
        self.addParameter(QgsProcessingParameterBoolean(self.CLEAN_EDGES, self.tr("Clean interpolation edges"), defaultValue=False))
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_MESSAGE, self.tr("Status message")))

    def processAlgorithm(self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback) -> dict[str, str]:
        dataset, crs, output, xres, yres, add = self.common_values(parameters, context)
        params = AdvancedChmParameters(dataset, output, crs, xres, yres, add, self.interpolation_value(parameters, self.INTERPOLATION, context), self.parameterAsBool(parameters, self.INTERP_VALID_REGION, context), self.parameterAsBool(parameters, self.CLEAN_EDGES, context))
        request = build_chm_request(params)
        result = run_adapter_call(feedback, "CHM", lambda: PyForestScanAdapter().create_chm(request))
        load_raster_if_requested(result.output_path, "chm_geotiff", context, feedback, add)
        return self.push_result(feedback, result.output_path, "CHM")
