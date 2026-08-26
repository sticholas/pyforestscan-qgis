"""Architecture-only adapter boundary around PyForestScan and PDAL.

This module validates and inspects datasets, exposes typed results, and
centralizes PyForestScan imports behind a plugin-owned API. CHM, canopy cover,
PAD, PAI, FHD, and rumple are implemented for single-dataset workflows.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable, Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable as TypingCallable
from urllib.parse import urlparse

from .config import AdapterConfig, DatasetOpenOptions, InspectionOptions
from .dependency_check import EnvironmentReport, collect_environment_report
from .exceptions import AdapterError, DatasetError, EnvironmentError, ProcessingError
from .ept_bounds import EptBounds, EptBoundsError, validate_pyforestscan_bounds_value
from .ept_spatial_reference import resolve_ept_spatial_reference
from .pad_products import pad_band_mapping, pad_metadata_tags
from .spatial_reference_resolver import SpatialReferenceResolver, SpatialReferenceStatus
from .point_dimensions import PointDimensionCapabilities, SourceDimensionMismatch
from .spatial_reference_contract import SpatialReferenceMode
from .polygon_transport import looks_like_wkt, materialize_polygon_input, polygon_execution_input_from_mapping
from .ept_subset import EptSubsetRequest, EptSubsetResult, ept_read_lidar_kwargs
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

EXECUTION_MODE_AUTO = "auto"
EXECUTION_MODE_QGIS_PYTHON = "qgis_python"
EXECUTION_MODE_PBM_BACKEND = "pbm_backend"

PBM_ROUTED_PRODUCTS = {
    ProductType.CHM,
    ProductType.PAD,
    ProductType.PAI,
    ProductType.FHD,
    ProductType.CANOPY_COVER,
    ProductType.RUMPLE,
    ProductType.POINT_DENSITY,
    ProductType.VOXEL_STAT,
    ProductType.DTM,
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
        execution_mode: str = EXECUTION_MODE_AUTO,
        backend_service_factory: TypingCallable[[], object] | None = None,
    ) -> None:
        """Create an adapter with immutable configuration and optional logging."""
        self.config = config or AdapterConfig()
        self._log_sink = log_sink
        self.execution_mode = execution_mode
        self._backend_service_factory = backend_service_factory
        self._progress = AdapterProgress()
        self._open_dataset: DatasetSource | None = None
        self._chm_cache: dict[tuple[object, ...], tuple[object, object]] = {}

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
                pbm_inspection = self._run_pbm_inspection_if_selected(source, opts)
                inspection = pbm_inspection if pbm_inspection is not None else self._inspect_with_pdal(source, opts)
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
        resolution = _resolve_product_spatial_reference(request, source_local_allowed=True)
        if resolution.status is SpatialReferenceStatus.SOURCE_LOCAL_ONLY:
            request = replace(request, crs=None)
        elif resolution.resolved_crs and not request.crs:
            request = replace(request, crs=resolution.resolved_crs)
        output_path = Path(request.output_path)
        _validate_output_path(output_path)
        pbm_result = self._run_pbm_product_if_selected(ProductType.CHM, request)
        if pbm_result is not None:
            return pbm_result
        self._progress.start("Reading lidar for CHM")
        self._log(LogLevel.INFO, "Starting CHM generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            handlers = _import_required("pyforestscan.handlers", ProcessingError)
            planned_method = getattr(request, "hag_method", "classified_ground_delaunay")
            if planned_method not in {"existing_normalized_height", "classified_ground_delaunay"}:
                raise ProcessingError(f"Unsupported planned HAG method for CHM: {planned_method}")
            if resolution.status is SpatialReferenceStatus.SOURCE_LOCAL_ONLY:
                point_cloud = _read_source_local_lidar(request)
            else:
                point_cloud = handlers.read_lidar(str(request.input_path), request.crs, **_read_lidar_spatial_kwargs(request, hag=planned_method != "existing_normalized_height"))
            if point_cloud is None:
                raise ProcessingError("PyForestScan returned no point data for CHM generation.")
            self._progress.update(35, "Point cloud loaded")
            point_array = _merge_point_cloud_arrays(point_cloud)
            point_array, capabilities = _canonicalize_hag_dimension(point_array)
            names = capabilities.names
            inspected = PointDimensionCapabilities.from_names(getattr(request, "source_dimensions", ()))
            if planned_method == "existing_normalized_height" and not capabilities.has_existing_hag:
                raise SourceDimensionMismatch(getattr(request, "hag_source_dimension", "HeightAboveGround"), names)
            if resolution.status is SpatialReferenceStatus.SOURCE_LOCAL_ONLY:
                if capabilities.has_existing_hag:
                    planned_method = "existing_normalized_height"
                    request = replace(request, hag_method=planned_method, hag_source_dimension="HeightAboveGround")
                elif inspected.has_existing_hag:
                    raise SourceDimensionMismatch(inspected.hag_dimension_name or "HeightAboveGround", names)
                else:
                    raise ProcessingError("Source-local CHM requires an existing normalized-height dimension; the execution read did not contain one.")
            _write_source_local_adapter_trace(request, "pdal_read", {"dimensions": list(names), "has_existing_hag": capabilities.has_existing_hag})
            if planned_method == "existing_normalized_height":
                from .chm_work_unit_execution import validate_existing_hag_array
                validate_existing_hag_array(point_array, request)
            required = {"X", "Y", "HeightAboveGround"}
            missing = sorted(required.difference(names))
            if missing:
                suffix = " for the planned existing-HAG method" if planned_method == "existing_normalized_height" else ""
                raise ProcessingError(f"CHM input is missing required dimensions{suffix}: {', '.join(missing)}")
            chm, extent = pyforestscan.calculate_chm(
                point_array,
                _xy_resolution(request.grid_resolution, request.y_resolution),
                interpolation=request.interpolation,
                interp_valid_region=request.interp_valid_region,
                interp_clean_edges=request.interp_clean_edges,
            )
            self._progress.update(70, "CHM array calculated")
            self._chm_cache[_chm_cache_key(request)] = (chm, extent)
            if resolution.status is SpatialReferenceStatus.SOURCE_LOCAL_ONLY:
                _write_source_local_geotiff(chm, output_path, extent, product="Canopy Height Model")
                _write_source_local_adapter_trace(request, "chm_writer", {"source_local": True, "crs": None, "hag_mode": "EXISTING_HAG"})
            else:
                handlers.create_geotiff(chm, str(output_path), request.crs, extent)
                _write_crs_provenance(output_path, resolution)
            _validate_created_output(output_path)
            self._progress.complete("CHM GeoTIFF created")
            self._log(LogLevel.INFO, "CHM generation complete", output=str(output_path))
            return ChmResult(
                output_path=output_path,
                spatial_extent=tuple(float(value) for value in extent),
                grid_resolution=request.grid_resolution,
                crs=request.crs or "",
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
        pbm_result = self._run_pbm_product_if_selected(ProductType.PAD, request)
        if pbm_result is not None:
            return pbm_result
        self._progress.start("Reading lidar for PAD")
        self._log(LogLevel.INFO, "Starting PAD generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            point_array = self._read_hag_point_array(request, "PAD")
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
            _write_multiband_geotiff(pad, output_path, request.crs, extent, voxel_height=request.voxel_height, beer_lambert_constant=request.beer_lambert_constant, drop_ground=request.drop_ground)
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
        pbm_result = self._run_pbm_product_if_selected(ProductType.PAI, request)
        if pbm_result is not None:
            return pbm_result
        self._progress.start("Reading lidar for PAI")
        self._log(LogLevel.INFO, "Starting PAI generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            handlers = _import_required("pyforestscan.handlers", ProcessingError)
            point_array = self._read_hag_point_array(request, "PAI")
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
        pbm_result = self._run_pbm_product_if_selected(ProductType.FHD, request)
        if pbm_result is not None:
            return pbm_result
        self._progress.start("Reading lidar for FHD")
        self._log(LogLevel.INFO, "Starting FHD generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            handlers = _import_required("pyforestscan.handlers", ProcessingError)
            point_array = self._read_hag_point_array(request, "FHD")
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
        """Generate a patch-centered Rumple GeoTIFF plus scalar summary."""
        if request.grid_resolution <= 0:
            raise ProcessingError("Rumple X resolution must be greater than zero.")
        if request.y_resolution is not None and request.y_resolution <= 0:
            raise ProcessingError("Rumple Y resolution must be greater than zero.")
        if request.min_height is not None and request.min_height < 0:
            raise ProcessingError("Rumple minimum height must be zero or greater.")
        resolution = _resolve_product_spatial_reference(request, source_local_allowed=True)
        if resolution.status is SpatialReferenceStatus.SOURCE_LOCAL_ONLY:
            request = replace(request, crs=None)
        elif resolution.resolved_crs and not request.crs:
            request = replace(request, crs=resolution.resolved_crs)
        output_path = Path(request.output_path)
        if output_path.suffix.lower() not in {".tif", ".tiff", ".csv"}:
            raise ProcessingError("Rumple output must be a GeoTIFF, or CSV for legacy scalar compatibility.")
        pbm_result = self._run_pbm_product_if_selected(ProductType.RUMPLE, request)
        if pbm_result is not None:
            return pbm_result
        self._progress.start("Reading lidar for rumple")
        self._log(LogLevel.INFO, "Starting rumple generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            cache_key = _chm_cache_key(request)
            if cache_key in self._chm_cache:
                chm, extent = self._chm_cache[cache_key]
                chm_source = "reused compatible CHM from current adapter session"
                self._progress.update(55, "Compatible CHM reused")
            else:
                point_array = self._read_hag_point_array(request, "rumple")
                chm, extent = pyforestscan.calculate_chm(
                    point_array,
                    _xy_resolution(request.grid_resolution, request.y_resolution),
                    interpolation=request.interpolation,
                    interp_valid_region=request.interp_valid_region,
                    interp_clean_edges=request.interp_clean_edges,
                )
                self._chm_cache[cache_key] = (chm, extent)
                chm_source = "internally generated for Rumple"
                self._progress.update(65, "Internal CHM prerequisite calculated")
            rumple_index = float(pyforestscan.calculate_rumple(
                chm,
                _xy_resolution(request.grid_resolution, request.y_resolution),
                min_height=request.min_height,
            ))
            from .localized_rumple import calculate_local_rumple_surface, rumple_patch_extent
            surface = calculate_local_rumple_surface(chm, _xy_resolution(request.grid_resolution, request.y_resolution), request.min_height)
            if not surface.valid_patch_count:
                raise ProcessingError("Rumple cannot be calculated because no valid 2x2 CHM surface patches remain.")
            difference = abs(rumple_index - surface.aggregate_rumple)
            tolerance = 1e-10 * max(1.0, abs(rumple_index))
            if output_path.suffix.lower() != ".csv" and difference > tolerance:
                raise ProcessingError(f"Rumple scalar compatibility check failed ({difference:.3g} > {tolerance:.3g}).")
            self._progress.update(85, "Spatial Rumple surface calculated")
            if output_path.suffix.lower() == ".csv":
                summary_path = output_path
            else:
                _write_rumple_geotiff(output_path, surface.values, request.crs, rumple_patch_extent(extent, surface.cell_resolution), request, surface, rumple_index)
                _write_crs_provenance(output_path, resolution)
                if resolution.status is SpatialReferenceStatus.SOURCE_LOCAL_ONLY:
                    _write_source_local_adapter_trace(request, "rumple_writer", {"source_local": True, "crs": None, "supporting_chm": chm_source})
                summary_path = output_path.with_name(f"{output_path.stem}_summary.csv")
            _write_rumple_csv(summary_path, rumple_index, request, extent, chm_source=chm_source, spatial_aggregate=surface.aggregate_rumple, valid_patch_count=surface.valid_patch_count)
            _validate_created_output(output_path)
            self._progress.complete("Rumple raster created" if output_path.suffix.lower() != ".csv" else "Rumple summary created")
            self._log(LogLevel.INFO, "Rumple generation complete", output=str(output_path), rumple_index=rumple_index, valid_patch_count=surface.valid_patch_count)
            return RumpleResult(
                output_path=output_path,
                rumple_index=rumple_index,
                spatial_extent=tuple(float(value) for value in extent),
                grid_resolution=request.grid_resolution,
                crs=request.crs or "",
                summary_path=summary_path,
                valid_patch_count=surface.valid_patch_count,
                spatial_aggregate=surface.aggregate_rumple,
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
        pbm_result = self._run_pbm_product_if_selected(ProductType.CANOPY_COVER, request)
        if pbm_result is not None:
            return pbm_result
        self._progress.start("Reading lidar for canopy cover")
        self._log(LogLevel.INFO, "Starting canopy cover generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            handlers = _import_required("pyforestscan.handlers", ProcessingError)
            point_array = self._read_hag_point_array(request, "canopy cover")
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
        pbm_result = self._run_pbm_product_if_selected(ProductType.POINT_DENSITY, request)
        if pbm_result is not None:
            return pbm_result
        self._progress.start("Reading lidar for point density")
        self._log(LogLevel.INFO, "Starting point density generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            handlers = _import_required("pyforestscan.handlers", ProcessingError)
            point_array = self._read_hag_point_array(request, "point density")
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
        pbm_result = self._run_pbm_product_if_selected(ProductType.VOXEL_STAT, request)
        if pbm_result is not None:
            return pbm_result
        self._progress.start("Reading lidar for voxel statistic")
        self._log(LogLevel.INFO, "Starting voxel statistic generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            handlers = _import_required("pyforestscan.handlers", ProcessingError)
            point_array = self._read_hag_point_array(request, "voxel statistic")
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
            read_kwargs = _read_lidar_spatial_kwargs(request, hag=not request.use_dtm)
            read_kwargs.update(
                thin_radius=request.thin_radius,
                hag_dtm=request.use_dtm,
                dtm=str(request.dtm_path) if request.dtm_path is not None else None,
                reproject=request.reproject,
            )
            point_cloud = handlers.read_lidar(str(request.input_path), request.crs, **read_kwargs)
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
        pbm_result = self._run_pbm_product_if_selected(ProductType.DTM, request)
        if pbm_result is not None:
            return pbm_result
        self._progress.start("Reading lidar for DTM")
        self._log(LogLevel.INFO, "Starting DTM generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            handlers = _import_required("pyforestscan.handlers", ProcessingError)
            filters = _import_required("pyforestscan.filters", ProcessingError)
            point_cloud = handlers.read_lidar(str(request.input_path), request.crs, **_read_lidar_spatial_kwargs(request, hag=False))
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
                arrays = filters.remove_outliers_and_clean(
                    arrays,
                    mean_k=request.outlier_mean_k,
                    multiplier=request.outlier_multiplier,
                    remove=request.outlier_remove,
                )
                operations.append("remove_outliers_and_clean")
            if request.classify_ground:
                arrays = filters.classify_ground_points(
                    arrays,
                    ignore_class=request.smrf_ignore_class,
                    cell=request.smrf_cell,
                    cut=request.smrf_cut,
                    returns=request.smrf_returns,
                    scalar=request.smrf_scalar,
                    slope=request.smrf_slope,
                    threshold=request.smrf_threshold,
                    window=request.smrf_window,
                )
                operations.append("classify_ground_points")
            if request.ground_action == "remove_ground":
                arrays = filters.filter_ground(arrays)
                operations.append("filter_ground")
            elif request.ground_action == "select_ground":
                arrays = filters.filter_select_ground(arrays)
                operations.append("filter_select_ground")
            if request.filter_pointsourceid:
                arrays = filters.filter_pointsourceid(arrays, request.pointsource_ids)
                operations.append("filter_pointsourceid")
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


    def extract_lidar_subset(self, request: EptSubsetRequest) -> EptSubsetResult:
        """Extract an EPT subset and write it as LAS/LAZ through the active backend."""
        output_path = Path(request.output_path)
        _validate_las_output_path(output_path)
        pbm_result = self._run_pbm_ept_subset_if_selected(request)
        if pbm_result is not None:
            return pbm_result
        self._progress.start("Reading EPT subset")
        self._log(LogLevel.INFO, "Starting EPT subset extraction", input=str(request.input_path), output=str(output_path))
        try:
            handlers = _import_required("pyforestscan.handlers", ProcessingError)
            kwargs = {key: value for key, value in ept_read_lidar_kwargs(request).items() if value is not None}
            point_cloud = handlers.read_lidar(str(request.input_path), request.crs, **kwargs)
            if point_cloud is None:
                raise ProcessingError("PyForestScan returned no point data for EPT subset extraction.")
            self._progress.update(70, "EPT subset read")
            handlers.write_las(point_cloud, str(output_path), srs=request.crs, compress=request.compress)
            _validate_created_point_cloud_output(output_path)
            point_count = _point_count_from_point_cloud(point_cloud)
            message = f"EPT subset written to {output_path}"
            self._progress.complete("EPT subset written")
            self._log(LogLevel.INFO, "EPT subset extraction complete", output=str(output_path))
            return EptSubsetResult(output_path=output_path, point_count=point_count, written=True, message=message)
        except ProcessingError:
            self._progress.fail("EPT subset extraction failed")
            raise
        except Exception as exc:  # noqa: BLE001 - convert dependency errors at boundary.
            self._progress.fail("EPT subset extraction failed")
            raise ProcessingError(f"EPT subset extraction failed: {exc}") from exc

    def _run_pbm_ept_subset_if_selected(self, request: EptSubsetRequest) -> EptSubsetResult | None:
        if self.execution_mode == EXECUTION_MODE_QGIS_PYTHON:
            return None
        service = self._backend_service()
        try:
            availability = service.can_execute_processing()
        except Exception as exc:  # noqa: BLE001 - fall back in auto, fail in forced PBM.
            if self.execution_mode == EXECUTION_MODE_PBM_BACKEND:
                raise ProcessingError(f"PBM backend is not available for EPT subset extraction: {exc}") from exc
            return None
        if not availability.ready:
            if self.execution_mode == EXECUTION_MODE_PBM_BACKEND:
                raise ProcessingError(availability.message)
            return None
        self._progress.start("Running EPT subset extraction through PyForestScan Backend Manager")
        self._log(LogLevel.INFO, "Running EPT subset through PBM backend", backend_python=str(availability.backend_python))
        try:
            backend_result = service.run_product("ept_subset_extract", request)
        except Exception as exc:  # noqa: BLE001 - convert backend subprocess errors at adapter boundary.
            self._progress.fail("PBM backend EPT subset extraction failed")
            raise ProcessingError(f"PBM backend EPT subset extraction failed: {exc}") from exc
        metrics = getattr(backend_result, "product_metrics", {}) or {}
        outputs = getattr(backend_result, "outputs", {}) or {}
        output_path = Path(metrics.get("output_path") or outputs.get("primary") or request.output_path)
        point_count = metrics.get("point_count")
        self._progress.complete("PBM backend EPT subset extraction complete")
        return EptSubsetResult(
            output_path=output_path,
            point_count=int(point_count) if point_count is not None else None,
            written=bool(metrics.get("written", True)),
            message=str(metrics.get("message") or f"EPT subset written to {output_path}"),
        )

    def selected_execution_backend(self) -> str:
        """Return the currently selected processing backend label."""
        if self._can_use_pbm_backend():
            return EXECUTION_MODE_PBM_BACKEND
        return EXECUTION_MODE_QGIS_PYTHON

    def _backend_service(self) -> object:
        if self._backend_service_factory is not None:
            return self._backend_service_factory()
        from .backend import BackendService

        return BackendService()

    def _can_use_pbm_backend(self) -> bool:
        if self.execution_mode == EXECUTION_MODE_QGIS_PYTHON:
            return False
        try:
            service = self._backend_service()
            availability = service.can_execute_processing()
            return bool(availability.ready)
        except Exception:
            return False

    def _run_pbm_product_if_selected(self, product: ProductType, request: object):
        if product not in PBM_ROUTED_PRODUCTS or self.execution_mode == EXECUTION_MODE_QGIS_PYTHON:
            return None
        service = self._backend_service()
        try:
            availability = service.can_execute_processing()
        except Exception as exc:  # noqa: BLE001 - fall back in auto, fail in forced PBM.
            if self.execution_mode == EXECUTION_MODE_PBM_BACKEND:
                raise ProcessingError(f"PBM backend is not available for {product.value}: {exc}") from exc
            return None
        if not availability.ready:
            if self.execution_mode == EXECUTION_MODE_PBM_BACKEND:
                raise ProcessingError(availability.message)
            return None
        self._progress.start(f"Running {product.value} through PyForestScan Backend Manager")
        self._log(LogLevel.INFO, "Running product through PBM backend", product=product.value, backend_python=str(availability.backend_python))
        try:
            backend_result = service.run_product(product.value, request)
        except Exception as exc:  # noqa: BLE001 - convert backend subprocess errors at adapter boundary.
            self._progress.fail(f"PBM backend {product.value} failed")
            raise ProcessingError(_backend_user_error(product, exc)) from exc
        self._progress.complete(f"PBM backend {product.value} complete")
        return _adapter_result_from_backend(product, request, backend_result)


    def _run_pbm_inspection_if_selected(self, source: DatasetSource, options: InspectionOptions) -> DatasetInspection | None:
        if self.execution_mode == EXECUTION_MODE_QGIS_PYTHON:
            return None
        service = self._backend_service()
        try:
            availability = service.can_execute_processing()
        except Exception as exc:  # noqa: BLE001 - fall back in auto, fail in forced PBM.
            if self.execution_mode == EXECUTION_MODE_PBM_BACKEND:
                raise DatasetError(f"PBM backend is not available for Dataset Explorer: {exc}") from exc
            return None
        if not availability.ready:
            if self.execution_mode == EXECUTION_MODE_PBM_BACKEND:
                raise DatasetError(availability.message)
            return None
        self._log(LogLevel.INFO, "Inspecting dataset through PBM backend", backend_python=str(availability.backend_python), path=str(source.path))
        result = service.run_dataset_inspection(
            Path(source.path),
            source.crs or "",
            {
                "include_classification_summary": options.include_classification_summary,
                "include_dimensions": options.include_dimensions,
                "max_points_for_classification_summary": options.max_points_for_classification_summary,
            },
            self.config.working_directory or Path(source.path).parent,
        )
        return _dataset_inspection_from_backend_metrics(result.product_metrics)

    def _read_hag_point_array(self, request_or_path: object, crs: str | None = None, product_label: str | None = None) -> object:
        """Read lidar with HeightAboveGround and return one structured point array."""
        if product_label is None:
            product_label = str(crs or "product")
            crs = str(getattr(request_or_path, "crs", "") or "")
        handlers = _import_required("pyforestscan.handlers", ProcessingError)
        input_path = getattr(request_or_path, "input_path", request_or_path)
        if not crs:
            point_cloud = _read_source_local_lidar(request_or_path)
        else:
            point_cloud = handlers.read_lidar(str(input_path), str(crs), **_read_lidar_spatial_kwargs(request_or_path, hag=True))
        if point_cloud is None:
            raise ProcessingError(f"PyForestScan returned no point data for {product_label} generation.")
        self._progress.update(25, "Point cloud loaded")
        point_array = _merge_point_cloud_arrays(point_cloud)
        point_array, capabilities = _canonicalize_hag_dimension(point_array)
        names = capabilities.names
        required = {"X", "Y", "HeightAboveGround"}
        missing = sorted(required.difference(names))
        if missing:
            expected = getattr(request_or_path, "hag_source_dimension", "HeightAboveGround")
            raise SourceDimensionMismatch(expected, names)
        _write_source_local_adapter_trace(request_or_path, "pdal_read", {"dimensions": list(names), "has_existing_hag": True})
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
        self._chm_cache.clear()
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



def _read_lidar_spatial_kwargs(request: object, *, hag: bool) -> dict[str, object]:
    """Return spatial read options carried across the PBM request boundary."""
    kwargs: dict[str, object] = {"hag": hag}
    bounds = getattr(request, "bounds", None)
    crop_polygon = getattr(request, "crop_polygon", None)
    crop_polygon_path = getattr(request, "crop_polygon_path", None)
    polygon_input = polygon_execution_input_from_mapping(getattr(request, "polygon_execution_input", None))
    if crop_polygon_path is None and polygon_input is not None:
        output_path = Path(getattr(request, "output_path", Path.cwd()))
        prepared = materialize_polygon_input(polygon_input, output_path.parent / ".polygon_inputs")
        crop_polygon_path = prepared.temporary_vector_path
    if bounds is not None:
        kwargs["bounds"] = prepare_ept_bounds(bounds, crs=str(getattr(request, "crs", ""))).to_pyforestscan_value()
        validate_pyforestscan_bounds_value(kwargs["bounds"])
    if crop_polygon_path:
        kwargs["crop_poly"] = True
        kwargs["poly"] = str(crop_polygon_path)
    elif crop_polygon and not looks_like_wkt(crop_polygon):
        kwargs["crop_poly"] = True
        kwargs["poly"] = str(crop_polygon)
    return kwargs


def prepare_ept_bounds(bounds: object, *, crs: str, source: str = "polygon_envelope", transformed: bool = True) -> EptBounds:
    """Normalize EPT bounds at the one authoritative adapter boundary."""
    try:
        return EptBounds.from_value(bounds, crs=crs, source=source, transformed=transformed)
    except EptBoundsError as exc:
        raise ProcessingError(f"Invalid EPT bounds for PyForestScan request: {exc}") from exc

def _dataset_inspection_from_backend_metrics(metrics: dict[str, object]) -> DatasetInspection:
    source_data = dict(metrics.get("source", {}) or {})
    bounds_data = metrics.get("bounds")
    if isinstance(bounds_data, dict):
        bounds = Bounds3D(
            min_x=float(bounds_data["min_x"]),
            max_x=float(bounds_data["max_x"]),
            min_y=float(bounds_data["min_y"]),
            max_y=float(bounds_data["max_y"]),
            min_z=float(bounds_data["min_z"]) if bounds_data.get("min_z") is not None else None,
            max_z=float(bounds_data["max_z"]) if bounds_data.get("max_z") is not None else None,
        )
    else:
        bounds = None
    classification_summary = tuple(
        ClassificationCount(int(item["classification"]), int(item["count"]))
        for item in metrics.get("classification_summary", ()) or ()
        if isinstance(item, dict)
    )
    products = tuple(ProductType(item) for item in metrics.get("supported_products", ()) or ())
    return DatasetInspection(
        source=DatasetSource(
            path=Path(str(source_data.get("path", ""))),
            format=DatasetFormat(str(source_data.get("format", DatasetFormat.LAS.value))),
            crs=source_data.get("crs"),
            is_remote=bool(source_data.get("is_remote", False)),
        ),
        point_count=int(metrics["point_count"]) if metrics.get("point_count") is not None else None,
        bounds=bounds,
        crs=metrics.get("crs"),
        dimensions=tuple(str(item) for item in metrics.get("dimensions", ()) or ()),
        classification_summary=classification_summary,
        point_format=metrics.get("point_format"),
        estimated_density=float(metrics["estimated_density"]) if metrics.get("estimated_density") is not None else None,
        supported_products=products,
        metadata_source=str(metrics.get("metadata_source", "pbm-backend")),
        warnings=tuple(str(item) for item in metrics.get("warnings", ()) or ()),
    )


def _adapter_result_from_backend(product: ProductType, request: object, backend_result: object):
    metrics = getattr(backend_result, "product_metrics", {}) or {}
    outputs = getattr(backend_result, "outputs", {}) or {}
    output_path = Path(metrics.get("output_path") or outputs.get("primary") or getattr(request, "output_path"))
    extent = tuple(float(value) for value in metrics.get("spatial_extent", (0.0, 0.0, 0.0, 0.0)))
    crs = str(metrics.get("crs") or getattr(request, "crs", ""))
    if product is ProductType.CHM:
        return ChmResult(output_path, extent, float(metrics.get("grid_resolution", getattr(request, "grid_resolution"))), crs)
    if product is ProductType.PAD:
        return PadResult(output_path, extent, float(metrics.get("grid_resolution", getattr(request, "grid_resolution"))), float(metrics.get("voxel_height", getattr(request, "voxel_height"))), int(metrics.get("band_count", 0)), crs)
    if product is ProductType.PAI:
        return PaiResult(output_path, extent, float(metrics.get("grid_resolution", getattr(request, "grid_resolution"))), float(metrics.get("voxel_height", getattr(request, "voxel_height"))), crs)
    if product is ProductType.FHD:
        return FhdResult(output_path, extent, float(metrics.get("grid_resolution", getattr(request, "grid_resolution"))), float(metrics.get("voxel_height", getattr(request, "voxel_height"))), crs)
    if product is ProductType.RUMPLE:
        summary=metrics.get("summary_path")
        return RumpleResult(output_path,float(metrics.get("rumple_index",0.0)),extent,float(metrics.get("grid_resolution",getattr(request,"grid_resolution"))),crs,Path(summary) if summary else None,int(metrics.get("valid_patch_count",0)),metrics.get("spatial_aggregate"))
    if product is ProductType.CANOPY_COVER:
        return CanopyCoverResult(output_path, extent, float(metrics.get("grid_resolution", getattr(request, "grid_resolution"))), float(metrics.get("canopy_height_threshold", getattr(request, "canopy_height_threshold"))), crs)
    if product is ProductType.POINT_DENSITY:
        return PointDensityResult(output_path, extent, float(metrics.get("grid_resolution", getattr(request, "grid_resolution"))), float(metrics.get("voxel_height", getattr(request, "voxel_height"))), crs)
    if product is ProductType.VOXEL_STAT:
        return VoxelStatResult(output_path, extent, float(metrics.get("grid_resolution", getattr(request, "grid_resolution"))), float(metrics.get("voxel_height", getattr(request, "voxel_height"))), str(metrics.get("dimension", getattr(request, "dimension"))), str(metrics.get("stat", getattr(request, "stat"))), crs)
    if product is ProductType.DTM:
        return DtmResult(output_path, extent, float(metrics.get("resolution", getattr(request, "resolution"))), crs)
    raise ProcessingError(f"Unsupported PBM backend result product: {product.value}")


def _chm_cache_key(request: object) -> tuple[object, ...]:
    path = Path(str(getattr(request, "input_path", "")))
    try:
        stat = path.stat()
        fingerprint = (stat.st_size, stat.st_mtime_ns)
    except OSError:
        fingerprint = (None, None)
    crs = str(getattr(request, "crs", "") or "").strip()
    return (
        str(path),
        fingerprint,
        SpatialReferenceMode.RESOLVED.value if crs else SpatialReferenceMode.SOURCE_LOCAL.value,
        crs or None,
        str(getattr(request, "hag_method", "existing_normalized_height")),
        str(getattr(request, "hag_source_dimension", "HeightAboveGround")),
        str(getattr(request, "hag_method_signature", "")),
        float(getattr(request, "grid_resolution", 0.0)),
        float(getattr(request, "y_resolution", getattr(request, "grid_resolution", 0.0)) or getattr(request, "grid_resolution", 0.0)),
        getattr(request, "interpolation", None),
        bool(getattr(request, "interp_valid_region", False)),
        bool(getattr(request, "interp_clean_edges", False)),
    )


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


def _write_rumple_csv(output_path: Path, rumple_index: float, request: RumpleRequest, spatial_extent: object, *, chm_source: str = "internally generated for Rumple", spatial_aggregate=None, valid_patch_count=0) -> None:
    """Write a scalar rumple result as a small CSV table."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    x_min, x_max, y_min, y_max = spatial_extent
    rows = [
        ("metric", "value"),
        ("rumple_index", f"{rumple_index:.12g}"),
        ("spatial_raster_aggregate", "" if spatial_aggregate is None else f"{spatial_aggregate:.12g}"),
        ("absolute_difference", "" if spatial_aggregate is None else f"{abs(rumple_index-spatial_aggregate):.12g}"),
        ("valid_patch_count", str(valid_patch_count)),
        ("grid_resolution", f"{request.grid_resolution:.12g}"),
        ("min_height", "" if request.min_height is None else f"{request.min_height:.12g}"),
        ("native_pyforestscan_output", "scalar"),
        ("chm_source", chm_source),
        ("supporting_chm_saved", "false"),
        ("interpretation_note", "Upstream PyForestScan returns this area scalar; the primary QGIS raster stores the same ratio for each valid 2x2 CHM patch."),
        ("crs", request.crs),
        ("extent_x_min", f"{float(x_min):.12g}"),
        ("extent_x_max", f"{float(x_max):.12g}"),
        ("extent_y_min", f"{float(y_min):.12g}"),
        ("extent_y_max", f"{float(y_max):.12g}"),
    ]
    output_path.write_text("\n".join(f"{name},{value}" for name, value in rows) + "\n", encoding="utf-8")

