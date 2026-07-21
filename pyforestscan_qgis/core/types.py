"""Typed value objects for the PyForestScan adapter layer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class DatasetFormat(str, Enum):
    """Point cloud formats recognized by the adapter."""

    LAS = "las"
    LAZ = "laz"
    COPC = "copc"
    EPT = "ept"


class ProductType(str, Enum):
    """Product families planned for PyForestScan QGIS."""

    CHM = "chm"
    PAD = "pad"
    PAI = "pai"
    FHD = "fhd"
    CANOPY_COVER = "canopy_cover"
    RUMPLE = "rumple"
    POINT_DENSITY = "point_density"
    VOXEL_STAT = "voxel_stat"
    HAG = "hag"
    DTM = "dtm"
    POINT_CLOUD_PREPROCESS = "point_cloud_preprocess"


class LogLevel(str, Enum):
    """Structured adapter log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ProgressState(str, Enum):
    """Progress lifecycle states for adapter operations."""

    IDLE = "idle"
    RUNNING = "running"
    CANCELED = "canceled"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass(frozen=True)
class Bounds3D:
    """Three-dimensional dataset bounds."""

    min_x: float
    max_x: float
    min_y: float
    max_y: float
    min_z: float | None = None
    max_z: float | None = None

    @property
    def width(self) -> float:
        """Return the X dimension width."""
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        """Return the Y dimension height."""
        return self.max_y - self.min_y

    @property
    def area(self) -> float:
        """Return the XY area, or 0 for invalid extents."""
        return max(0.0, self.width) * max(0.0, self.height)


@dataclass(frozen=True)
class DatasetSource:
    """Validated dataset reference opened by the adapter."""

    path: Path | str
    format: DatasetFormat
    crs: str | None = None
    is_remote: bool = False


@dataclass(frozen=True)
class DatasetValidationResult:
    """Result of validating a dataset path and format."""

    source: DatasetSource | None
    is_valid: bool
    messages: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClassificationCount:
    """Count for a single point classification code."""

    classification: int
    count: int


@dataclass(frozen=True)
class AdapterParameter:
    """Typed key-value parameter reserved for future product requests."""

    name: str
    value: object


@dataclass(frozen=True)
class LogContextItem:
    """Typed key-value context item for structured adapter logs."""

    key: str
    value: object


@dataclass(frozen=True)
class DatasetInspection:
    """Non-output inspection summary for a point cloud dataset."""

    source: DatasetSource
    point_count: int | None
    bounds: Bounds3D | None
    crs: str | None
    dimensions: tuple[str, ...]
    classification_summary: tuple[ClassificationCount, ...]
    point_format: str | None
    estimated_density: float | None
    supported_products: tuple[ProductType, ...]
    metadata_source: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChmRequest:
    """Adapter request for CHM generation."""

    input_path: Path | str
    output_path: Path
    grid_resolution: float
    crs: str
    interpolation: str | None = "linear"
    interp_valid_region: bool = False
    interp_clean_edges: bool = False
    y_resolution: float | None = None
    bounds: tuple[tuple[float, float], ...] | None = None
    crop_polygon: str | None = None


@dataclass(frozen=True)
class ChmResult:
    """Adapter result for a generated CHM GeoTIFF."""

    output_path: Path
    spatial_extent: tuple[float, float, float, float]
    grid_resolution: float
    crs: str


@dataclass(frozen=True)
class CanopyCoverRequest:
    """Adapter request for canopy cover generation."""

    input_path: Path | str
    output_path: Path
    grid_resolution: float
    canopy_height_threshold: float
    crs: str
    voxel_height: float = 1.0
    extinction_coefficient: float = 0.5
    max_height: float | None = None
    beer_lambert_constant: float = 1.0
    drop_ground: bool = True
    y_resolution: float | None = None
    bounds: tuple[tuple[float, float], ...] | None = None
    crop_polygon: str | None = None


@dataclass(frozen=True)
class CanopyCoverResult:
    """Adapter result for a generated canopy cover GeoTIFF."""

    output_path: Path
    spatial_extent: tuple[float, float, float, float]
    grid_resolution: float
    canopy_height_threshold: float
    crs: str


@dataclass(frozen=True)
class PadRequest:
    """Adapter request for PAD generation."""

    input_path: Path | str
    output_path: Path
    grid_resolution: float
    voxel_height: float
    crs: str
    beer_lambert_constant: float = 1.0
    drop_ground: bool = True
    y_resolution: float | None = None
    bounds: tuple[tuple[float, float], ...] | None = None
    crop_polygon: str | None = None


@dataclass(frozen=True)
class PadResult:
    """Adapter result for a generated PAD multi-band GeoTIFF."""

    output_path: Path
    spatial_extent: tuple[float, float, float, float]
    grid_resolution: float
    voxel_height: float
    band_count: int
    crs: str


@dataclass(frozen=True)
class PaiRequest:
    """Adapter request for PAI generation."""

    input_path: Path | str
    output_path: Path
    grid_resolution: float
    voxel_height: float
    crs: str
    min_height: float = 1.0
    max_height: float | None = None
    beer_lambert_constant: float = 1.0
    drop_ground: bool = True
    y_resolution: float | None = None
    bounds: tuple[tuple[float, float], ...] | None = None
    crop_polygon: str | None = None


