"""QGIS-free request builders for Advanced Processing Toolbox algorithms."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .exceptions import ProcessingError
from .types import (
    CanopyCoverRequest,
    ChmRequest,
    DtmRequest,
    FhdRequest,
    HagNormalizationRequest,
    PadRequest,
    PointCloudPreprocessRequest,
    PointDensityRequest,
    PaiRequest,
    ProductType,
    RumpleRequest,
    VoxelStatRequest,
)

Interpolation = Literal["none", "nearest", "linear", "cubic"]

VALID_INTERPOLATION = ("none", "nearest", "linear", "cubic")
VALID_VOXEL_STATS = ("mean", "sum", "count", "min", "max", "median", "std")
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
    bounds_text: str = ""
    thin_radius: float | None = None
    crop_polygon: str = ""


@dataclass(frozen=True)
class AdvancedDtmParameters:
    """Advanced DTM generation parameters."""

    input_path: Path | str
    output_path: Path
    crs: str
    resolution: float = 2.0
    classify_ground: bool = False
    nodata: float = -9999.0
    add_to_project: bool = True


@dataclass(frozen=True)
class AdvancedPointDensityParameters(AdvancedRasterParameters):
    """Advanced point-density parameters exposed through Processing Toolbox."""

    voxel_height: float = 1.0
    per_area: bool = False
    cell_area: float | None = None


@dataclass(frozen=True)
class AdvancedVoxelStatParameters(AdvancedRasterParameters):
    """Advanced voxel-statistic parameters exposed through Processing Toolbox."""

    voxel_height: float = 1.0
    dimension: str = "HeightAboveGround"
    stat: str = "mean"
    z_index_min: int | None = None
    z_index_max: int | None = None


@dataclass(frozen=True)
class AdvancedPointCloudPreprocessParameters:
    """Advanced point-cloud preprocessing parameters."""

    input_path: Path | str
    output_path: Path
    crs: str
    remove_outliers: bool = False
    outlier_mean_k: int = 8
    outlier_multiplier: float = 3.0
    outlier_remove: bool = False
    classify_ground: bool = False
    smrf_ignore_class: str = "Classification[7:7]"
    smrf_cell: float = 1.0
    smrf_cut: float = 0.0
    smrf_returns: str = "last,only"
    smrf_scalar: float = 1.25
    smrf_slope: float = 0.15
    smrf_threshold: float = 0.5
    smrf_window: float = 18.0
    ground_action: str = "none"
    filter_pointsourceid: bool = False
    pointsource_ids_text: str = ""
    add_hag: bool = False
    hag_method: str | None = None
    dtm_path: Path | None = None
    filter_hag: bool = False
    hag_lower_limit: float = 0.0
    hag_upper_limit: float | None = None
    thin_radius: float | None = None
    voxelgrid_cell: float | None = None
    voxelgrid_mode: str = "first"
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
        bounds=parse_bounds_text(params.bounds_text),
        thin_radius=params.thin_radius,
        crop_polygon=params.crop_polygon.strip() or None,
    )


def build_dtm_request(params: AdvancedDtmParameters) -> DtmRequest:
    """Validate DTM parameters and return an adapter request."""
    if params.resolution <= 0:
        raise ProcessingError("DTM resolution must be greater than zero.")
    if not params.crs.strip():
        raise ProcessingError("DTM requires a CRS string such as EPSG:32610.")
    if params.output_path.suffix.lower() not in {".tif", ".tiff"}:
        raise ProcessingError("DTM output must be a GeoTIFF path ending in .tif or .tiff.")
    return DtmRequest(
        input_path=params.input_path,
        output_path=params.output_path,
        crs=params.crs,
        resolution=params.resolution,
        classify_ground=params.classify_ground,
        nodata=params.nodata,
    )


def build_point_density_request(params: AdvancedPointDensityParameters) -> PointDensityRequest:
    """Validate point-density parameters and return an adapter request."""
    _validate_raster_params(params, product="Point Density")
    if params.voxel_height <= 0:
        raise ProcessingError("Point Density voxel_height must be greater than zero.")
    if params.cell_area is not None and params.cell_area <= 0:
        raise ProcessingError("Point Density cell_area must be greater than zero when provided.")
    return PointDensityRequest(
        input_path=params.input_path,
        output_path=params.output_path,
        grid_resolution=params.x_resolution,
        y_resolution=params.y_resolution,
        voxel_height=params.voxel_height,
        crs=params.crs,
        per_area=params.per_area,
        cell_area=params.cell_area,
    )


def build_voxel_stat_request(params: AdvancedVoxelStatParameters) -> VoxelStatRequest:
    """Validate voxel-statistic parameters and return an adapter request."""
    _validate_raster_params(params, product="Voxel Statistic")
    if params.voxel_height <= 0:
        raise ProcessingError("Voxel Statistic voxel_resolution Z / voxel height must be greater than zero.")
    if not params.dimension.strip():
        raise ProcessingError("Voxel Statistic dimension is required.")
    if params.stat not in VALID_VOXEL_STATS:
        raise ProcessingError(f"Voxel Statistic stat must be one of: {', '.join(VALID_VOXEL_STATS)}.")
    z_index_range: tuple[int, int] | None = None
    if params.z_index_min is not None or params.z_index_max is not None:
        if params.z_index_min is None or params.z_index_max is None:
            raise ProcessingError("Voxel Statistic z_index_range requires both minimum and maximum indexes.")
        if params.z_index_min < 0 or params.z_index_max < 0:
            raise ProcessingError("Voxel Statistic z_index_range indexes must be zero or greater.")
        if params.z_index_max <= params.z_index_min:
            raise ProcessingError("Voxel Statistic z_index_range maximum must be greater than minimum.")
        z_index_range = (params.z_index_min, params.z_index_max)
    return VoxelStatRequest(
        input_path=params.input_path,
        output_path=params.output_path,
        grid_resolution=params.x_resolution,
        y_resolution=params.y_resolution,
        voxel_height=params.voxel_height,
        crs=params.crs,
        dimension=params.dimension.strip(),
        stat=params.stat,
        z_index_range=z_index_range,
    )


def build_point_cloud_preprocess_request(params: AdvancedPointCloudPreprocessParameters) -> PointCloudPreprocessRequest:
    """Validate point-cloud preprocessing parameters and return an adapter request."""
    if not params.crs.strip():
        raise ProcessingError("Point-cloud preprocessing requires a CRS string such as EPSG:32610.")
    if params.output_path.suffix.lower() not in {".las", ".laz"}:
        raise ProcessingError("Point-cloud preprocessing output must end with .las or .laz.")
    if params.outlier_mean_k <= 0:
        raise ProcessingError("Outlier mean_k must be greater than zero.")
    if params.outlier_multiplier <= 0:
        raise ProcessingError("Outlier multiplier must be greater than zero.")
    if params.smrf_cell <= 0:
        raise ProcessingError("SMRF cell must be greater than zero.")
    if params.smrf_scalar <= 0:
        raise ProcessingError("SMRF scalar must be greater than zero.")
    if params.smrf_slope < 0:
        raise ProcessingError("SMRF slope must be zero or greater.")
    if params.smrf_threshold <= 0:
        raise ProcessingError("SMRF threshold must be greater than zero.")
    if params.smrf_window <= 0:
        raise ProcessingError("SMRF window must be greater than zero.")
    pointsource_ids = parse_integer_list(params.pointsource_ids_text, label="PointSourceId")
    if params.filter_pointsourceid and not pointsource_ids:
        raise ProcessingError("PointSourceId filtering requires at least one ID.")
    if params.thin_radius is not None and params.thin_radius <= 0:
        raise ProcessingError("Poisson thinning radius must be greater than zero.")
    if params.voxelgrid_cell is not None and params.voxelgrid_cell <= 0:
        raise ProcessingError("Voxel-grid cell size must be greater than zero.")
    if params.hag_upper_limit is not None and params.hag_upper_limit <= params.hag_lower_limit:
        raise ProcessingError("HAG upper limit must be greater than lower limit.")
    if params.hag_method not in {None, "delaunay", "dtm"}:
        raise ProcessingError("HAG method must be auto, delaunay, or dtm.")
    if params.hag_method == "dtm" and params.add_hag and params.dtm_path is None:
        raise ProcessingError("DTM HAG preprocessing requires a DTM path.")
    if params.ground_action not in {"none", "remove_ground", "select_ground"}:
        raise ProcessingError("Ground action must be none, remove_ground, or select_ground.")
    if params.voxelgrid_mode not in {"first", "last", "center", "nearest"}:
        raise ProcessingError("Voxel-grid mode must be first, last, center, or nearest.")
    values = dict(params.__dict__)
    values.pop("pointsource_ids_text")
    values["pointsource_ids"] = pointsource_ids
    return PointCloudPreprocessRequest(**values)


def parse_integer_list(values_text: str, *, label: str = "value") -> tuple[int, ...]:
    """Parse a comma-separated integer list for expert filter parameters."""
    text = values_text.strip()
    if not text:
        return ()
    values: list[int] = []
    for raw_item in text.split(","):
        item = raw_item.strip()
        if not item:
            continue
        try:
            value = int(item)
        except ValueError as exc:
            raise ProcessingError(f"{label} list contains a non-integer value: {item}") from exc
        if value < 0:
            raise ProcessingError(f"{label} values must be zero or greater.")
        values.append(value)
    return tuple(values)


def parse_bounds_text(bounds_text: str) -> tuple[tuple[float, float], ...] | None:
    """Parse xmin,xmax,ymin,ymax[,zmin,zmax] into PyForestScan read_lidar bounds."""
    text = bounds_text.strip()
    if not text:
        return None
    parts = [float(item.strip()) for item in text.split(",") if item.strip()]
    if len(parts) not in {4, 6}:
        raise ProcessingError("Bounds must contain xmin,xmax,ymin,ymax or xmin,xmax,ymin,ymax,zmin,zmax.")
    xmin, xmax, ymin, ymax = parts[:4]
    if xmax <= xmin or ymax <= ymin:
        raise ProcessingError("Bounds maximum values must be greater than minimum values.")
    bounds: tuple[tuple[float, float], ...] = ((xmin, xmax), (ymin, ymax))
    if len(parts) == 6:
        zmin, zmax = parts[4:]
        if zmax <= zmin:
            raise ProcessingError("Z bounds maximum must be greater than minimum.")
        bounds = bounds + ((zmin, zmax),)
    return bounds


def result_type_for_product(product: ProductType) -> str:
    """Return the job-style result type used by QGIS raster styling helpers."""
    return {
        ProductType.CHM: "chm_geotiff",
        ProductType.PAD: "pad_geotiff",
        ProductType.PAI: "pai_geotiff",
        ProductType.CANOPY_COVER: "canopy_cover_geotiff",
        ProductType.FHD: "fhd_geotiff",
        ProductType.DTM: "dtm_geotiff",
        ProductType.POINT_DENSITY: "point_density_geotiff",
        ProductType.VOXEL_STAT: "voxel_stat_geotiff",
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
