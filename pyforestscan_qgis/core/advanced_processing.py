"""QGIS-free request builders for Advanced Processing Toolbox algorithms."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .exceptions import ProcessingError
from .types import (
    CanopyCoverRequest,
    ChmRequest,
    FhdRequest,
    HagNormalizationRequest,
    PadRequest,
    PaiRequest,
    ProductType,
    RumpleRequest,
)

Interpolation = Literal["none", "nearest", "linear", "cubic"]

VALID_INTERPOLATION = ("none", "nearest", "linear", "cubic")
POINT_CLOUD_FILTER = "Point cloud datasets (*.las *.laz *.copc *.copc.laz *ept.json);;All files (*.*)"
GEOTIFF_FILTER = "GeoTIFF files (*.tif *.tiff)"
CSV_FILTER = "CSV files (*.csv)"
LAS_FILTER = "LAS/LAZ files (*.las *.laz)"


@dataclass(frozen=True)
class AdvancedRasterParameters:
    """Common spatial raster settings for advanced algorithms."""

    input_path: Path | str
    output_path: Path
    crs: str
    x_resolution: float
    y_resolution: float
    add_to_project: bool = True


@dataclass(frozen=True)
class AdvancedChmParameters(AdvancedRasterParameters):
    """Advanced CHM parameters exposed through Processing Toolbox."""

    interpolation: Interpolation = "linear"
    interpolate_valid_region: bool = False
    clean_edges: bool = False


@dataclass(frozen=True)
class AdvancedVoxelParameters(AdvancedRasterParameters):
    """Shared voxel settings for PAD/PAI/FHD/canopy cover."""

    voxel_height: float = 1.0
    min_height: float = 0.0
    max_height: float | None = None
    beer_lambert_constant: float = 1.0
    drop_ground: bool = True


@dataclass(frozen=True)
class AdvancedCanopyCoverParameters(AdvancedVoxelParameters):
    """Advanced canopy cover parameters."""

    extinction_coefficient: float = 0.5


@dataclass(frozen=True)
class AdvancedRumpleParameters:
    """Advanced rumple parameters exposed through Processing Toolbox."""

    input_path: Path | str
    output_path: Path
    crs: str
    x_resolution: float
    y_resolution: float
    interpolation: Interpolation = "linear"
    interpolate_valid_region: bool = False
    clean_edges: bool = False
    min_height: float | None = None
    add_to_project: bool = True


@dataclass(frozen=True)
class AdvancedHagParameters:
    """Advanced HAG/normalization parameters."""

    input_path: Path | str
    crs: str
    output_path: Path | None = None
    use_dtm: bool = False
    dtm_path: Path | None = None
    reproject: bool = False
    compress: bool = True


def build_chm_request(params: AdvancedChmParameters) -> ChmRequest:
    """Validate advanced CHM parameters and return an adapter request."""
    _validate_raster_params(params, product="CHM")
    interpolation = _adapter_interpolation(params.interpolation)
    return ChmRequest(
        input_path=params.input_path,
        output_path=params.output_path,
        grid_resolution=params.x_resolution,
        y_resolution=params.y_resolution,
        crs=params.crs,
        interpolation=interpolation,
        interp_valid_region=params.interpolate_valid_region,
        interp_clean_edges=params.clean_edges,
    )


def build_pad_request(params: AdvancedVoxelParameters) -> PadRequest:
    """Validate advanced PAD parameters and return an adapter request."""
    _validate_voxel_params(params, product="PAD")
    return PadRequest(
        input_path=params.input_path,
        output_path=params.output_path,
        grid_resolution=params.x_resolution,
        y_resolution=params.y_resolution,
        voxel_height=params.voxel_height,
        crs=params.crs,
        beer_lambert_constant=params.beer_lambert_constant,
        drop_ground=params.drop_ground,
    )


def build_pai_request(params: AdvancedVoxelParameters) -> PaiRequest:
    """Validate advanced PAI parameters and return an adapter request."""
    _validate_voxel_params(params, product="PAI")
    return PaiRequest(
        input_path=params.input_path,
        output_path=params.output_path,
        grid_resolution=params.x_resolution,
        y_resolution=params.y_resolution,
        voxel_height=params.voxel_height,
        crs=params.crs,
        min_height=params.min_height,
        max_height=params.max_height,
        beer_lambert_constant=params.beer_lambert_constant,
        drop_ground=params.drop_ground,
    )


def build_canopy_cover_request(params: AdvancedCanopyCoverParameters) -> CanopyCoverRequest:
    """Validate advanced canopy cover parameters and return an adapter request."""
    _validate_voxel_params(params, product="Canopy Cover")
    if params.extinction_coefficient < 0:
        raise ProcessingError("Canopy Cover extinction coefficient k must be zero or greater.")
    return CanopyCoverRequest(
        input_path=params.input_path,
        output_path=params.output_path,
        grid_resolution=params.x_resolution,
        y_resolution=params.y_resolution,
        canopy_height_threshold=params.min_height,
        voxel_height=params.voxel_height,
        crs=params.crs,
        extinction_coefficient=params.extinction_coefficient,
        max_height=params.max_height,
        beer_lambert_constant=params.beer_lambert_constant,
        drop_ground=params.drop_ground,
    )


def build_fhd_request(params: AdvancedVoxelParameters) -> FhdRequest:
    """Validate advanced FHD parameters and return an adapter request."""
    _validate_voxel_params(params, product="FHD")
    return FhdRequest(
        input_path=params.input_path,
        output_path=params.output_path,
        grid_resolution=params.x_resolution,
        y_resolution=params.y_resolution,
        voxel_height=params.voxel_height,
        crs=params.crs,
        min_height=params.min_height,
        max_height=params.max_height,
    )


def build_rumple_request(params: AdvancedRumpleParameters) -> RumpleRequest:
    """Validate advanced rumple parameters and return an adapter request."""
    if params.x_resolution <= 0 or params.y_resolution <= 0:
        raise ProcessingError("Rumple X and Y resolution must be greater than zero.")
    if params.min_height is not None and params.min_height < 0:
        raise ProcessingError("Rumple minimum height must be zero or greater.")
    if not params.crs.strip():
        raise ProcessingError("Rumple requires a CRS string such as EPSG:32610.")
    _validate_interpolation(params.interpolation)
    if params.output_path.suffix.lower() != ".csv":
        raise ProcessingError("Advanced Rumple output must be a CSV summary because PyForestScan returns a scalar value.")
    return RumpleRequest(
        input_path=params.input_path,
        output_path=params.output_path,
        grid_resolution=params.x_resolution,
        y_resolution=params.y_resolution,
        crs=params.crs,
        min_height=params.min_height,
        interpolation=_adapter_interpolation(params.interpolation),
        interp_valid_region=params.interpolate_valid_region,
        interp_clean_edges=params.clean_edges,
    )


def build_hag_request(params: AdvancedHagParameters) -> HagNormalizationRequest:
    """Validate HAG settings and return an adapter request."""
    if not params.crs.strip():
        raise ProcessingError("Height normalization requires a CRS string such as EPSG:32610.")
    if params.use_dtm and params.dtm_path is None:
        raise ProcessingError("DTM-backed HAG requires a DTM GeoTIFF path.")
    if params.output_path is not None and params.output_path.suffix.lower() not in {".las", ".laz"}:
        raise ProcessingError("Height normalization output must be LAS or LAZ when writing is requested.")
    return HagNormalizationRequest(
        input_path=params.input_path,
        crs=params.crs,
        output_path=params.output_path,
        use_dtm=params.use_dtm,
        dtm_path=params.dtm_path,
        reproject=params.reproject,
        compress=params.compress,
    )


def result_type_for_product(product: ProductType) -> str:
    """Return the job-style result type used by QGIS raster styling helpers."""
    return {
        ProductType.CHM: "chm_geotiff",
        ProductType.PAD: "pad_geotiff",
        ProductType.PAI: "pai_geotiff",
        ProductType.CANOPY_COVER: "canopy_cover_geotiff",
        ProductType.FHD: "fhd_geotiff",
    }.get(product, "table")


def _validate_raster_params(params: AdvancedRasterParameters, *, product: str) -> None:
    if params.x_resolution <= 0 or params.y_resolution <= 0:
        raise ProcessingError(f"{product} X and Y resolution must be greater than zero.")
    if not params.crs.strip():
        raise ProcessingError(f"{product} requires a CRS string such as EPSG:32610.")
    if params.output_path.suffix.lower() not in {".tif", ".tiff"}:
        raise ProcessingError(f"{product} output must be a GeoTIFF path ending in .tif or .tiff.")


def _validate_voxel_params(params: AdvancedVoxelParameters, *, product: str) -> None:
    _validate_raster_params(params, product=product)
    if params.voxel_height <= 0:
        raise ProcessingError(f"{product} voxel height must be greater than zero.")
    if params.min_height < 0:
        raise ProcessingError(f"{product} minimum height must be zero or greater.")
    if params.max_height is not None and params.max_height <= params.min_height:
        raise ProcessingError(f"{product} maximum height must be greater than minimum height.")
    if params.beer_lambert_constant <= 0:
        raise ProcessingError(f"{product} Beer-Lambert constant must be greater than zero.")


def _validate_interpolation(value: str) -> None:
    if value not in VALID_INTERPOLATION:
        raise ProcessingError(f"Unsupported interpolation method: {value}")


def _adapter_interpolation(value: str) -> str | None:
    _validate_interpolation(value)
    return None if value == "none" else value
