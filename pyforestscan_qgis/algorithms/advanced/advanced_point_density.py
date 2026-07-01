"""Point Density Processing algorithm."""

from __future__ import annotations

from typing import Any

from qgis.core import QgsProcessingContext, QgsProcessingFeedback, QgsProcessingOutputString, QgsProcessingParameterBoolean, QgsProcessingParameterNumber

from ...core.adapter import PyForestScanAdapter
from ...core.advanced_processing import AdvancedPointDensityParameters, build_point_density_request
from .common import AdvancedPyForestScanAlgorithm, load_raster_if_requested, run_adapter_call


class AdvancedPointDensityAlgorithm(AdvancedPyForestScanAlgorithm):
    """Generate expert-configured point-density rasters through the adapter."""

    VOXEL_HEIGHT = "VOXEL_HEIGHT"
    PER_AREA = "PER_AREA"
    CELL_AREA = "CELL_AREA"

    def name(self) -> str:
        """Return the Processing algorithm identifier."""
        return "advanced_point_density"

    def displayName(self) -> str:
        """Return the Processing display name."""
        return self.tr("Point Density")

    def shortHelpString(self) -> str:
        """Return Processing help text."""
        return self.tr("Creates a point-density GeoTIFF by voxelizing LiDAR returns and summing returns by X/Y column. Use it to QA sampling support before interpreting structural metrics. Key parameters are voxel_height, per_area, and cell_area. If cell_area is blank, the adapter uses X resolution multiplied by Y resolution.")

    def initAlgorithm(self, configuration: dict[str, Any] | None = None) -> None:
        """Register Processing parameters."""
        self.add_input_dataset(); self.add_crs(); self.add_xy_resolution()
        self.addParameter(QgsProcessingParameterNumber(self.VOXEL_HEIGHT, self.tr("voxel_resolution Z / voxel height"), type=QgsProcessingParameterNumber.Double, defaultValue=1.0, minValue=0.01))
        self.addParameter(QgsProcessingParameterBoolean(self.PER_AREA, self.tr("per_area"), defaultValue=False))
        self.addParameter(QgsProcessingParameterNumber(self.CELL_AREA, self.tr("cell_area"), type=QgsProcessingParameterNumber.Double, defaultValue=None, minValue=0.000001, optional=True))
        self.add_geotiff_output("Output Point Density GeoTIFF")
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_MESSAGE, self.tr("Status message")))

    def processAlgorithm(self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback) -> dict[str, str]:
        """Run advanced point-density generation."""
        dataset, crs, output, xres, yres, add = self.common_values(parameters, context)
        params = AdvancedPointDensityParameters(
            input_path=dataset,
            output_path=output,
            crs=crs,
            x_resolution=xres,
            y_resolution=yres,
            add_to_project=add,
            voxel_height=self.parameterAsDouble(parameters, self.VOXEL_HEIGHT, context),
            per_area=self.parameterAsBool(parameters, self.PER_AREA, context),
            cell_area=self.optional_double(parameters, self.CELL_AREA, context),
        )
        request = build_point_density_request(params)
        result = run_adapter_call(feedback, "Point Density", lambda: PyForestScanAdapter().create_point_density(request))
        load_raster_if_requested(result.output_path, "point_density_geotiff", context, feedback, add)
        return self.push_result(feedback, result.output_path, "Point Density")
