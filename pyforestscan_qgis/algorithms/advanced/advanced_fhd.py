"""Advanced FHD Processing algorithm."""

from __future__ import annotations

from typing import Any

from qgis.core import QgsProcessingContext, QgsProcessingFeedback, QgsProcessingOutputString

from ...core.adapter import PyForestScanAdapter
from ...core.advanced_processing import AdvancedVoxelParameters, build_fhd_request
from .common import AdvancedPyForestScanAlgorithm, add_voxel_parameters, load_raster_if_requested, run_adapter_call


class AdvancedFhdAlgorithm(AdvancedPyForestScanAlgorithm):
    """Generate expert-configured FHD through the adapter."""

    def name(self) -> str:
        return "advanced_fhd"

    def displayName(self) -> str:
        return self.tr("Advanced FHD")

    def shortHelpString(self) -> str:
        return self.tr("Advanced FHD uses assign_voxels and calculate_fhd through the adapter with explicit height range controls.")

    def initAlgorithm(self, configuration: dict[str, Any] | None = None) -> None:
        self.add_input_dataset(); self.add_crs(); self.add_xy_resolution(); add_voxel_parameters(self, include_beer=False, min_default=0.0); self.add_geotiff_output("Output FHD GeoTIFF")
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_MESSAGE, self.tr("Status message")))

    def processAlgorithm(self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback) -> dict[str, str]:
        dataset, crs, output, xres, yres, add = self.common_values(parameters, context)
        params = AdvancedVoxelParameters(dataset, output, crs, xres, yres, add, self.parameterAsDouble(parameters, "VOXEL_HEIGHT", context), self.parameterAsDouble(parameters, "MIN_HEIGHT", context), self.optional_double(parameters, "MAX_HEIGHT", context), 1.0, True)
        request = build_fhd_request(params)
        result = run_adapter_call(feedback, "Advanced FHD", lambda: PyForestScanAdapter().create_fhd(request))
        load_raster_if_requested(result.output_path, "fhd_geotiff", context, feedback, add)
        return self.push_result(feedback, result.output_path, "Advanced FHD")
