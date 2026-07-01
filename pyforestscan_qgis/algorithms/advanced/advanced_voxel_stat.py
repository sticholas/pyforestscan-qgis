"""Voxel Statistic Processing algorithm."""

from __future__ import annotations

from typing import Any

from qgis.core import QgsProcessingContext, QgsProcessingFeedback, QgsProcessingOutputString, QgsProcessingParameterEnum, QgsProcessingParameterNumber, QgsProcessingParameterString

from ...core.adapter import PyForestScanAdapter
from ...core.advanced_processing import AdvancedVoxelStatParameters, VALID_VOXEL_STATS, build_voxel_stat_request
from .common import AdvancedPyForestScanAlgorithm, load_raster_if_requested, run_adapter_call


class AdvancedVoxelStatAlgorithm(AdvancedPyForestScanAlgorithm):
    """Generate expert-configured voxel-statistic rasters through the adapter."""

    VOXEL_HEIGHT = "VOXEL_HEIGHT"
    DIMENSION = "DIMENSION"
    STAT = "STAT"
    Z_INDEX_MIN = "Z_INDEX_MIN"
    Z_INDEX_MAX = "Z_INDEX_MAX"

    def name(self) -> str:
        """Return the Processing algorithm identifier."""
        return "advanced_voxel_statistic"

    def displayName(self) -> str:
        """Return the Processing display name."""
        return self.tr("Voxel Statistic")

    def shortHelpString(self) -> str:
        """Return Processing help text."""
        return self.tr("Calculates a statistic for a point-cloud dimension using PyForestScan calculate_voxel_stat. Supported stat values are mean, sum, count, min, max, median, and std.")

    def initAlgorithm(self, configuration: dict[str, Any] | None = None) -> None:
        """Register Processing parameters."""
        self.add_input_dataset(); self.add_crs(); self.add_xy_resolution()
        self.addParameter(QgsProcessingParameterNumber(self.VOXEL_HEIGHT, self.tr("voxel_resolution Z / voxel height"), type=QgsProcessingParameterNumber.Double, defaultValue=1.0, minValue=0.01))
        self.addParameter(QgsProcessingParameterString(self.DIMENSION, self.tr("dimension"), defaultValue="HeightAboveGround"))
        self.addParameter(QgsProcessingParameterEnum(self.STAT, self.tr("stat"), options=list(VALID_VOXEL_STATS), defaultValue=0))
        self.addParameter(QgsProcessingParameterNumber(self.Z_INDEX_MIN, self.tr("z_index_range minimum"), type=QgsProcessingParameterNumber.Integer, defaultValue=None, minValue=0, optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.Z_INDEX_MAX, self.tr("z_index_range maximum"), type=QgsProcessingParameterNumber.Integer, defaultValue=None, minValue=0, optional=True))
        self.add_geotiff_output("Output Voxel Statistic GeoTIFF")
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_MESSAGE, self.tr("Status message")))

    def processAlgorithm(self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback) -> dict[str, str]:
        """Run advanced voxel-statistic generation."""
        dataset, crs, output, xres, yres, add = self.common_values(parameters, context)
        params = AdvancedVoxelStatParameters(
            input_path=dataset,
            output_path=output,
            crs=crs,
            x_resolution=xres,
            y_resolution=yres,
            add_to_project=add,
            voxel_height=self.parameterAsDouble(parameters, self.VOXEL_HEIGHT, context),
            dimension=self.parameterAsString(parameters, self.DIMENSION, context),
            stat=VALID_VOXEL_STATS[self.parameterAsEnum(parameters, self.STAT, context)],
            z_index_min=self._optional_int(parameters, self.Z_INDEX_MIN, context),
            z_index_max=self._optional_int(parameters, self.Z_INDEX_MAX, context),
        )
        request = build_voxel_stat_request(params)
        result = run_adapter_call(feedback, "Voxel Statistic", lambda: PyForestScanAdapter().create_voxel_stat(request))
        load_raster_if_requested(result.output_path, "voxel_stat_geotiff", context, feedback, add)
        return self.push_result(feedback, result.output_path, "Voxel Statistic")

    def _optional_int(self, parameters: dict[str, Any], name: str, context: QgsProcessingContext) -> int | None:
        value = parameters.get(name)
        if value in (None, ""):
            return None
        return self.parameterAsInt(parameters, name, context)
