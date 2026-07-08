"""EPT subset extraction Processing algorithm."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qgis.core import (
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingOutputString,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
)

from ...core.adapter import PyForestScanAdapter
from ...core.advanced_processing import LAS_FILTER
from ...core.ept_subset import build_ept_subset_request, compact_ept_subset_summary
from .common import AdvancedPyForestScanAlgorithm, run_adapter_call


class EptSubsetExtractAlgorithm(AdvancedPyForestScanAlgorithm):
    """Extract an EPT subset with read_lidar bounds/crop/thinning options."""

    ADVANCED_GROUP = "Input / I/O"

    INPUT_FILE = "input_file"
    SRS = "srs"
    BOUNDS = "bounds"
    THIN_RADIUS = "thin_radius"
    HAG_METHOD = "hag_method"
    HAG = "hag"
    HAG_DTM = "hag_dtm"
    DTM = "dtm"
    CROP_POLY = "crop_poly"
    POLY = "poly"
    REPROJECT = "reproject"
    OUTPUT_LAS_LAZ = "output_las_laz"
    COMPRESS = "compress"
    HAG_METHODS = ("none", "delaunay", "dtm")

    def name(self) -> str:
        return "extract_ept_subset"

    def displayName(self) -> str:
        return self.tr("Extract EPT Subset")

    def shortHelpString(self) -> str:
        return self.tr(
            "Extracts a bounded or cropped subset from an Entwine Point Tile ept.json source. "
            "Parameters map to pyforestscan.handlers.read_lidar(input_file, srs, bounds, thin_radius, "
            "hag, hag_dtm, dtm, crop_poly, poly, reproject), then write_las writes LAS/LAZ output."
        )

    def initAlgorithm(self, configuration: dict[str, Any] | None = None) -> None:
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_FILE,
                self.tr("input_file (EPT ept.json)"),
                behavior=QgsProcessingParameterFile.File,
                fileFilter=self.tr("EPT metadata (ept.json);;JSON files (*.json);;All files (*.*)"),
            )
        )
        self.addParameter(QgsProcessingParameterString(self.SRS, self.tr("srs / CRS"), defaultValue="EPSG:4326"))
        self.addParameter(QgsProcessingParameterString(self.BOUNDS, self.tr("bounds xmin,xmax,ymin,ymax[,zmin,zmax]"), defaultValue="", optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.THIN_RADIUS, self.tr("thin_radius"), type=QgsProcessingParameterNumber.Double, defaultValue=None, minValue=0.0, optional=True))
        self.addParameter(QgsProcessingParameterEnum(self.HAG_METHOD, self.tr("HAG method"), options=list(self.HAG_METHODS), defaultValue=0))
        self.addParameter(QgsProcessingParameterBoolean(self.HAG, self.tr("hag (Delaunay HAG)"), defaultValue=False))
        self.addParameter(QgsProcessingParameterBoolean(self.HAG_DTM, self.tr("hag_dtm (DTM-backed HAG)"), defaultValue=False))
        self.addParameter(QgsProcessingParameterFile(self.DTM, self.tr("dtm"), behavior=QgsProcessingParameterFile.File, fileFilter=self.tr("GeoTIFF files (*.tif *.tiff);;All files (*.*)"), optional=True))
        self.addParameter(QgsProcessingParameterBoolean(self.CROP_POLY, self.tr("crop_poly"), defaultValue=False))
        self.addParameter(QgsProcessingParameterString(self.POLY, self.tr("poly (polygon WKT or polygon file)"), defaultValue="", optional=True, multiLine=True))
        self.addParameter(QgsProcessingParameterBoolean(self.REPROJECT, self.tr("reproject"), defaultValue=False))
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT_LAS_LAZ, self.tr("output_las_laz"), fileFilter=self.tr(LAS_FILTER)))
        self.addParameter(QgsProcessingParameterBoolean(self.COMPRESS, self.tr("compress LAZ output"), defaultValue=True))
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_MESSAGE, self.tr("Status message")))
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_LAS_LAZ, self.tr("EPT subset LAS/LAZ output path")))

    def processAlgorithm(self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback) -> dict[str, str]:
        input_file = self.parameterAsFile(parameters, self.INPUT_FILE, context)
        if not input_file:
            raise QgsProcessingException(self.tr("input_file is required."))
        output_text = self.parameterAsFileOutput(parameters, self.OUTPUT_LAS_LAZ, context)
        if not output_text:
            raise QgsProcessingException(self.tr("output_las_laz is required."))
        hag_method = self.HAG_METHODS[self.parameterAsEnum(parameters, self.HAG_METHOD, context)]
        hag = self.parameterAsBool(parameters, self.HAG, context) or hag_method == "delaunay"
        hag_dtm = self.parameterAsBool(parameters, self.HAG_DTM, context) or hag_method == "dtm"
        dtm_text = self.parameterAsFile(parameters, self.DTM, context)
        request = build_ept_subset_request(
            input_path=input_file,
            crs=self.parameterAsString(parameters, self.SRS, context),
            output_path=Path(output_text),
            bounds_text=self.parameterAsString(parameters, self.BOUNDS, context),
            thin_radius=self.optional_double(parameters, self.THIN_RADIUS, context),
            hag=hag,
            hag_dtm=hag_dtm,
            dtm_path=Path(dtm_text) if dtm_text else None,
            crop_poly=self.parameterAsBool(parameters, self.CROP_POLY, context),
            poly=self.parameterAsString(parameters, self.POLY, context),
            reproject=self.parameterAsBool(parameters, self.REPROJECT, context),
            compress=self.parameterAsBool(parameters, self.COMPRESS, context),
        )
        result = run_adapter_call(feedback, "EPT Subset", lambda: PyForestScanAdapter().extract_lidar_subset(request))
        message = compact_ept_subset_summary(result)
        feedback.setProgress(100)
        feedback.pushInfo(self.tr(message))
        return {self.OUTPUT_MESSAGE: self.tr(message), self.OUTPUT_LAS_LAZ: str(result.output_path)}