def _write_rumple_geotiff(output_path, values, crs, extent, request, surface, upstream_scalar, nodata=-9999.0):
    rasterio=_import_required("rasterio",ProcessingError);numpy=_import_required("numpy",ProcessingError)
    from rasterio.transform import from_bounds
    if values.ndim != 2 or not values.size: raise ProcessingError("Rumple raster has invalid dimensions.")
    xmin,xmax,ymin,ymax=extent;output_path.parent.mkdir(parents=True,exist_ok=True);temporary=output_path.with_suffix(".partial.tif");raster_values=values.T
    profile={"driver":"GTiff","height":raster_values.shape[0],"width":raster_values.shape[1],"count":1,"dtype":"float32","crs":crs or None,"transform":from_bounds(xmin,ymin,xmax,ymax,raster_values.shape[1],raster_values.shape[0]),"nodata":nodata,"compress":"deflate","tiled":raster_values.shape[0]>=16 and raster_values.shape[1]>=16}
    with rasterio.open(temporary,"w",**profile) as dst:
        dst.write(numpy.where(numpy.isfinite(raster_values),raster_values,nodata).astype("float32"),1);dst.set_band_description(1,"Rumple Index")
        spatial_tags = _source_local_raster_tags() if not crs else {"PYFORESTSCAN_SPATIAL_REFERENCE_MODE": "RESOLVED", "SOURCE_CRS_RESOLVED": "true", "SOURCE_COORDINATE_UNITS": "crs_defined", "CRS_ASSIGNMENT_REQUIRED_FOR_SPATIAL_ALIGNMENT": "false"}
        dst.update_tags(PRODUCT="Rumple Index",UNITS="dimensionless",METHOD="pyforestscan_qgis_patch_surface_v1",CHM_RESOLUTION=str(surface.cell_resolution),RUMPLE_ANALYSIS_SCALE="2x2 CHM patch",MIN_HEIGHT="None" if request.min_height is None else str(request.min_height),PYFORESTSCAN_SCALAR_COMPATIBLE="true",PYFORESTSCAN_SCALAR=f"{upstream_scalar:.12g}",VALID_PATCH_COUNT=str(surface.valid_patch_count),**spatial_tags)
    temporary.replace(output_path)


