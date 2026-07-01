"""Generate DTM Processing algorithm."""

from __future__ import annotations

from typing import Any

from pathlib import Path

from qgis.core import QgsProcessingContext, QgsProcessingException, QgsProcessingFeedback, QgsProcessingOutputString, QgsProcessingParameterBoolean, QgsProcessingParameterNumber

from ...core.adapter import PyForestScanAdapter
from ...core.advanced_processing import AdvancedDtmParameters, build_dtm_request
from .common import AdvancedPyForestScanAlgorithm, load_raster_if_requested, run_adapter_call


class AdvancedDtmAlgorithm(AdvancedPyForestScanAlgorithm):
    """Generate a DTM GeoTIFF from ground-classified lidar points."""

    ADVANCED_GROUP = "Terrain"

    RESOLUTION = "RESOLUTION"
    CLASSIFY_GROUND = "CLASSIFY_GROUND"
    NODATA = "NODATA"

    def name(self) -> str:
        return "advanced_dtm"

    def displayName(self) -> str:
        return self.tr("Generate DTM")

    def shortHelpString(self) -> str:
        return self.tr("Generates a Digital Terrain Model from ground points using PyForestScan generate_dtm through the adapter.")

    def initAlgorithm(self, configuration: dict[str, Any] | None = None) -> None:
        self.add_input_dataset(); self.add_crs()
        self.addParameter(QgsProcessingParameterNumber(self.RESOLUTION, self.tr("DTM resolution"), type=QgsProcessingParameterNumber.Double, defaultValue=2.0, minValue=0.01))
        self.addParameter(QgsProcessingParameterBoolean(self.CLASSIFY_GROUND, self.tr("Classify ground before DTM"), defaultValue=False))
        self.addParameter(QgsProcessingParameterNumber(self.NODATA, self.tr("NoData value"), type=QgsProcessingParameterNumber.Double, defaultValue=-9999.0))
        self.add_geotiff_output("Output DTM GeoTIFF")
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_MESSAGE, self.tr("Status message")))

    def processAlgorithm(self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback) -> dict[str, str]:
        dataset = self.parameterAsFile(parameters, self.INPUT_DATASET, context)
        output = self.parameterAsFileOutput(parameters, self.OUTPUT, context)
        if not dataset or not output:
            raise QgsProcessingException(self.tr("Input dataset and output GeoTIFF are required."))
        params = AdvancedDtmParameters(
            input_path=dataset,
            output_path=Path(output),
            crs=self.parameter_crs_text(parameters, context),
            resolution=self.parameterAsDouble(parameters, self.RESOLUTION, context),
            classify_ground=self.parameterAsBool(parameters, self.CLASSIFY_GROUND, context),
            nodata=self.parameterAsDouble(parameters, self.NODATA, context),
            add_to_project=self.parameterAsBool(parameters, self.ADD_TO_PROJECT, context),
        )
        request = build_dtm_request(params)
        result = run_adapter_call(feedback, "Generate DTM", lambda: PyForestScanAdapter().generate_dtm(request))
        load_raster_if_requested(result.output_path, "dtm_geotiff", context, feedback, params.add_to_project)
        return self.push_result(feedback, result.output_path, "Generate DTM")
