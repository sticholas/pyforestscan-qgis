"""PAI Processing algorithm."""

from __future__ import annotations

from typing import Any

from qgis.core import QgsProcessingContext, QgsProcessingFeedback, QgsProcessingOutputString

from ...core.adapter import PyForestScanAdapter
from ...core.advanced_processing import AdvancedVoxelParameters, build_pai_request
from .common import AdvancedPyForestScanAlgorithm, add_voxel_parameters, load_raster_if_requested, run_adapter_call


class AdvancedPaiAlgorithm(AdvancedPyForestScanAlgorithm):
    """Generate expert-configured PAI through the adapter."""

    def name(self) -> str:
        return "advanced_pai"

    def displayName(self) -> str:
        return self.tr("PAI")

    def shortHelpString(self) -> str:
        return self.tr("Creates a Plant Area Index GeoTIFF by calculating PAD internally and integrating over min_height to max_height. Use it for area-integrated canopy structure. Key parameters are voxel_height, min_height, max_height, beer_lambert_constant, and drop_ground. Confirm the selected height range matches the study design.")

    def initAlgorithm(self, configuration: dict[str, Any] | None = None) -> None:
        self.add_input_dataset(); self.add_crs(); self.add_xy_resolution(); add_voxel_parameters(self, include_beer=True, min_default=1.0); self.add_geotiff_output("Output PAI GeoTIFF")
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_MESSAGE, self.tr("Status message")))

    def processAlgorithm(self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback) -> dict[str, str]:
        dataset, crs, output, xres, yres, add = self.common_values(parameters, context)
        params = AdvancedVoxelParameters(dataset, output, crs, xres, yres, add, self.parameterAsDouble(parameters, "VOXEL_HEIGHT", context), self.parameterAsDouble(parameters, "MIN_HEIGHT", context), self.optional_double(parameters, "MAX_HEIGHT", context), self.parameterAsDouble(parameters, "BEER_LAMBERT_CONSTANT", context), self.parameterAsBool(parameters, "DROP_GROUND", context))
        request = build_pai_request(params)
        result = run_adapter_call(feedback, "PAI", lambda: PyForestScanAdapter().create_pai(request))
        load_raster_if_requested(result.output_path, "pai_geotiff", context, feedback, add)
        return self.push_result(feedback, result.output_path, "PAI")