def _resolve_product_spatial_reference(request: object, *, source_local_allowed: bool):
    """Resolve request CRS and block source-local use for spatial comparisons."""
    polygon_required = bool(
        getattr(request, "crop_polygon", None)
        or getattr(request, "crop_polygon_path", None)
        or getattr(request, "polygon_execution_input", None)
        or getattr(request, "reproject", False)
    )
    resolution = SpatialReferenceResolver().resolve(
        Path(getattr(request, "input_path")),
        embedded_crs=str(getattr(request, "crs", "") or ""),
        spatial_alignment_required=polygon_required,
        source_local_allowed=source_local_allowed,
    )
    if polygon_required and not resolution.safe_for_spatial_alignment:
        raise ProcessingError(
            "PyForestScan cannot align this LiDAR with the selected polygon because the LiDAR coordinate system is unknown. "
            "Assign the source or repository CRS, then run Prerun Check again."
        )
    if not resolution.resolved and resolution.status is not SpatialReferenceStatus.SOURCE_LOCAL_ONLY:
        raise ProcessingError("The LiDAR coordinate system could not be resolved for this operation.")
    return resolution


def _read_source_local_lidar(request: object) -> object:
    """Read LAS/LAZ/COPC coordinates without injecting a false spatial reference."""
    if any(getattr(request, name, None) for name in ("bounds", "crop_polygon", "crop_polygon_path", "polygon_execution_input")):
        raise ProcessingError("Source-local reads cannot perform polygon alignment or transformed bounded selection.")
    path = Path(getattr(request, "input_path"))
    lowered = str(path).lower()
    reader_type = "readers.ept" if lowered.endswith("ept.json") else ("readers.copc" if lowered.endswith((".copc.laz", ".copc")) else "readers.las")
    pdal = _import_required("pdal", ProcessingError)
    pipeline = pdal.Pipeline(json.dumps({"pipeline": [{"type": reader_type, "filename": str(path)}]}))
    pipeline.execute()
    arrays = tuple(pipeline.arrays or ())
    if not arrays:
        raise ProcessingError("PDAL returned no point data for source-local processing.")
    return arrays


