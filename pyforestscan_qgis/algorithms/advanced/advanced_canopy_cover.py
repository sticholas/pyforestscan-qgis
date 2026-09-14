"""Canopy Cover Processing algorithm."""

from __future__ import annotations

from typing import Any

from qgis.core import QgsProcessingContext, QgsProcessingFeedback, QgsProcessingOutputString, QgsProcessingParameterNumber

from ...core.adapter import PyForestScanAdapter
from ...core.advanced_processing import AdvancedCanopyCoverParameters, build_canopy_cover_request
from .common import AdvancedPyForestScanAlgorithm, add_voxel_parameters, load_raster_if_requested, run_adapter_call


class AdvancedCanopyCoverAlgorithm(AdvancedPyForestScanAlgorithm):
    """Generate expert-configured canopy cover through the adapter."""

    EXTINCTION_COEFFICIENT = "EXTINCTION_COEFFICIENT"

    def name(self) -> str:
        return "advanced_canopy_cover"

    def displayName(self) -> str:
        return self.tr("Canopy Cover")

    def shortHelpString(self) -> str:
        return self.tr("Creates a canopy-cover GeoTIFF from internally calculated PAD using PyForestScan calculate_canopy_cover. Use it to estimate cover above a height threshold. Key parameters are voxel_height, min_height, max_height, k, beer_lambert_constant, and drop_ground. Confirm the height threshold and extinction coefficient are appropriate for the study.")

    def initAlgorithm(self, configuration: dict[str, Any] | None = None) -> None:
        self.add_input_dataset(); self.add_crs(); self.add_xy_resolution(); add_voxel_parameters(self, include_beer=True, min_default=2.0)
        self.addParameter(QgsProcessingParameterNumber(self.EXTINCTION_COEFFICIENT, self.tr("k / extinction coefficient"), type=QgsProcessingParameterNumber.Double, defaultValue=0.5, minValue=0.0))
        self.add_geotiff_output("Output canopy cover GeoTIFF")
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_MESSAGE, self.tr("Status message")))

    def processAlgorithm(self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback) -> dict[str, str]:
        dataset, crs, output, xres, yres, add = self.common_values(parameters, context)
        params = AdvancedCanopyCoverParameters(dataset, output, crs, xres, yres, add, self.parameterAsDouble(parameters, "VOXEL_HEIGHT", context), self.parameterAsDouble(parameters, "MIN_HEIGHT", context), self.optional_double(parameters, "MAX_HEIGHT", context), self.parameterAsDouble(parameters, "BEER_LAMBERT_CONSTANT", context), self.parameterAsBool(parameters, "DROP_GROUND", context), self.parameterAsDouble(parameters, self.EXTINCTION_COEFFICIENT, context))
        request = build_canopy_cover_request(params)
        result = run_adapter_call(feedback, "Canopy Cover", lambda: PyForestScanAdapter(execution_mode="pbm_backend").create_canopy_cover(request))
        load_raster_if_requested(result.output_path, "canopy_cover_geotiff", context, feedback, add)
        return self.push_result(feedback, result.output_path, "Canopy Cover")
