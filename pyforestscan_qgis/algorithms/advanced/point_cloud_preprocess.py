"""Advanced point-cloud preprocessing Processing algorithm."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qgis.core import QgsProcessingContext, QgsProcessingException, QgsProcessingFeedback, QgsProcessingOutputString, QgsProcessingParameterBoolean, QgsProcessingParameterEnum, QgsProcessingParameterFile, QgsProcessingParameterFileDestination, QgsProcessingParameterNumber

from ...core.adapter import PyForestScanAdapter
from ...core.advanced_processing import AdvancedPointCloudPreprocessParameters, LAS_FILTER, build_point_cloud_preprocess_request
from .common import AdvancedPyForestScanAlgorithm, run_adapter_call


class PointCloudPreprocessAlgorithm(AdvancedPyForestScanAlgorithm):
    """Run safe PyForestScan filters and write LAS/LAZ output."""

    REMOVE_OUTLIERS = "REMOVE_OUTLIERS"
    OUTLIER_MEAN_K = "OUTLIER_MEAN_K"
    OUTLIER_MULTIPLIER = "OUTLIER_MULTIPLIER"
    CLASSIFY_GROUND = "CLASSIFY_GROUND"
    GROUND_ACTION = "GROUND_ACTION"
    ADD_HAG = "ADD_HAG"
    HAG_METHOD = "HAG_METHOD"
    DTM = "DTM"
    FILTER_HAG = "FILTER_HAG"
    HAG_LOWER = "HAG_LOWER"
    HAG_UPPER = "HAG_UPPER"
    THIN_RADIUS = "THIN_RADIUS"
    VOXELGRID_CELL = "VOXELGRID_CELL"
    VOXELGRID_MODE = "VOXELGRID_MODE"
    COMPRESS = "COMPRESS"
    GROUND_OPTIONS = ("none", "remove_ground", "select_ground")
    HAG_OPTIONS = ("delaunay", "dtm")
    VOXELGRID_OPTIONS = ("first", "last", "center", "nearest")

    def name(self) -> str:
        return "advanced_point_cloud_preprocess"

    def displayName(self) -> str:
        return self.tr("Advanced Point Cloud Preprocess / Filters")

    def shortHelpString(self) -> str:
        return self.tr("Runs selected PyForestScan filter functions through the adapter and writes LAS/LAZ output.")

    def initAlgorithm(self, configuration: dict[str, Any] | None = None) -> None:
        self.add_input_dataset(); self.add_crs()
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT, self.tr("Output LAS/LAZ"), fileFilter=self.tr(LAS_FILTER)))
        self.addParameter(QgsProcessingParameterBoolean(self.REMOVE_OUTLIERS, self.tr("Remove outliers and clean"), defaultValue=False))
        self.addParameter(QgsProcessingParameterNumber(self.OUTLIER_MEAN_K, self.tr("Outlier mean_k"), type=QgsProcessingParameterNumber.Integer, defaultValue=8, minValue=1))
        self.addParameter(QgsProcessingParameterNumber(self.OUTLIER_MULTIPLIER, self.tr("Outlier multiplier"), type=QgsProcessingParameterNumber.Double, defaultValue=3.0, minValue=0.01))
        self.addParameter(QgsProcessingParameterBoolean(self.CLASSIFY_GROUND, self.tr("Classify ground points"), defaultValue=False))
        self.addParameter(QgsProcessingParameterEnum(self.GROUND_ACTION, self.tr("Ground filter action"), options=list(self.GROUND_OPTIONS), defaultValue=0))
        self.addParameter(QgsProcessingParameterBoolean(self.ADD_HAG, self.tr("Add HeightAboveGround"), defaultValue=False))
        self.addParameter(QgsProcessingParameterEnum(self.HAG_METHOD, self.tr("HAG method"), options=list(self.HAG_OPTIONS), defaultValue=0))
        self.addParameter(QgsProcessingParameterFile(self.DTM, self.tr("Optional DTM GeoTIFF"), behavior=QgsProcessingParameterFile.File, fileFilter=self.tr("GeoTIFF files (*.tif *.tiff);;All files (*.*)"), optional=True))
        self.addParameter(QgsProcessingParameterBoolean(self.FILTER_HAG, self.tr("Filter by HeightAboveGround range"), defaultValue=False))
        self.addParameter(QgsProcessingParameterNumber(self.HAG_LOWER, self.tr("HAG lower limit"), type=QgsProcessingParameterNumber.Double, defaultValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(self.HAG_UPPER, self.tr("Optional HAG upper limit"), type=QgsProcessingParameterNumber.Double, defaultValue=None, optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.THIN_RADIUS, self.tr("Optional Poisson thinning radius"), type=QgsProcessingParameterNumber.Double, defaultValue=None, minValue=0.0, optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.VOXELGRID_CELL, self.tr("Optional voxel-grid cell size"), type=QgsProcessingParameterNumber.Double, defaultValue=None, minValue=0.0, optional=True))
        self.addParameter(QgsProcessingParameterEnum(self.VOXELGRID_MODE, self.tr("Voxel-grid mode"), options=list(self.VOXELGRID_OPTIONS), defaultValue=0))
        self.addParameter(QgsProcessingParameterBoolean(self.COMPRESS, self.tr("Write compressed LAZ"), defaultValue=True))
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_MESSAGE, self.tr("Status message")))

    def processAlgorithm(self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback) -> dict[str, str]:
        dataset = self.parameterAsFile(parameters, self.INPUT_DATASET, context)
        output = self.parameterAsFileOutput(parameters, self.OUTPUT, context)
        if not dataset or not output:
            raise QgsProcessingException(self.tr("Input dataset and output LAS/LAZ are required."))
        dtm_text = self.parameterAsFile(parameters, self.DTM, context)
        params = AdvancedPointCloudPreprocessParameters(
            input_path=dataset,
            output_path=Path(output),
            crs=self.parameter_crs_text(parameters, context),
            remove_outliers=self.parameterAsBool(parameters, self.REMOVE_OUTLIERS, context),
            outlier_mean_k=self.parameterAsInt(parameters, self.OUTLIER_MEAN_K, context),
            outlier_multiplier=self.parameterAsDouble(parameters, self.OUTLIER_MULTIPLIER, context),
            classify_ground=self.parameterAsBool(parameters, self.CLASSIFY_GROUND, context),
            ground_action=self.GROUND_OPTIONS[self.parameterAsEnum(parameters, self.GROUND_ACTION, context)],
            add_hag=self.parameterAsBool(parameters, self.ADD_HAG, context),
            hag_method=self.HAG_OPTIONS[self.parameterAsEnum(parameters, self.HAG_METHOD, context)],
            dtm_path=Path(dtm_text) if dtm_text else None,
            filter_hag=self.parameterAsBool(parameters, self.FILTER_HAG, context),
            hag_lower_limit=self.parameterAsDouble(parameters, self.HAG_LOWER, context),
            hag_upper_limit=self.optional_double(parameters, self.HAG_UPPER, context),
            thin_radius=self.optional_double(parameters, self.THIN_RADIUS, context),
            voxelgrid_cell=self.optional_double(parameters, self.VOXELGRID_CELL, context),
            voxelgrid_mode=self.VOXELGRID_OPTIONS[self.parameterAsEnum(parameters, self.VOXELGRID_MODE, context)],
            compress=self.parameterAsBool(parameters, self.COMPRESS, context),
        )
        request = build_point_cloud_preprocess_request(params)
        result = run_adapter_call(feedback, "Advanced point-cloud preprocessing", lambda: PyForestScanAdapter().preprocess_point_cloud(request))
        feedback.setProgress(100)
        message = self.tr(f"Preprocessed point cloud written: {result.output_path}. Operations: {', '.join(result.operations) or 'none'}")
        feedback.pushInfo(message)
        return {self.OUTPUT_MESSAGE: message, self.OUTPUT: str(result.output_path)}