def _write_source_local_geotiff(values: object, output_path: Path, extent: object, *, product: str, nodata: float = -9999.0) -> None:
    """Write an explicitly unassigned source-coordinate GeoTIFF."""
    rasterio = _import_required("rasterio", ProcessingError)
    numpy = _import_required("numpy", ProcessingError)
    from rasterio.transform import from_bounds
    array = numpy.asarray(values)
    if array.ndim != 2 or not array.size:
        raise ProcessingError(f"{product} source-local raster has invalid dimensions.")
    xmin, xmax, ymin, ymax = extent
    raster = array.T
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", driver="GTiff", height=raster.shape[0], width=raster.shape[1], count=1, dtype="float32", crs=None, transform=from_bounds(xmin, ymin, xmax, ymax, raster.shape[1], raster.shape[0]), nodata=nodata, compress="deflate") as dataset:
        dataset.write(numpy.where(numpy.isfinite(raster), raster, nodata).astype("float32"), 1)
        dataset.update_tags(PRODUCT=product, **_source_local_raster_tags())


def _source_local_raster_tags() -> dict[str, str]:
    """Return the single metadata contract for unassigned source-coordinate rasters."""
    return {
        "PYFORESTSCAN_SPATIAL_REFERENCE": "SOURCE_LOCAL",
        "PYFORESTSCAN_SPATIAL_REFERENCE_MODE": "SOURCE_LOCAL",
        "SOURCE_CRS_RESOLVED": "false",
        "SOURCE_CRS_STATUS": "SOURCE_LOCAL_ONLY",
        "SOURCE_CRS": "",
        "OUTPUT_CRS": "",
        "CRS_RESOLUTION_SOURCE": "source_local",
        "CRS_CONFIDENCE": "NONE",
        "TRANSFORMATION_APPLIED": "false",
        "SOURCE_COORDINATE_UNITS": "unknown",
        "CRS_ASSIGNMENT_REQUIRED_FOR_SPATIAL_ALIGNMENT": "true",
    }


