"""PAD Processing algorithm."""

from __future__ import annotations

from typing import Any

from qgis.core import QgsProcessingContext, QgsProcessingFeedback, QgsProcessingOutputString

from ...core.adapter import PyForestScanAdapter
from ...core.advanced_processing import AdvancedVoxelParameters, build_pad_request
from .common import AdvancedPyForestScanAlgorithm, add_voxel_parameters, load_raster_if_requested, run_adapter_call


class AdvancedPadAlgorithm(AdvancedPyForestScanAlgorithm):
    """Generate expert-configured PAD as a multi-band GeoTIFF."""

    def name(self) -> str:
        return "advanced_pad"

    def displayName(self) -> str:
        return self.tr("PAD")

    def shortHelpString(self) -> str:
        return self.tr("Creates a Plant Area Density multi-band GeoTIFF from voxelized LiDAR returns. Use it to inspect vertical canopy structure by height bin. Key parameters are X/Y resolution, voxel_height, beer_lambert_constant, and drop_ground. PAD bands represent vertical bins; review band mapping in QGIS symbology.")

    def initAlgorithm(self, configuration: dict[str, Any] | None = None) -> None:
        self.add_input_dataset(); self.add_crs(); self.add_xy_resolution(); add_voxel_parameters(self, include_beer=True, min_default=0.0); self.add_geotiff_output("Output PAD multi-band GeoTIFF")
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_MESSAGE, self.tr("Status message")))

    def processAlgorithm(self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback) -> dict[str, str]:
        dataset, crs, output, xres, yres, add = self.common_values(parameters, context)
        params = AdvancedVoxelParameters(dataset, output, crs, xres, yres, add, self.parameterAsDouble(parameters, "VOXEL_HEIGHT", context), 0.0, None, self.parameterAsDouble(parameters, "BEER_LAMBERT_CONSTANT", context), self.parameterAsBool(parameters, "DROP_GROUND", context))
        request = build_pad_request(params)
        result = run_adapter_call(feedback, "PAD", lambda: PyForestScanAdapter().create_pad(request))
        load_raster_if_requested(result.output_path, "pad_geotiff", context, feedback, add)
        return self.push_result(feedback, result.output_path, "PAD")
