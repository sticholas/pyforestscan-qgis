"""Architecture-only adapter boundary around PyForestScan and PDAL.

This module validates and inspects datasets, exposes typed results, and
centralizes PyForestScan imports behind a plugin-owned API. CHM, canopy cover,
PAD, PAI, FHD, and rumple are implemented for single-dataset workflows.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .config import AdapterConfig, DatasetOpenOptions, InspectionOptions
from .dependency_check import EnvironmentReport, collect_environment_report
from .exceptions import AdapterError, DatasetError, EnvironmentError, ProcessingError
from .types import (
    Bounds3D,
    CanopyCoverRequest,
    CanopyCoverResult,
    ChmRequest,
    ChmResult,
    ClassificationCount,
    DatasetFormat,
    DatasetInspection,
    DatasetSource,
    DatasetValidationResult,
    DtmRequest,
    DtmResult,
    LogContextItem,
    LogLevel,
    LogRecord,
    FhdRequest,
    FhdResult,
    HagNormalizationRequest,
    HagNormalizationResult,
    PadRequest,
    PadResult,
    PointCloudPreprocessRequest,
    PointCloudPreprocessResult,
    PointDensityRequest,
    PointDensityResult,
    PaiRequest,
    PaiResult,
    RumpleRequest,
    RumpleResult,
    VoxelStatRequest,
    VoxelStatResult,
    ProductRequest,
    ProductResult,
    ProductType,
    ProgressSnapshot,
    ProgressState,
)

LogSink = Callable[[LogRecord], None]

POINT_CLOUD_EXTENSIONS = {
    ".las": DatasetFormat.LAS,
    ".laz": DatasetFormat.LAZ,
    ".copc": DatasetFormat.COPC,
    ".copc.laz": DatasetFormat.COPC,
}

DEFAULT_PRODUCTS = (
    ProductType.CHM,
    ProductType.PAD,
    ProductType.PAI,
    ProductType.FHD,
    ProductType.CANOPY_COVER,
    ProductType.RUMPLE,
    ProductType.POINT_DENSITY,
    ProductType.VOXEL_STAT,
)


class AdapterProgress:
    """Small progress interface independent of QGIS Processing feedback."""

    def __init__(self) -> None:
        """Create an idle progress tracker."""
        self._snapshot = ProgressSnapshot(state=ProgressState.IDLE, percent=0.0)
        self._canceled = False

    def start(self, message: str) -> None:
        """Mark an operation as running."""
        self._snapshot = ProgressSnapshot(
            state=ProgressState.RUNNING,
            percent=0.0,
            message=message,
            canceled=self._canceled,
        )

    def update(self, percent: float, message: str = "") -> None:
        """Update progress percentage and optional message."""
        bounded = min(100.0, max(0.0, float(percent)))
        state = ProgressState.CANCELED if self._canceled else ProgressState.RUNNING
        self._snapshot = ProgressSnapshot(
            state=state,
            percent=bounded,
            message=message,
            canceled=self._canceled,
        )

    def complete(self, message: str = "") -> None:
        """Mark the operation as complete."""
        self._snapshot = ProgressSnapshot(
            state=ProgressState.COMPLETE,
            percent=100.0,
            message=message,
            canceled=self._canceled,
        )

    def fail(self, message: str) -> None:
        """Mark the operation as failed."""
        self._snapshot = ProgressSnapshot(
            state=ProgressState.FAILED,
            percent=self._snapshot.percent,
            message=message,
            canceled=self._canceled,
        )

    def cancel(self) -> None:
        """Request cancellation for future adapter work."""
        self._canceled = True
        self._snapshot = ProgressSnapshot(
            state=ProgressState.CANCELED,
            percent=self._snapshot.percent,
            message=self._snapshot.message,
            canceled=True,
        )

    def snapshot(self) -> ProgressSnapshot:
        """Return the current immutable progress snapshot."""
        return self._snapshot


class PyForestScanAdapter:
    """Plugin-owned adapter that isolates QGIS from PyForestScan internals."""

    def __init__(
        self,
        config: AdapterConfig | None = None,
        log_sink: LogSink | None = None,
    ) -> None:
        """Create an adapter with immutable configuration and optional logging."""
        self.config = config or AdapterConfig()
        self._log_sink = log_sink
        self._progress = AdapterProgress()
        self._open_dataset: DatasetSource | None = None

    def check_environment(self) -> EnvironmentReport:
        """Return the existing structured dependency environment report."""
        self._log(LogLevel.INFO, "Checking PyForestScan runtime environment")
        report = collect_environment_report()
        if report.readiness.value == "NOT READY":
            self._log(LogLevel.ERROR, "PyForestScan runtime environment is not ready")
        return report

    def open_dataset(
        self,
        path: str | Path,
        options: DatasetOpenOptions | None = None,
    ) -> DatasetSource:
        """Validate and remember a dataset reference without reading products."""
        result = self.validate_dataset(path, options)
        if not result.is_valid or result.source is None:
            raise DatasetError("; ".join(result.messages) or "Dataset is not valid")
        self._open_dataset = result.source
        self._log(LogLevel.INFO, "Opened dataset reference", path=str(path), format=result.source.format.value)
        return result.source

    def validate_dataset(
        self,
        path: str | Path,
        options: DatasetOpenOptions | None = None,
    ) -> DatasetValidationResult:
        """Validate dataset path, URL status, and supported format."""
        opts = options or DatasetOpenOptions(
            crs=self.config.default_crs,
            allow_remote=self.config.allow_remote_ept,
        )
        source_text = str(path)
        is_remote = _is_remote(source_text)
        dataset_format = _detect_format(source_text)
        messages: list[str] = []

        if dataset_format is None:
            messages.append(
                "Unsupported dataset format. Expected LAS, LAZ, COPC, COPC LAZ, or ept.json."
            )

        if is_remote:
            if not opts.allow_remote:
                messages.append("Remote datasets are disabled by adapter configuration.")
            if dataset_format is not DatasetFormat.EPT:
                messages.append("Only EPT JSON remote datasets are supported for inspection.")
        else:
            local_path = Path(source_text)
            if not local_path.is_file():
                messages.append(f"Dataset does not exist: {local_path}")

        if messages or dataset_format is None:
            return DatasetValidationResult(source=None, is_valid=False, messages=tuple(messages))

        return DatasetValidationResult(
            source=DatasetSource(
                path=source_text if is_remote else Path(source_text),
                format=dataset_format,
                crs=opts.crs,
                is_remote=is_remote,
            ),
            is_valid=True,
            messages=("Dataset is valid.",),
        )

    def inspect_dataset(
        self,
        dataset: DatasetSource | str | Path | None = None,
        options: InspectionOptions | None = None,
    ) -> DatasetInspection:
        """Inspect dataset metadata without creating scientific outputs."""
        source = self._coerce_dataset(dataset)
        opts = options or InspectionOptions(
            include_classification_summary=self.config.inspect_classifications,
            max_points_for_classification_summary=self.config.max_points_for_classification_summary,
        )
        self._progress.start("Inspecting dataset")
        self._log(LogLevel.INFO, "Inspecting dataset", path=str(source.path), format=source.format.value)

        try:
            if source.format is DatasetFormat.EPT:
                inspection = self._inspect_ept(source, opts)
            else:
                inspection = self._inspect_with_pdal(source, opts)
        except AdapterError:
            self._progress.fail("Dataset inspection failed")
            raise
        except Exception as exc:  # noqa: BLE001 - convert dependency errors at boundary.
            self._progress.fail("Dataset inspection failed")
            raise DatasetError(f"Dataset inspection failed: {exc}") from exc

        self._progress.complete("Dataset inspection complete")
        return inspection

    def create_chm(self, request: ChmRequest) -> ChmResult:
        """Generate a CHM GeoTIFF through PyForestScan.

        The adapter owns all direct PyForestScan imports and converts dependency or
        processing failures into plugin-owned ``ProcessingError`` exceptions.
        """
        if request.grid_resolution <= 0:
            raise ProcessingError("CHM X resolution must be greater than zero.")
        if request.y_resolution is not None and request.y_resolution <= 0:
            raise ProcessingError("CHM Y resolution must be greater than zero.")
        if not request.crs:
            raise ProcessingError("CHM generation requires a dataset CRS.")
        output_path = Path(request.output_path)
        _validate_output_path(output_path)
        self._progress.start("Reading lidar for CHM")
        self._log(LogLevel.INFO, "Starting CHM generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            handlers = _import_required("pyforestscan.handlers", ProcessingError)
            point_cloud = handlers.read_lidar(str(request.input_path), request.crs, hag=True)
            if point_cloud is None:
                raise ProcessingError("PyForestScan returned no point data for CHM generation.")
            self._progress.update(35, "Point cloud loaded")
            point_array = _merge_point_cloud_arrays(point_cloud)
            names = getattr(point_array.dtype, "names", ()) or ()
            required = {"X", "Y", "HeightAboveGround"}
            missing = sorted(required.difference(names))
            if missing:
                raise ProcessingError(f"CHM input is missing required dimensions: {', '.join(missing)}")
            chm, extent = pyforestscan.calculate_chm(
                point_array,
                _xy_resolution(request.grid_resolution, request.y_resolution),
                interpolation=request.interpolation,
                interp_valid_region=request.interp_valid_region,
                interp_clean_edges=request.interp_clean_edges,
            )
            self._progress.update(70, "CHM array calculated")
            handlers.create_geotiff(chm, str(output_path), request.crs, extent)
            _validate_created_output(output_path)
            self._progress.complete("CHM GeoTIFF created")
            self._log(LogLevel.INFO, "CHM generation complete", output=str(output_path))
            return ChmResult(
                output_path=output_path,
                spatial_extent=tuple(float(value) for value in extent),
                grid_resolution=request.grid_resolution,
                crs=request.crs,
            )
        except ProcessingError:
            self._progress.fail("CHM generation failed")
            raise
        except Exception as exc:  # noqa: BLE001 - convert dependency errors at boundary.
            self._progress.fail("CHM generation failed")
            raise ProcessingError(f"CHM generation failed: {exc}") from exc

    def create_pad(self, request: PadRequest) -> PadResult:
        """Generate PAD as a height-binned multi-band GeoTIFF."""
        if request.grid_resolution <= 0:
            raise ProcessingError("PAD X resolution must be greater than zero.")
        if request.y_resolution is not None and request.y_resolution <= 0:
            raise ProcessingError("PAD Y resolution must be greater than zero.")
        if request.voxel_height <= 0:
            raise ProcessingError("PAD voxel height must be greater than zero.")
        if request.beer_lambert_constant <= 0:
            raise ProcessingError("PAD Beer-Lambert constant must be greater than zero.")
        if not request.crs:
            raise ProcessingError("PAD generation requires a dataset CRS.")
        output_path = Path(request.output_path)
        _validate_output_path(output_path)
        self._progress.start("Reading lidar for PAD")
        self._log(LogLevel.INFO, "Starting PAD generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            point_array = self._read_hag_point_array(request.input_path, request.crs, "PAD")
            voxel_returns, extent = pyforestscan.assign_voxels(
                point_array,
                (*_xy_resolution(request.grid_resolution, request.y_resolution), request.voxel_height),
            )
            self._progress.update(50, "Voxel returns calculated")
            pad = pyforestscan.calculate_pad(
                voxel_returns,
                voxel_height=request.voxel_height,
                beer_lambert_constant=request.beer_lambert_constant,
                drop_ground=request.drop_ground,
            )
            self._progress.update(75, "PAD array calculated")
            _write_multiband_geotiff(pad, output_path, request.crs, extent)
            _validate_created_output(output_path)
            self._progress.complete("PAD GeoTIFF created")
            self._log(LogLevel.INFO, "PAD generation complete", output=str(output_path), bands=pad.shape[2])
            return PadResult(
                output_path=output_path,
                spatial_extent=tuple(float(value) for value in extent),
                grid_resolution=request.grid_resolution,
                voxel_height=request.voxel_height,
                band_count=int(pad.shape[2]),
                crs=request.crs,
            )
        except ProcessingError:
            self._progress.fail("PAD generation failed")
            raise
        except Exception as exc:  # noqa: BLE001 - convert dependency errors at boundary.
            self._progress.fail("PAD generation failed")
            raise ProcessingError(f"PAD generation failed: {exc}") from exc

    def create_pai(self, request: PaiRequest) -> PaiResult:
        """Generate a PAI GeoTIFF through PyForestScan."""
        if request.grid_resolution <= 0:
            raise ProcessingError("PAI X resolution must be greater than zero.")
        if request.y_resolution is not None and request.y_resolution <= 0:
            raise ProcessingError("PAI Y resolution must be greater than zero.")
        if request.voxel_height <= 0:
            raise ProcessingError("PAI voxel height must be greater than zero.")
        if request.min_height < 0:
            raise ProcessingError("PAI minimum height must be zero or greater.")
        if request.max_height is not None and request.max_height <= request.min_height:
            raise ProcessingError("PAI maximum height must be greater than minimum height.")
        if not request.crs:
            raise ProcessingError("PAI generation requires a dataset CRS.")
        output_path = Path(request.output_path)
        _validate_output_path(output_path)
        self._progress.start("Reading lidar for PAI")
        self._log(LogLevel.INFO, "Starting PAI generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            handlers = _import_required("pyforestscan.handlers", ProcessingError)
            point_array = self._read_hag_point_array(request.input_path, request.crs, "PAI")
            voxel_returns, extent = pyforestscan.assign_voxels(
                point_array,
                (*_xy_resolution(request.grid_resolution, request.y_resolution), request.voxel_height),
            )
            self._progress.update(45, "Voxel returns calculated")
            pad = pyforestscan.calculate_pad(
                voxel_returns,
                voxel_height=request.voxel_height,
                beer_lambert_constant=request.beer_lambert_constant,
                drop_ground=request.drop_ground,
            )
            self._progress.update(65, "Internal PAD prerequisite calculated")
            pai = pyforestscan.calculate_pai(
                pad,
                request.voxel_height,
                min_height=request.min_height,
                max_height=request.max_height,
            )
            self._progress.update(80, "PAI array calculated")
            handlers.create_geotiff(pai, str(output_path), request.crs, extent)
            _validate_created_output(output_path)
            self._progress.complete("PAI GeoTIFF created")
            self._log(LogLevel.INFO, "PAI generation complete", output=str(output_path))
            return PaiResult(
                output_path=output_path,
                spatial_extent=tuple(float(value) for value in extent),
                grid_resolution=request.grid_resolution,
                voxel_height=request.voxel_height,
                crs=request.crs,
            )
        except ProcessingError:
            self._progress.fail("PAI generation failed")
            raise
        except Exception as exc:  # noqa: BLE001 - convert dependency errors at boundary.
            self._progress.fail("PAI generation failed")
            raise ProcessingError(f"PAI generation failed: {exc}") from exc

    def create_fhd(self, request: FhdRequest) -> FhdResult:
        """Generate FHD as a single-band GeoTIFF through PyForestScan."""
        if request.grid_resolution <= 0:
            raise ProcessingError("FHD X resolution must be greater than zero.")
        if request.y_resolution is not None and request.y_resolution <= 0:
            raise ProcessingError("FHD Y resolution must be greater than zero.")
        if request.voxel_height <= 0:
            raise ProcessingError("FHD voxel height must be greater than zero.")
        if request.min_height < 0:
            raise ProcessingError("FHD minimum height must be zero or greater.")
        if request.max_height is not None and request.max_height <= request.min_height:
            raise ProcessingError("FHD maximum height must be greater than minimum height.")
        if not request.crs:
            raise ProcessingError("FHD generation requires a dataset CRS.")
        output_path = Path(request.output_path)
        _validate_output_path(output_path)
        self._progress.start("Reading lidar for FHD")
        self._log(LogLevel.INFO, "Starting FHD generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            handlers = _import_required("pyforestscan.handlers", ProcessingError)
            point_array = self._read_hag_point_array(request.input_path, request.crs, "FHD")
            voxel_returns, extent = pyforestscan.assign_voxels(
                point_array,
                (*_xy_resolution(request.grid_resolution, request.y_resolution), request.voxel_height),
            )
            self._progress.update(50, "Voxel returns calculated")
            fhd = pyforestscan.calculate_fhd(
                voxel_returns,
                voxel_height=request.voxel_height,
                min_height=request.min_height,
                max_height=request.max_height,
            )
            self._progress.update(80, "FHD array calculated")
            handlers.create_geotiff(fhd, str(output_path), request.crs, extent)
            _validate_created_output(output_path)
            self._progress.complete("FHD GeoTIFF created")
            self._log(LogLevel.INFO, "FHD generation complete", output=str(output_path))
            return FhdResult(
                output_path=output_path,
                spatial_extent=tuple(float(value) for value in extent),
                grid_resolution=request.grid_resolution,
                voxel_height=request.voxel_height,
                crs=request.crs,
            )
        except ProcessingError:
            self._progress.fail("FHD generation failed")
            raise
        except Exception as exc:  # noqa: BLE001 - convert dependency errors at boundary.
            self._progress.fail("FHD generation failed")
            raise ProcessingError(f"FHD generation failed: {exc}") from exc

    def create_rumple(self, request: RumpleRequest) -> RumpleResult:
        """Generate scalar rumple index and write a CSV summary."""
        if request.grid_resolution <= 0:
            raise ProcessingError("Rumple X resolution must be greater than zero.")
        if request.y_resolution is not None and request.y_resolution <= 0:
            raise ProcessingError("Rumple Y resolution must be greater than zero.")
        if request.min_height is not None and request.min_height < 0:
            raise ProcessingError("Rumple minimum height must be zero or greater.")
        if not request.crs:
            raise ProcessingError("Rumple generation requires a dataset CRS.")
        output_path = Path(request.output_path)
        _validate_csv_output_path(output_path)
        self._progress.start("Reading lidar for rumple")
        self._log(LogLevel.INFO, "Starting rumple generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            point_array = self._read_hag_point_array(request.input_path, request.crs, "rumple")
            chm, extent = pyforestscan.calculate_chm(
                point_array,
                _xy_resolution(request.grid_resolution, request.y_resolution),
                interpolation=request.interpolation,
                interp_valid_region=request.interp_valid_region,
                interp_clean_edges=request.interp_clean_edges,
            )
            self._progress.update(65, "Internal CHM prerequisite calculated")
            rumple_index = float(pyforestscan.calculate_rumple(
                chm,
                _xy_resolution(request.grid_resolution, request.y_resolution),
                min_height=request.min_height,
            ))
            self._progress.update(85, "Rumple index calculated")
            _write_rumple_csv(output_path, rumple_index, request, extent)
            _validate_created_output(output_path)
            self._progress.complete("Rumple summary created")
            self._log(LogLevel.INFO, "Rumple generation complete", output=str(output_path), rumple_index=rumple_index)
            return RumpleResult(
                output_path=output_path,
                rumple_index=rumple_index,
                spatial_extent=tuple(float(value) for value in extent),
                grid_resolution=request.grid_resolution,
                crs=request.crs,
            )
        except ProcessingError:
            self._progress.fail("Rumple generation failed")
            raise
        except Exception as exc:  # noqa: BLE001 - convert dependency errors at boundary.
            self._progress.fail("Rumple generation failed")
            raise ProcessingError(f"Rumple generation failed: {exc}") from exc

    def create_canopy_cover(self, request: CanopyCoverRequest) -> CanopyCoverResult:
        """Generate a canopy cover GeoTIFF through PyForestScan.

        PAD is computed only as an internal prerequisite. The adapter does not
        expose PAD as a product in this phase.
        """
        if request.grid_resolution <= 0:
            raise ProcessingError("Canopy cover X resolution must be greater than zero.")
        if request.y_resolution is not None and request.y_resolution <= 0:
            raise ProcessingError("Canopy cover Y resolution must be greater than zero.")
        if request.voxel_height <= 0:
            raise ProcessingError("Canopy cover voxel height must be greater than zero.")
        if request.canopy_height_threshold < 0:
            raise ProcessingError("Canopy cover height threshold must be zero or greater.")
        if request.extinction_coefficient < 0:
            raise ProcessingError("Canopy cover extinction coefficient must be zero or greater.")
        if request.beer_lambert_constant <= 0:
            raise ProcessingError("Canopy cover Beer-Lambert constant must be greater than zero.")
        if request.max_height is not None and request.max_height <= request.canopy_height_threshold:
            raise ProcessingError("Canopy cover maximum height must be greater than the minimum height threshold.")
        if not request.crs:
            raise ProcessingError("Canopy cover generation requires a dataset CRS.")
        output_path = Path(request.output_path)
        _validate_output_path(output_path)
        self._progress.start("Reading lidar for canopy cover")
        self._log(LogLevel.INFO, "Starting canopy cover generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            handlers = _import_required("pyforestscan.handlers", ProcessingError)
            point_array = self._read_hag_point_array(request.input_path, request.crs, "canopy cover")
            voxel_returns, extent = pyforestscan.assign_voxels(
                point_array,
                (*_xy_resolution(request.grid_resolution, request.y_resolution), request.voxel_height),
            )
            self._progress.update(45, "Voxel returns calculated")
            pad = pyforestscan.calculate_pad(
                voxel_returns,
                voxel_height=request.voxel_height,
                beer_lambert_constant=request.beer_lambert_constant,
                drop_ground=request.drop_ground,
            )
            self._progress.update(65, "Internal PAD prerequisite calculated")
            canopy_cover = pyforestscan.calculate_canopy_cover(
                pad,
                request.voxel_height,
                min_height=request.canopy_height_threshold,
                max_height=request.max_height,
                k=request.extinction_coefficient,
            )
            self._progress.update(80, "Canopy cover array calculated")
            handlers.create_geotiff(canopy_cover, str(output_path), request.crs, extent)
            _validate_created_output(output_path)
            self._progress.complete("Canopy cover GeoTIFF created")
            self._log(LogLevel.INFO, "Canopy cover generation complete", output=str(output_path))
            return CanopyCoverResult(
                output_path=output_path,
                spatial_extent=tuple(float(value) for value in extent),
                grid_resolution=request.grid_resolution,
                canopy_height_threshold=request.canopy_height_threshold,
                crs=request.crs,
            )
        except ProcessingError:
            self._progress.fail("Canopy cover generation failed")
            raise
        except Exception as exc:  # noqa: BLE001 - convert dependency errors at boundary.
            self._progress.fail("Canopy cover generation failed")
            raise ProcessingError(f"Canopy cover generation failed: {exc}") from exc

    def create_point_density(self, request: PointDensityRequest) -> PointDensityResult:
        """Generate a point-density GeoTIFF through PyForestScan calculate_point_density."""
        if request.grid_resolution <= 0:
            raise ProcessingError("Point Density X resolution must be greater than zero.")
        if request.y_resolution is not None and request.y_resolution <= 0:
            raise ProcessingError("Point Density Y resolution must be greater than zero.")
        if request.voxel_height <= 0:
            raise ProcessingError("Point Density voxel_height must be greater than zero.")
        if request.cell_area is not None and request.cell_area <= 0:
            raise ProcessingError("Point Density cell_area must be greater than zero when provided.")
        if not request.crs:
            raise ProcessingError("Point Density generation requires a dataset CRS.")
        output_path = Path(request.output_path)
        _validate_output_path(output_path)
        self._progress.start("Reading lidar for point density")
        self._log(LogLevel.INFO, "Starting point density generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            handlers = _import_required("pyforestscan.handlers", ProcessingError)
            point_array = self._read_hag_point_array(request.input_path, request.crs, "point density")
            x_resolution, y_resolution = _xy_resolution(request.grid_resolution, request.y_resolution)
            voxel_returns, extent = pyforestscan.assign_voxels(point_array, (x_resolution, y_resolution, request.voxel_height))
            self._progress.update(55, "Voxel returns calculated")
            cell_area = request.cell_area if request.cell_area is not None else x_resolution * y_resolution
            point_density = pyforestscan.calculate_point_density(
                voxel_returns,
                per_area=request.per_area,
                cell_area=cell_area,
            )
            self._progress.update(80, "Point density array calculated")
            handlers.create_geotiff(point_density, str(output_path), request.crs, extent)
            _validate_created_output(output_path)
            self._progress.complete("Point Density GeoTIFF created")
            return PointDensityResult(
                output_path=output_path,
                spatial_extent=tuple(float(value) for value in extent),
                grid_resolution=request.grid_resolution,
                voxel_height=request.voxel_height,
                crs=request.crs,
            )
        except ProcessingError:
            self._progress.fail("Point Density generation failed")
            raise
        except Exception as exc:  # noqa: BLE001 - convert dependency errors at boundary.
            self._progress.fail("Point Density generation failed")
            raise ProcessingError(f"Point Density generation failed: {exc}") from exc

    def create_voxel_stat(self, request: VoxelStatRequest) -> VoxelStatResult:
        """Generate a voxel-statistic GeoTIFF through PyForestScan calculate_voxel_stat."""
        if request.grid_resolution <= 0:
            raise ProcessingError("Voxel Statistic X resolution must be greater than zero.")
        if request.y_resolution is not None and request.y_resolution <= 0:
            raise ProcessingError("Voxel Statistic Y resolution must be greater than zero.")
        if request.voxel_height <= 0:
            raise ProcessingError("Voxel Statistic voxel_resolution Z / voxel height must be greater than zero.")
        if not request.dimension.strip():
            raise ProcessingError("Voxel Statistic dimension is required.")
        if request.stat not in {"mean", "sum", "count", "min", "max", "median", "std"}:
            raise ProcessingError("Voxel Statistic stat must be one of: mean, sum, count, min, max, median, std.")
        if request.z_index_range is not None:
            start, stop = request.z_index_range
            if start < 0 or stop <= start:
                raise ProcessingError("Voxel Statistic z_index_range must be an increasing pair of non-negative indexes.")
        if not request.crs:
            raise ProcessingError("Voxel Statistic generation requires a dataset CRS.")
        output_path = Path(request.output_path)
        _validate_output_path(output_path)
        self._progress.start("Reading lidar for voxel statistic")
        self._log(LogLevel.INFO, "Starting voxel statistic generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            handlers = _import_required("pyforestscan.handlers", ProcessingError)
            point_array = self._read_hag_point_array(request.input_path, request.crs, "voxel statistic")
            names = getattr(point_array.dtype, "names", ()) or ()
            if request.dimension not in names:
                raise ProcessingError(f"Voxel Statistic input is missing requested dimension: {request.dimension}")
            voxel_resolution = (*_xy_resolution(request.grid_resolution, request.y_resolution), request.voxel_height)
            voxel_stat, extent = pyforestscan.calculate_voxel_stat(
                point_array,
                voxel_resolution,
                request.dimension,
                request.stat,
                z_index_range=request.z_index_range,
            )
            self._progress.update(80, "Voxel statistic array calculated")
            handlers.create_geotiff(voxel_stat, str(output_path), request.crs, extent)
            _validate_created_output(output_path)
            self._progress.complete("Voxel Statistic GeoTIFF created")
            return VoxelStatResult(
                output_path=output_path,
                spatial_extent=tuple(float(value) for value in extent),
                grid_resolution=request.grid_resolution,
                voxel_height=request.voxel_height,
                dimension=request.dimension,
                stat=request.stat,
                crs=request.crs,
            )
        except ProcessingError:
            self._progress.fail("Voxel Statistic generation failed")
            raise
        except Exception as exc:  # noqa: BLE001 - convert dependency errors at boundary.
            self._progress.fail("Voxel Statistic generation failed")
            raise ProcessingError(f"Voxel Statistic generation failed: {exc}") from exc


    def normalize_heights(self, request: HagNormalizationRequest) -> HagNormalizationResult:
        """Read lidar with HeightAboveGround and optionally write LAS/LAZ output.

        PyForestScan exposes HAG through ``handlers.read_lidar(..., hag=True)`` and
        a generic ``handlers.write_las`` writer. The adapter uses that public path
        when an output point-cloud path is supplied; otherwise it reports the
        point count and limitation without inventing a normalized output.
        """
        if not request.crs:
            raise ProcessingError("Height normalization requires a dataset CRS.")
        if request.use_dtm and request.dtm_path is None:
            raise ProcessingError("DTM-backed HAG requires a DTM raster path.")
        if request.output_path is not None:
            _validate_las_output_path(Path(request.output_path))
        self._progress.start("Reading lidar with HeightAboveGround")
        self._log(LogLevel.INFO, "Starting HAG normalization", input=str(request.input_path))
        try:
            handlers = _import_required("pyforestscan.handlers", ProcessingError)
            point_cloud = handlers.read_lidar(
                str(request.input_path),
                request.crs,
                bounds=request.bounds,
                thin_radius=request.thin_radius,
                hag=not request.use_dtm,
                hag_dtm=request.use_dtm,
                dtm=str(request.dtm_path) if request.dtm_path is not None else None,
                crop_poly=bool(request.crop_polygon),
                poly=request.crop_polygon,
                reproject=request.reproject,
            )
            if point_cloud is None:
                raise ProcessingError("PyForestScan returned no point data for HAG normalization.")
            point_count = _point_count_from_point_cloud(point_cloud)
            self._progress.update(70, "Point cloud read with HAG")
            output_path = Path(request.output_path) if request.output_path is not None else None
            if output_path is not None:
                handlers.write_las(point_cloud, str(output_path), srs=request.crs, compress=request.compress)
                _validate_created_output(output_path)
                self._progress.complete("HAG-enabled point cloud written")
                return HagNormalizationResult(output_path=output_path, point_count=point_count, crs=request.crs, written=True)
            self._progress.complete("HAG available in memory")
            return HagNormalizationResult(
                output_path=None,
                point_count=point_count,
                crs=request.crs,
                written=False,
                limitation="PyForestScan HAG is primarily an in-memory read option; provide LAS/LAZ output to rewrite a point cloud via handlers.write_las.",
            )
        except ProcessingError:
            self._progress.fail("HAG normalization failed")
            raise
        except Exception as exc:  # noqa: BLE001 - convert dependency errors at boundary.
            self._progress.fail("HAG normalization failed")
            raise ProcessingError(f"HAG normalization failed: {exc}") from exc


    def generate_dtm(self, request: DtmRequest) -> DtmResult:
        """Generate a DTM GeoTIFF from ground-classified lidar points."""
        if request.resolution <= 0:
            raise ProcessingError("DTM resolution must be greater than zero.")
        if not request.crs:
            raise ProcessingError("DTM generation requires a dataset CRS.")
        output_path = Path(request.output_path)
        _validate_output_path(output_path)
        self._progress.start("Reading lidar for DTM")
        self._log(LogLevel.INFO, "Starting DTM generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            handlers = _import_required("pyforestscan.handlers", ProcessingError)
            filters = _import_required("pyforestscan.filters", ProcessingError)
            point_cloud = handlers.read_lidar(str(request.input_path), request.crs, hag=False)
            if point_cloud is None:
                raise ProcessingError("PyForestScan returned no point data for DTM generation.")
            self._progress.update(30, "Point cloud loaded")
            arrays = filters.classify_ground_points(point_cloud) if request.classify_ground else point_cloud
            ground_arrays = filters.filter_select_ground(arrays)
            ground_points = _merge_point_cloud_arrays(ground_arrays)
            self._progress.update(60, "Ground points selected")
            dtm, extent = pyforestscan.generate_dtm(ground_points, resolution=request.resolution)
            self._progress.update(80, "DTM array calculated")
            handlers.create_geotiff(dtm, str(output_path), request.crs, extent, nodata=request.nodata)
            _validate_created_output(output_path)
            self._progress.complete("DTM GeoTIFF created")
            return DtmResult(output_path=output_path, spatial_extent=tuple(float(value) for value in extent), resolution=request.resolution, crs=request.crs)
        except ProcessingError:
            self._progress.fail("DTM generation failed")
            raise
        except Exception as exc:  # noqa: BLE001 - convert dependency errors at boundary.
            self._progress.fail("DTM generation failed")
            raise ProcessingError(f"DTM generation failed: {exc}") from exc

    def preprocess_point_cloud(self, request: PointCloudPreprocessRequest) -> PointCloudPreprocessResult:
        """Run safe PyForestScan filter/preprocess steps and write LAS/LAZ."""
        if not request.crs:
            raise ProcessingError("Point-cloud preprocessing requires a dataset CRS.")
        output_path = Path(request.output_path)
        _validate_las_output_path(output_path)
        operations: list[str] = []
        self._progress.start("Reading lidar for preprocessing")
        try:
            handlers = _import_required("pyforestscan.handlers", ProcessingError)
            filters = _import_required("pyforestscan.filters", ProcessingError)
            arrays = handlers.read_lidar(str(request.input_path), request.crs, hag=False)
            if arrays is None:
                raise ProcessingError("PyForestScan returned no point data for preprocessing.")
            self._progress.update(20, "Point cloud loaded")
            if request.remove_outliers:
                arrays = filters.remove_outliers_and_clean(arrays, mean_k=request.outlier_mean_k, multiplier=request.outlier_multiplier)
                operations.append("remove_outliers_and_clean")
            if request.classify_ground:
                arrays = filters.classify_ground_points(arrays)
                operations.append("classify_ground_points")
            if request.ground_action == "remove_ground":
                arrays = filters.filter_ground(arrays)
                operations.append("filter_ground")
            elif request.ground_action == "select_ground":
                arrays = filters.filter_select_ground(arrays)
                operations.append("filter_select_ground")
            if request.add_hag:
                arrays = filters.add_height_above_ground(
                    arrays,
                    method=request.hag_method,
                    dtm=str(request.dtm_path) if request.dtm_path is not None else None,
                )
                operations.append("add_height_above_ground")
            if request.filter_hag:
                arrays = filters.filter_hag(arrays, lower_limit=request.hag_lower_limit, upper_limit=request.hag_upper_limit)
                operations.append("filter_hag")
            if request.thin_radius is not None:
                arrays = filters.downsample_poisson(arrays, request.thin_radius)
                operations.append("downsample_poisson")
            if request.voxelgrid_cell is not None:
                arrays = filters.downsample_voxel(arrays, request.voxelgrid_cell, request.voxelgrid_mode)
                operations.append("downsample_voxel")
            self._progress.update(75, "Filters applied")
            handlers.write_las(arrays, str(output_path), srs=request.crs, compress=request.compress)
            _validate_created_output(output_path)
            self._progress.complete("Preprocessed point cloud written")
            return PointCloudPreprocessResult(
                output_path=output_path,
                point_count=_point_count_from_point_cloud(arrays),
                crs=request.crs,
                operations=tuple(operations),
            )
        except ProcessingError:
            self._progress.fail("Point-cloud preprocessing failed")
            raise
        except Exception as exc:  # noqa: BLE001 - convert dependency errors at boundary.
            self._progress.fail("Point-cloud preprocessing failed")
            raise ProcessingError(f"Point-cloud preprocessing failed: {exc}") from exc

    def _read_hag_point_array(self, input_path: Path | str, crs: str, product_label: str) -> object:
        """Read lidar with HeightAboveGround and return one structured point array."""
        handlers = _import_required("pyforestscan.handlers", ProcessingError)
        point_cloud = handlers.read_lidar(str(input_path), crs, hag=True)
        if point_cloud is None:
            raise ProcessingError(f"PyForestScan returned no point data for {product_label} generation.")
        self._progress.update(25, "Point cloud loaded")
        point_array = _merge_point_cloud_arrays(point_cloud)
        names = getattr(point_array.dtype, "names", ()) or ()
        required = {"X", "Y", "HeightAboveGround"}
        missing = sorted(required.difference(names))
        if missing:
            raise ProcessingError(f"{product_label} input is missing required dimensions: {', '.join(missing)}")
        return point_array

    def clip_dataset(self, *args: object, **kwargs: object) -> None:
        """Placeholder for future adapter-managed clipping."""
        raise NotImplementedError("Dataset clipping is not implemented in Phase 4.")

    def list_available_products(self) -> tuple[ProductType, ...]:
        """Return product families known to the adapter architecture."""
        return DEFAULT_PRODUCTS

    def compute_products(self, request: ProductRequest) -> ProductResult:
        """Placeholder for future scientific processing."""
        raise NotImplementedError("Product computation is not implemented in Phase 4.")

    def export_products(self, result: ProductResult, output_directory: Path | str) -> tuple[Path, ...]:
        """Placeholder for future adapter-managed exports."""
        raise NotImplementedError("Product export is not implemented in Phase 4.")

    def get_progress(self) -> ProgressSnapshot:
        """Return the current adapter progress snapshot."""
        return self._progress.snapshot()

    def cancel(self) -> None:
        """Request cancellation for future long-running adapter work."""
        self._progress.cancel()
        self._log(LogLevel.WARNING, "Adapter cancellation requested")

    def close(self) -> None:
        """Clear adapter-held dataset references."""
        self._open_dataset = None
        self._progress = AdapterProgress()
        self._log(LogLevel.INFO, "Adapter closed")

    def _coerce_dataset(self, dataset: DatasetSource | str | Path | None) -> DatasetSource:
        if isinstance(dataset, DatasetSource):
            return dataset
        if dataset is None:
            if self._open_dataset is None:
                raise DatasetError("No dataset has been opened.")
            return self._open_dataset
        return self.open_dataset(dataset)

    def _inspect_ept(self, source: DatasetSource, options: InspectionOptions) -> DatasetInspection:
        metadata = _read_ept_json(str(source.path))
        bounds = _bounds_from_ept_metadata(metadata)
        crs = _crs_from_ept_metadata(metadata) or source.crs
        point_count = _point_count_from_ept_metadata(metadata)
        density = _estimate_density(point_count, bounds)
        dimensions = _dimensions_from_ept_metadata(metadata) if options.include_dimensions else ()

        return DatasetInspection(
            source=source,
            point_count=point_count,
            bounds=bounds,
            crs=crs,
            dimensions=dimensions,
            classification_summary=(),
            point_format=None,
            estimated_density=density,
            supported_products=DEFAULT_PRODUCTS,
            metadata_source="ept-json",
            warnings=("Classification summary is not available from EPT metadata inspection.",),
        )

    def _inspect_with_pdal(self, source: DatasetSource, options: InspectionOptions) -> DatasetInspection:
        pdal = _import_required("pdal", EnvironmentError)
        pipeline_json = _reader_pipeline_json(source)
        pipeline = pdal.Pipeline(pipeline_json)
        pipeline.execute()
        arrays = list(getattr(pipeline, "arrays", []) or [])
        if not arrays:
            raise DatasetError("PDAL returned no point arrays for dataset inspection.")

        first = arrays[0]
        point_count = int(sum(int(getattr(array, "size", len(array))) for array in arrays))
        bounds = _bounds_from_arrays(arrays)
        raw_dimensions = tuple(str(name) for name in (getattr(first.dtype, "names", None) or ()))
        dimensions = raw_dimensions if options.include_dimensions else ()
        crs = _crs_from_pdal_metadata(getattr(pipeline, "metadata", None)) or source.crs
        point_format = _point_format_from_pdal_metadata(getattr(pipeline, "metadata", None))
        warnings: list[str] = []

        classification_summary: tuple[ClassificationCount, ...] = ()
        if options.include_classification_summary and "Classification" in raw_dimensions:
            if (
                options.max_points_for_classification_summary is not None
                and point_count > options.max_points_for_classification_summary
            ):
                warnings.append("Classification summary skipped because point count exceeds inspection limit.")
            else:
                classification_summary = _classification_summary(arrays)
        elif options.include_classification_summary:
            warnings.append("Classification dimension not present; summary unavailable.")

        return DatasetInspection(
            source=source,
            point_count=point_count,
            bounds=bounds,
            crs=crs,
            dimensions=dimensions,
            classification_summary=classification_summary,
            point_format=point_format,
            estimated_density=_estimate_density(point_count, bounds),
            supported_products=DEFAULT_PRODUCTS,
            metadata_source="pdal-pipeline",
            warnings=tuple(warnings),
        )

    def _log(self, level: LogLevel, message: str, **context: object) -> None:
        if self._log_sink is not None:
            typed_context = tuple(
                LogContextItem(key=str(key), value=value) for key, value in context.items()
            )
            self._log_sink(LogRecord(level=level, message=message, context=typed_context))


def _xy_resolution(x_resolution: float, y_resolution: float | None) -> tuple[float, float]:
    """Return explicit X/Y resolution while preserving guided-mode defaults."""
    return (float(x_resolution), float(y_resolution if y_resolution is not None else x_resolution))


def _point_count_from_point_cloud(point_cloud: object) -> int | None:
    """Return the total point count from a PyForestScan read_lidar result."""
    if isinstance(point_cloud, (list, tuple)):
        return sum(int(getattr(array, "size", len(array) if hasattr(array, "__len__") else 0)) for array in point_cloud)
    size = getattr(point_cloud, "size", None)
    if size is not None:
        return int(size)
    if hasattr(point_cloud, "__len__"):
        return int(len(point_cloud))
    return None


def _validate_las_output_path(output_path: Path) -> None:
    """Validate that a LAS/LAZ point-cloud output path can be written."""
    if output_path.suffix.lower() not in {".las", ".laz"}:
        raise ProcessingError("Height normalization output must end with .las or .laz.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not output_path.parent.is_dir():
        raise ProcessingError(f"Output folder is not available: {output_path.parent}")
    probe = output_path.parent / f".{output_path.name}.write-test"
    try:
        probe.write_text("", encoding="utf-8")
    except OSError as exc:
        raise ProcessingError(f"Output folder is not writable: {output_path.parent}") from exc
    finally:
        try:
            probe.unlink()
        except OSError:
            pass


def _write_rumple_csv(output_path: Path, rumple_index: float, request: RumpleRequest, spatial_extent: object) -> None:
    """Write a scalar rumple result as a small CSV table."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    x_min, x_max, y_min, y_max = spatial_extent
    rows = [
        ("metric", "value"),
        ("rumple_index", f"{rumple_index:.12g}"),
        ("grid_resolution", f"{request.grid_resolution:.12g}"),
        ("min_height", "" if request.min_height is None else f"{request.min_height:.12g}"),
        ("crs", request.crs),
        ("extent_x_min", f"{float(x_min):.12g}"),
        ("extent_x_max", f"{float(x_max):.12g}"),
        ("extent_y_min", f"{float(y_min):.12g}"),
        ("extent_y_max", f"{float(y_max):.12g}"),
    ]
    output_path.write_text("\n".join(f"{name},{value}" for name, value in rows) + "\n", encoding="utf-8")