def _canonicalize_hag_dimension(point_array: object) -> tuple[object, PointDimensionCapabilities]:
    """Preserve all fields while exposing a supported HAG alias canonically."""
    names = getattr(getattr(point_array, "dtype", None), "names", ()) or ()
    capabilities = PointDimensionCapabilities.from_names(names)
    if not capabilities.has_existing_hag or capabilities.hag_dimension_name == "HeightAboveGround":
        return point_array, capabilities
    numpy = _import_required("numpy", ProcessingError)
    source = capabilities.hag_dimension_name
    dtype = [("HeightAboveGround" if name == source else name, point_array.dtype.fields[name][0]) for name in names]
    normalized = numpy.empty(point_array.shape, dtype=dtype)
    for name in names:
        normalized["HeightAboveGround" if name == source else name] = point_array[name]
    return normalized, PointDimensionCapabilities.from_names(normalized.dtype.names)


def _write_source_local_adapter_trace(request: object, stage: str, payload: dict[str, object]) -> None:
    """Persist compact execution evidence when a diagnostics path is available."""
    diagnostics = getattr(request, "diagnostics_path", None)
    if not diagnostics:
        diagnostics = Path(getattr(request, "output_path")).parent / "diagnostics"
    path = Path(diagnostics) / "source_local_trace.json"
    try:
        trace = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"stages": {}}
    except (OSError, json.JSONDecodeError):
        trace = {"stages": {}}
    trace.setdefault("stages", {})[stage] = payload
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _backend_user_error(product: ProductType, exc: Exception) -> str:
    """Return one actionable message while diagnostics retain the full chain."""
    text = str(exc)
    if "SOURCE_DIMENSION_MISMATCH" in text:
        detail = text[text.index("SOURCE_DIMENSION_MISMATCH"):].split("; The backend", 1)[0]
        return f"{product.value.upper()} could not be created. The backend did not detect the expected normalized-height field. {detail}"
    if "Processing backend needs an update" in text or "BACKEND_CONTRACT_MISMATCH" in text:
        return "Processing backend needs an update. Open Tools & Setup and choose Repair Backend."
    parts = [part.strip() for part in text.replace("The backend job failed before completion.;", "").split(";") if part.strip()]
    reason = parts[-1] if parts else text
    return f"{product.value.upper()} could not be created. Reason: {reason}"