@dataclass(frozen=True)
class PaiResult:
    """Adapter result for a generated PAI GeoTIFF."""

    output_path: Path
    spatial_extent: tuple[float, float, float, float]
    grid_resolution: float
    voxel_height: float
    crs: str


@dataclass(frozen=True)
class FhdRequest:
    """Adapter request for FHD generation."""

    input_path: Path | str
    output_path: Path
    grid_resolution: float
    voxel_height: float
    crs: str
    min_height: float = 0.0
    max_height: float | None = None
    y_resolution: float | None = None
    bounds: tuple[tuple[float, float], ...] | None = None
    crop_polygon: str | None = None


@dataclass(frozen=True)
class FhdResult:
    """Adapter result for a generated FHD GeoTIFF."""

    output_path: Path
    spatial_extent: tuple[float, float, float, float]
    grid_resolution: float
    voxel_height: float
    crs: str


@dataclass(frozen=True)
class RumpleRequest:
    """Adapter request for rumple index generation."""

    input_path: Path | str
    output_path: Path
    grid_resolution: float
    crs: str
    min_height: float | None = None
    interpolation: str | None = "linear"
    interp_valid_region: bool = False
    interp_clean_edges: bool = False
    y_resolution: float | None = None
    bounds: tuple[tuple[float, float], ...] | None = None
    crop_polygon: str | None = None


@dataclass(frozen=True)
class RumpleResult:
    """Adapter result for a scalar rumple index table."""

    output_path: Path
    rumple_index: float
    spatial_extent: tuple[float, float, float, float]
    grid_resolution: float
    crs: str


@dataclass(frozen=True)
class HagNormalizationRequest:
    """Adapter request for HAG-enabled point-cloud reading and optional LAS/LAZ export."""

    input_path: Path | str
    crs: str
    output_path: Path | None = None
    use_dtm: bool = False
    dtm_path: Path | None = None
    reproject: bool = False
    compress: bool = True
    bounds: tuple[tuple[float, float], ...] | None = None
    thin_radius: float | None = None
    crop_polygon: str | None = None


@dataclass(frozen=True)
class HagNormalizationResult:
    """Adapter result for HAG-enabled point-cloud handling."""

    output_path: Path | None
    point_count: int | None
    crs: str
    written: bool
    limitation: str | None = None


@dataclass(frozen=True)
class DtmRequest:
    """Adapter request for DTM generation from ground-classified points."""

    input_path: Path | str
    output_path: Path
    crs: str
    resolution: float = 2.0
    classify_ground: bool = False
    nodata: float = -9999.0
    bounds: tuple[tuple[float, float], ...] | None = None
    crop_polygon: str | None = None


@dataclass(frozen=True)
class DtmResult:
    """Adapter result for a generated DTM GeoTIFF."""

    output_path: Path
    spatial_extent: tuple[float, float, float, float]
    resolution: float
    crs: str


@dataclass(frozen=True)
class PointDensityRequest:
    """Adapter request for point-density raster generation."""

    input_path: Path | str
    output_path: Path
    grid_resolution: float
    voxel_height: float
    crs: str
    per_area: bool = False
    cell_area: float | None = None
    y_resolution: float | None = None
    bounds: tuple[tuple[float, float], ...] | None = None
    crop_polygon: str | None = None


@dataclass(frozen=True)
class PointDensityResult:
    """Adapter result for a point-density GeoTIFF."""

    output_path: Path
    spatial_extent: tuple[float, float, float, float]
    grid_resolution: float
    voxel_height: float
    crs: str


@dataclass(frozen=True)
class VoxelStatRequest:
    """Adapter request for voxel-statistic raster generation."""

    input_path: Path | str
    output_path: Path
    grid_resolution: float
    voxel_height: float
    crs: str
    dimension: str
    stat: str
    z_index_range: tuple[int, int] | None = None
    y_resolution: float | None = None
    bounds: tuple[tuple[float, float], ...] | None = None
    crop_polygon: str | None = None


@dataclass(frozen=True)
class VoxelStatResult:
    """Adapter result for a voxel-statistic GeoTIFF."""

    output_path: Path
    spatial_extent: tuple[float, float, float, float]
    grid_resolution: float
    voxel_height: float
    dimension: str
    stat: str
    crs: str


@dataclass(frozen=True)
class PointCloudPreprocessRequest:
    """Adapter request for safe point-cloud filter/preprocess workflows."""

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
    pointsource_ids: tuple[int, ...] = ()
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


@dataclass(frozen=True)
class PointCloudPreprocessResult:
    """Adapter result for a written preprocessed point cloud."""

    output_path: Path
    point_count: int | None
    crs: str
    operations: tuple[str, ...]


@dataclass(frozen=True)
class ProductRequest:
    """Future product request placeholder for adapter architecture."""

    products: tuple[ProductType, ...]
    parameters: tuple[AdapterParameter, ...] = ()


@dataclass(frozen=True)
class ProductResult:
    """Future product result placeholder for adapter architecture."""

    products: tuple[ProductType, ...]
    outputs: tuple[Path, ...] = ()
    messages: tuple[str, ...] = ()


@dataclass(frozen=True)
class LogRecord:
    """Structured adapter log record."""

    level: LogLevel
    message: str
    context: tuple[LogContextItem, ...] = ()


@dataclass(frozen=True)
class ProgressSnapshot:
    """Immutable snapshot of adapter progress."""

    state: ProgressState
    percent: float
    message: str = ""
    canceled: bool = False