def _write_multiband_geotiff(layer: object, output_path: Path, crs: str, spatial_extent: object, nodata: float = -9999.0) -> None:
    """Write a 3D X/Y/Z PAD array as a multi-band GeoTIFF."""
    rasterio = _import_required("rasterio", ProcessingError)
    numpy = _import_required("numpy", ProcessingError)
    from rasterio.transform import from_bounds

    if not hasattr(layer, "shape") or len(layer.shape) != 3:
        raise ProcessingError(f"PAD output must be a 3D array; got shape {getattr(layer, 'shape', None)}")
    if layer.shape[0] <= 0 or layer.shape[1] <= 0 or layer.shape[2] <= 0:
        raise ProcessingError(f"PAD output has invalid dimensions: {layer.shape}")
    x_min, x_max, y_min, y_max = spatial_extent
    if x_max <= x_min or y_max <= y_min:
        raise ProcessingError(f"PAD output has invalid spatial extent: {spatial_extent}")
    data = numpy.nan_to_num(layer, nan=nodata)
    height = int(data.shape[1])
    width = int(data.shape[0])
    bands = int(data.shape[2])
    transform = from_bounds(x_min, y_min, x_max, y_max, width, height)
    with rasterio.open(
        output_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=bands,
        dtype=data.dtype.name,
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as dataset:
        for band_index in range(bands):
            dataset.write(data[:, :, band_index].T, band_index + 1)


def _validate_csv_output_path(output_path: Path) -> None:
    """Validate that a CSV table output path can be written."""
    if output_path.suffix.lower() != ".csv":
        raise ProcessingError("Rumple output filename must end with .csv because rumple is a scalar table product.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not output_path.parent.is_dir():
        raise ProcessingError(f"Output folder is not available: {output_path.parent}")
    probe = output_path.parent / f".{output_path.name}.write-test"
    try:
        probe.write_text("", encoding="utf-8")
    except OSError as exc:
        raise ProcessingError(f"Output folder is not writable: {output_path.parent}") from exc
    finally:
        try:
            probe.unlink()
        except OSError:
            pass


def _validate_output_path(output_path: Path) -> None:
    """Validate that a GeoTIFF output path can be written."""
    if output_path.suffix.lower() not in {".tif", ".tiff"}:
        raise ProcessingError("Output filename must end with .tif or .tiff.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not output_path.parent.is_dir():
        raise ProcessingError(f"Output folder is not available: {output_path.parent}")
    probe = output_path.parent / f".{output_path.name}.write-test"
    try:
        probe.write_text("", encoding="utf-8")
    except OSError as exc:
        raise ProcessingError(f"Output folder is not writable: {output_path.parent}") from exc
    finally:
        try:
            probe.unlink()
        except OSError:
            pass


def _validate_created_output(output_path: Path) -> None:
    """Require the PyForestScan GeoTIFF writer to create a usable file."""
    if not output_path.exists():
        raise ProcessingError(f"GeoTIFF was not created: {output_path}")
    try:
        if output_path.stat().st_size <= 0:
            raise ProcessingError(f"GeoTIFF is empty: {output_path}")
    except OSError as exc:
        raise ProcessingError(f"GeoTIFF could not be inspected: {output_path}") from exc


def _merge_point_cloud_arrays(point_cloud: object) -> object:
    """Return one structured array from PyForestScan read_lidar output."""
    if isinstance(point_cloud, (list, tuple)):
        arrays = [array for array in point_cloud if getattr(array, "size", len(array) if hasattr(array, "__len__") else 0) > 0]
        if not arrays:
            raise ProcessingError("PyForestScan returned empty point arrays for CHM generation.")
        if len(arrays) == 1:
            return arrays[0]
        numpy = _import_required("numpy", ProcessingError)
        return numpy.concatenate(arrays)
    return point_cloud


def _detect_format(path: str) -> DatasetFormat | None:
    lowered = path.lower()
    if lowered.endswith("ept.json"):
        return DatasetFormat.EPT
    if lowered.endswith(".copc.laz") or lowered.endswith(".copc"):
        return DatasetFormat.COPC
    for suffix, dataset_format in POINT_CLOUD_EXTENSIONS.items():
        if lowered.endswith(suffix):
            return dataset_format
    return None


def _is_remote(path: str) -> bool:
    parsed = urlparse(path)
    return bool(parsed.scheme and parsed.netloc)


def _read_ept_json(source: str) -> dict[str, Any]:
    if _is_remote(source):
        requests = _import_required("requests", EnvironmentError)
        response = requests.get(source, timeout=30)
        response.raise_for_status()
        return dict(response.json())
    with Path(source).open("r", encoding="utf-8") as handle:
        return dict(json.load(handle))


def _reader_pipeline_json(source: DatasetSource) -> str:
    if source.format in (DatasetFormat.LAS, DatasetFormat.LAZ):
        reader_type = "readers.las"
    elif source.format is DatasetFormat.COPC:
        reader_type = "readers.copc"
    else:
        reader_type = "readers.ept"
    reader: dict[str, object] = {"type": reader_type, "filename": str(source.path)}
    if source.crs:
        reader["spatialreference"] = source.crs
    return json.dumps({"pipeline": [reader]})


def _bounds_from_arrays(arrays: Iterable[Any]) -> Bounds3D | None:
    min_x = min_y = min_z = None
    max_x = max_y = max_z = None
    for array in arrays:
        names = getattr(array.dtype, "names", ()) or ()
        if "X" not in names or "Y" not in names:
            continue
        x_values = array["X"]
        y_values = array["Y"]
        if getattr(x_values, "size", 0) == 0:
            continue
        z_values = array["Z"] if "Z" in names else None
        min_x = _min_value(min_x, float(x_values.min()))
        max_x = _max_value(max_x, float(x_values.max()))
        min_y = _min_value(min_y, float(y_values.min()))
        max_y = _max_value(max_y, float(y_values.max()))
        if z_values is not None and getattr(z_values, "size", 0) > 0:
            min_z = _min_value(min_z, float(z_values.min()))
            max_z = _max_value(max_z, float(z_values.max()))
    if min_x is None or max_x is None or min_y is None or max_y is None:
        return None
    return Bounds3D(min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y, min_z=min_z, max_z=max_z)


def _bounds_from_ept_metadata(metadata: dict[str, Any]) -> Bounds3D | None:
    raw = metadata.get("bounds") or metadata.get("boundsConforming")
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)) and len(raw) == 6:
        min_x, min_y, min_z, max_x, max_y, max_z = raw
        return Bounds3D(float(min_x), float(max_x), float(min_y), float(max_y), float(min_z), float(max_z))
    if isinstance(raw, dict):
        return Bounds3D(
            min_x=float(raw["minx"]),
            max_x=float(raw["maxx"]),
            min_y=float(raw["miny"]),
            max_y=float(raw["maxy"]),
            min_z=float(raw["minz"]) if "minz" in raw else None,
            max_z=float(raw["maxz"]) if "maxz" in raw else None,
        )
    raise DatasetError(f"Unsupported EPT bounds format: {type(raw).__name__}")


def _crs_from_ept_metadata(metadata: dict[str, Any]) -> str | None:
    srs = metadata.get("srs") or {}
    if isinstance(srs, dict):
        authority = srs.get("authority")
        horizontal = srs.get("horizontal")
        if authority and horizontal:
            return f"{authority}:{horizontal}"
        if srs.get("wkt"):
            return str(srs["wkt"])
    return None


def _point_count_from_ept_metadata(metadata: dict[str, Any]) -> int | None:
    for key in ("points", "pointCount", "numPoints"):
        value = metadata.get(key)
        if value is not None:
            return int(value)
    return None


def _dimensions_from_ept_metadata(metadata: dict[str, Any]) -> tuple[str, ...]:
    schema = metadata.get("schema") or []
    names: list[str] = []
    if isinstance(schema, list):
        for item in schema:
            if isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
    return tuple(names)


def _classification_summary(arrays: Iterable[Any]) -> tuple[ClassificationCount, ...]:
    summary: dict[int, int] = {}
    for array in arrays:
        names = getattr(array.dtype, "names", ()) or ()
        if "Classification" not in names:
            continue
        values = array["Classification"]
        try:
            import numpy as np

            unique, counts = np.unique(values, return_counts=True)
            for value, count in zip(unique, counts):
                key = int(value)
                summary[key] = summary.get(key, 0) + int(count)
        except Exception as exc:  # noqa: BLE001 - summarize as dataset error at adapter boundary.
            raise DatasetError(f"Failed to summarize classifications: {exc}") from exc
    return tuple(
        ClassificationCount(classification=classification, count=count)
        for classification, count in sorted(summary.items())
    )


def _estimate_density(point_count: int | None, bounds: Bounds3D | None) -> float | None:
    if point_count is None or bounds is None or bounds.area <= 0:
        return None
    return float(point_count) / bounds.area


def _crs_from_pdal_metadata(metadata: object) -> str | None:
    text = _metadata_text(metadata)
    if not text:
        return None
    for key in ("compoundwkt", "wkt", "srs", "spatialreference"):
        value = _find_nested_value(text, key)
        if isinstance(value, str) and value:
            return value
    return None


def _point_format_from_pdal_metadata(metadata: object) -> str | None:
    text = _metadata_text(metadata)
    if not text:
        return None
    for key in ("dataformat_id", "pointformat", "point_format_id"):
        value = _find_nested_value(text, key)
        if value is not None:
            return str(value)
    return None


def _metadata_text(metadata: object) -> object:
    if callable(metadata):
        try:
            metadata = metadata()
        except TypeError:
            return None
    if isinstance(metadata, str):
        try:
            return json.loads(metadata)
        except json.JSONDecodeError:
            return metadata
    return metadata


def _find_nested_value(value: object, key: str) -> object | None:
    if isinstance(value, dict):
        for current_key, current_value in value.items():
            if str(current_key).lower() == key.lower():
                return current_value
            found = _find_nested_value(current_value, key)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_nested_value(item, key)
            if found is not None:
                return found
    return None


def _import_required(module_name: str, error_type: type[AdapterError]) -> Any:
    try:
        return importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001 - dependency errors become adapter errors.
        raise error_type(f"Required dependency is not importable: {module_name}") from exc


def _min_value(current: float | None, candidate: float) -> float:
    return candidate if current is None else min(current, candidate)


def _max_value(current: float | None, candidate: float) -> float:
    return candidate if current is None else max(current, candidate)