def _write_crs_provenance(output_path: Path, resolution: object) -> None:
    """Attach resolution provenance without changing raster coordinates."""
    if output_path.suffix.lower() not in {".tif", ".tiff"} or not output_path.exists():
        return
    try:
        rasterio = _import_required("rasterio", ProcessingError)
        with rasterio.open(output_path, "r+") as dataset:
            dataset.update_tags(PYFORESTSCAN_SPATIAL_REFERENCE="SOURCE_LOCAL" if resolution.status is SpatialReferenceStatus.SOURCE_LOCAL_ONLY else "RESOLVED", SOURCE_CRS_RESOLVED="false" if resolution.status is SpatialReferenceStatus.SOURCE_LOCAL_ONLY else "true", SOURCE_CRS_STATUS=resolution.status.value, SOURCE_CRS=resolution.resolved_crs, OUTPUT_CRS=resolution.resolved_crs, CRS_RESOLUTION_SOURCE=resolution.source, CRS_CONFIDENCE=resolution.confidence.value, TRANSFORMATION_APPLIED="true" if resolution.transformation_required else "false")
    except Exception:
        return


def _write_multiband_geotiff(layer: object, output_path: Path, crs: str, spatial_extent: object, nodata: float = -9999.0, *, voxel_height: float = 1.0, beer_lambert_constant: float = 1.0, drop_ground: bool = True) -> None:
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
        try:
            dataset.update_tags(**pad_metadata_tags(voxel_height, beer_lambert_constant, drop_ground, bands))
        except Exception:
            pass
        for mapping in pad_band_mapping(bands, voxel_height, drop_ground=drop_ground):
            band_number = mapping.band_index
            dataset.write(data[:, :, band_number - 1].T, band_number)
            try:
                dataset.set_band_description(band_number, mapping.description)
                dataset.update_tags(band_number, height_min=f"{mapping.min_height:g}", height_max=f"{mapping.max_height:g}", units="map_units")
            except Exception:
                pass


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


def _validate_created_point_cloud_output(output_path: Path) -> None:
    """Require the PyForestScan LAS/LAZ writer to create a usable file."""
    if not output_path.exists():
        raise ProcessingError(f"Point-cloud output was not created: {output_path}")
    try:
        if output_path.stat().st_size <= 0:
            raise ProcessingError(f"Point-cloud output is empty: {output_path}")
    except OSError as exc:
        raise ProcessingError(f"Point-cloud output could not be inspected: {output_path}") from exc


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
    resolved = resolve_ept_spatial_reference(metadata)
    return resolved.crs_text if resolved.valid else None


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
