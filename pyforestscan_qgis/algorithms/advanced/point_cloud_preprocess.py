"""Advanced point-cloud preprocessing Processing algorithm."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qgis.core import QgsProcessingContext, QgsProcessingException, QgsProcessingFeedback, QgsProcessingOutputString, QgsProcessingParameterBoolean, QgsProcessingParameterEnum, QgsProcessingParameterFile, QgsProcessingParameterFileDestination, QgsProcessingParameterNumber, QgsProcessingParameterString

from ...core.adapter import PyForestScanAdapter
from ...core.advanced_processing import AdvancedPointCloudPreprocessParameters, LAS_FILTER, build_point_cloud_preprocess_request
from .common import AdvancedPyForestScanAlgorithm, run_adapter_call


class PointCloudPreprocessAlgorithm(AdvancedPyForestScanAlgorithm):
    """Run safe PyForestScan filters and write LAS/LAZ output."""

    ADVANCED_GROUP = "Preprocessing / Filters"

    REMOVE_OUTLIERS = "REMOVE_OUTLIERS"
    OUTLIER_MEAN_K = "OUTLIER_MEAN_K"
    OUTLIER_MULTIPLIER = "OUTLIER_MULTIPLIER"
    OUTLIER_REMOVE = "OUTLIER_REMOVE"
    CLASSIFY_GROUND = "CLASSIFY_GROUND"
    SMRF_IGNORE_CLASS = "SMRF_IGNORE_CLASS"
    SMRF_CELL = "SMRF_CELL"
    SMRF_CUT = "SMRF_CUT"
    SMRF_RETURNS = "SMRF_RETURNS"
    SMRF_SCALAR = "SMRF_SCALAR"
    SMRF_SLOPE = "SMRF_SLOPE"
    SMRF_THRESHOLD = "SMRF_THRESHOLD"
    SMRF_WINDOW = "SMRF_WINDOW"
    GROUND_ACTION = "GROUND_ACTION"
    FILTER_POINTSOURCEID = "FILTER_POINTSOURCEID"
    POINTSOURCE_IDS = "POINTSOURCE_IDS"
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
    HAG_OPTIONS = ("auto", "delaunay", "dtm")
    VOXELGRID_OPTIONS = ("first", "last", "center", "nearest")

    def name(self) -> str:
        return "advanced_point_cloud_preprocess"

    def displayName(self) -> str:
        return self.tr("Preprocess Point Cloud")

    def shortHelpString(self) -> str:
        return self.tr("Applies selected PyForestScan filters in a documented order and writes LAS/LAZ output. Use it for expert preprocessing before metric generation. Operations run in this order: remove_outliers_and_clean, classify_ground_points, ground filter/select, filter_pointsourceid, add_height_above_ground, filter_hag, downsample_poisson, downsample_voxel, write_las. Review outputs before using them for products.")

    def initAlgorithm(self, configuration: dict[str, Any] | None = None) -> None:
        self.add_input_dataset(); self.add_crs()
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT, self.tr("Output LAS/LAZ"), fileFilter=self.tr(LAS_FILTER)))
        self.addParameter(QgsProcessingParameterBoolean(self.REMOVE_OUTLIERS, self.tr("Remove outliers and clean"), defaultValue=False))
        self.addParameter(QgsProcessingParameterNumber(self.OUTLIER_MEAN_K, self.tr("mean_k"), type=QgsProcessingParameterNumber.Integer, defaultValue=8, minValue=1))
        self.addParameter(QgsProcessingParameterNumber(self.OUTLIER_MULTIPLIER, self.tr("multiplier"), type=QgsProcessingParameterNumber.Double, defaultValue=3.0, minValue=0.01))
        self.addParameter(QgsProcessingParameterBoolean(self.OUTLIER_REMOVE, self.tr("remove"), defaultValue=False))
        self.addParameter(QgsProcessingParameterBoolean(self.CLASSIFY_GROUND, self.tr("Classify ground points"), defaultValue=False))
        self.addParameter(QgsProcessingParameterString(self.SMRF_IGNORE_CLASS, self.tr("ignore_class"), defaultValue="Classification[7:7]"))
        self.addParameter(QgsProcessingParameterNumber(self.SMRF_CELL, self.tr("SMRF cell"), type=QgsProcessingParameterNumber.Double, defaultValue=1.0, minValue=0.01))
        self.addParameter(QgsProcessingParameterNumber(self.SMRF_CUT, self.tr("cut"), type=QgsProcessingParameterNumber.Double, defaultValue=0.0))
        self.addParameter(QgsProcessingParameterString(self.SMRF_RETURNS, self.tr("returns"), defaultValue="last,only"))
        self.addParameter(QgsProcessingParameterNumber(self.SMRF_SCALAR, self.tr("scalar"), type=QgsProcessingParameterNumber.Double, defaultValue=1.25, minValue=0.01))
        self.addParameter(QgsProcessingParameterNumber(self.SMRF_SLOPE, self.tr("slope"), type=QgsProcessingParameterNumber.Double, defaultValue=0.15, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(self.SMRF_THRESHOLD, self.tr("threshold"), type=QgsProcessingParameterNumber.Double, defaultValue=0.5, minValue=0.01))
        self.addParameter(QgsProcessingParameterNumber(self.SMRF_WINDOW, self.tr("window"), type=QgsProcessingParameterNumber.Double, defaultValue=18.0, minValue=0.01))
        self.addParameter(QgsProcessingParameterEnum(self.GROUND_ACTION, self.tr("Ground filter action"), options=list(self.GROUND_OPTIONS), defaultValue=0))
        self.addParameter(QgsProcessingParameterBoolean(self.FILTER_POINTSOURCEID, self.tr("Filter PointSourceId"), defaultValue=False))
        self.addParameter(QgsProcessingParameterString(self.POINTSOURCE_IDS, self.tr("pointsource_ids"), defaultValue=""))
        self.addParameter(QgsProcessingParameterBoolean(self.ADD_HAG, self.tr("Add HeightAboveGround"), defaultValue=False))
        self.addParameter(QgsProcessingParameterEnum(self.HAG_METHOD, self.tr("HAG method"), options=list(self.HAG_OPTIONS), defaultValue=0))
        self.addParameter(QgsProcessingParameterFile(self.DTM, self.tr("DTM GeoTIFF"), behavior=QgsProcessingParameterFile.File, fileFilter=self.tr("GeoTIFF files (*.tif *.tiff);;All files (*.*)"), optional=True))
        self.addParameter(QgsProcessingParameterBoolean(self.FILTER_HAG, self.tr("Filter by HeightAboveGround range"), defaultValue=False))
        self.addParameter(QgsProcessingParameterNumber(self.HAG_LOWER, self.tr("lower_limit"), type=QgsProcessingParameterNumber.Double, defaultValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(self.HAG_UPPER, self.tr("upper_limit"), type=QgsProcessingParameterNumber.Double, defaultValue=None, optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.THIN_RADIUS, self.tr("thin_radius"), type=QgsProcessingParameterNumber.Double, defaultValue=None, minValue=0.0, optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.VOXELGRID_CELL, self.tr("voxel downsample cell"), type=QgsProcessingParameterNumber.Double, defaultValue=None, minValue=0.0, optional=True))
        self.addParameter(QgsProcessingParameterEnum(self.VOXELGRID_MODE, self.tr("voxel downsample mode"), options=list(self.VOXELGRID_OPTIONS), defaultValue=0))
        self.addParameter(QgsProcessingParameterBoolean(self.COMPRESS, self.tr("compress"), defaultValue=True))
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
            outlier_remove=self.parameterAsBool(parameters, self.OUTLIER_REMOVE, context),
            classify_ground=self.parameterAsBool(parameters, self.CLASSIFY_GROUND, context),
            smrf_ignore_class=self.parameterAsString(parameters, self.SMRF_IGNORE_CLASS, context),
            smrf_cell=self.parameterAsDouble(parameters, self.SMRF_CELL, context),
            smrf_cut=self.parameterAsDouble(parameters, self.SMRF_CUT, context),
            smrf_returns=self.parameterAsString(parameters, self.SMRF_RETURNS, context),
            smrf_scalar=self.parameterAsDouble(parameters, self.SMRF_SCALAR, context),
            smrf_slope=self.parameterAsDouble(parameters, self.SMRF_SLOPE, context),
            smrf_threshold=self.parameterAsDouble(parameters, self.SMRF_THRESHOLD, context),
            smrf_window=self.parameterAsDouble(parameters, self.SMRF_WINDOW, context),
            ground_action=self.GROUND_OPTIONS[self.parameterAsEnum(parameters, self.GROUND_ACTION, context)],
            filter_pointsourceid=self.parameterAsBool(parameters, self.FILTER_POINTSOURCEID, context),
            pointsource_ids_text=self.parameterAsString(parameters, self.POINTSOURCE_IDS, context),
            add_hag=self.parameterAsBool(parameters, self.ADD_HAG, context),
            hag_method=self._hag_method(parameters, context),
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
        result = run_adapter_call(feedback, "Preprocess Point Cloud", lambda: PyForestScanAdapter(execution_mode="pbm_backend").preprocess_point_cloud(request))
        feedback.setProgress(100)
        message = self.tr(f"Preprocessed point cloud written: {result.output_path}. Operations: {', '.join(result.operations) or 'none'}")
        feedback.pushInfo(message)
        return {self.OUTPUT_MESSAGE: message, self.OUTPUT: str(result.output_path)}

    def _hag_method(self, parameters: dict[str, Any], context: QgsProcessingContext) -> str | None:
        """Return PyForestScan add_height_above_ground method, using None for auto."""
        value = self.HAG_OPTIONS[self.parameterAsEnum(parameters, self.HAG_METHOD, context)]
        return None if value == "auto" else value
