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


@dataclass(frozen=True)
class RumpleResult:
    """Adapter result for a scalar rumple index table."""

    output_path: Path
    rumple_index: float
    spatial_extent: tuple[float, float, float, float]
    grid_resolution: float
    crs: str


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
