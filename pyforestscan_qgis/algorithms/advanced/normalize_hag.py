"""Height Above Ground / Normalize Heights Processing algorithm."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qgis.core import QgsProcessingContext, QgsProcessingException, QgsProcessingFeedback, QgsProcessingOutputString, QgsProcessingParameterBoolean, QgsProcessingParameterFile, QgsProcessingParameterFileDestination, QgsProcessingParameterNumber, QgsProcessingParameterString

from ...core.adapter import PyForestScanAdapter
from ...core.advanced_processing import AdvancedHagParameters, build_hag_request
from .common import AdvancedPyForestScanAlgorithm, LAS_FILTER, run_adapter_call


class NormalizeHagAlgorithm(AdvancedPyForestScanAlgorithm):
    """Read lidar with HeightAboveGround and optionally write a normalized LAS/LAZ."""

    USE_DTM = "USE_DTM"
    DTM = "DTM"
    REPROJECT = "REPROJECT"
    COMPRESS = "COMPRESS"
    BOUNDS = "BOUNDS"
    THIN_RADIUS = "THIN_RADIUS"
    CROP_POLYGON = "CROP_POLYGON"

    def name(self) -> str:
        return "normalize_height_above_ground"

    def displayName(self) -> str:
        return self.tr("Generate Height Above Ground / Normalize Heights")

    def shortHelpString(self) -> str:
        return self.tr("Reads lidar with PyForestScan handlers.read_lidar(..., hag=True) or DTM-backed HAG and writes LAS/LAZ only when a supported output is provided. It does not fake unsupported normalized outputs.")

    def initAlgorithm(self, configuration: dict[str, Any] | None = None) -> None:
        self.add_input_dataset(); self.add_crs()
        self.addParameter(QgsProcessingParameterBoolean(self.USE_DTM, self.tr("Use DTM-backed HAG"), defaultValue=False))
        self.addParameter(QgsProcessingParameterFile(self.DTM, self.tr("Optional DTM GeoTIFF"), behavior=QgsProcessingParameterFile.File, fileFilter=self.tr("GeoTIFF files (*.tif *.tiff);;All files (*.*)"), optional=True))
        self.addParameter(QgsProcessingParameterBoolean(self.REPROJECT, self.tr("Reproject to CRS while reading"), defaultValue=False))
        self.addParameter(QgsProcessingParameterString(self.BOUNDS, self.tr("Optional bounds xmin,xmax,ymin,ymax[,zmin,zmax]"), defaultValue="", optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.THIN_RADIUS, self.tr("Optional thinning radius"), type=QgsProcessingParameterNumber.Double, defaultValue=None, minValue=0.0, optional=True))
        self.addParameter(QgsProcessingParameterString(self.CROP_POLYGON, self.tr("Optional crop polygon WKT or file path"), defaultValue="", optional=True, multiLine=True))
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT, self.tr("Optional normalized LAS/LAZ output"), fileFilter=self.tr(LAS_FILTER), optional=True))
        self.addParameter(QgsProcessingParameterBoolean(self.COMPRESS, self.tr("Write compressed LAZ"), defaultValue=True))
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_MESSAGE, self.tr("Status message")))
        self.addOutput(QgsProcessingOutputString(self.OUTPUT, self.tr("Normalized point-cloud output path")))

    def processAlgorithm(self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback) -> dict[str, str]:
        dataset = self.parameterAsFile(parameters, self.INPUT_DATASET, context)
        if not dataset:
            raise QgsProcessingException(self.tr("Input lidar dataset is required."))
        output_text = self.parameterAsFileOutput(parameters, self.OUTPUT, context)
        dtm_text = self.parameterAsFile(parameters, self.DTM, context)
        params = AdvancedHagParameters(
            input_path=dataset,
            crs=self.parameter_crs_text(parameters, context),
            output_path=Path(output_text) if output_text else None,
            use_dtm=self.parameterAsBool(parameters, self.USE_DTM, context),
            dtm_path=Path(dtm_text) if dtm_text else None,
            reproject=self.parameterAsBool(parameters, self.REPROJECT, context),
            compress=self.parameterAsBool(parameters, self.COMPRESS, context),
            bounds_text=self.parameterAsString(parameters, self.BOUNDS, context),
            thin_radius=self.optional_double(parameters, self.THIN_RADIUS, context),
            crop_polygon=self.parameterAsString(parameters, self.CROP_POLYGON, context),
        )
        request = build_hag_request(params)
        result = run_adapter_call(feedback, "Height Above Ground", lambda: PyForestScanAdapter().normalize_heights(request))
        message = "HAG point cloud written" if result.written else "HAG read completed; no point-cloud output was requested"
        if result.limitation:
            feedback.pushInfo(result.limitation)
        feedback.setProgress(100)
        feedback.pushInfo(self.tr(message))
        return {self.OUTPUT_MESSAGE: self.tr(message), self.OUTPUT: str(result.output_path or "")}
