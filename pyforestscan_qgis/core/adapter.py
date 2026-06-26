"""Architecture-only adapter boundary around PyForestScan and PDAL.

This module validates and inspects datasets, exposes typed results, and
centralizes PyForestScan imports behind a plugin-owned API. CHM and canopy cover
are implemented; PAI, PAD, FHD, and rumple remain unimplemented.
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
    LogContextItem,
    LogLevel,
    LogRecord,
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
            raise ProcessingError("CHM grid resolution must be greater than zero.")
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
                (request.grid_resolution, request.grid_resolution),
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


    def create_canopy_cover(self, request: CanopyCoverRequest) -> CanopyCoverResult:
        """Generate a canopy cover GeoTIFF through PyForestScan.

        PAD is computed only as an internal prerequisite. The adapter does not
        expose PAD as a product in this phase.
        """
        if request.grid_resolution <= 0:
            raise ProcessingError("Canopy cover grid resolution must be greater than zero.")
        if request.voxel_height <= 0:
            raise ProcessingError("Canopy cover voxel height must be greater than zero.")
        if request.canopy_height_threshold < 0:
            raise ProcessingError("Canopy cover height threshold must be zero or greater.")
        if request.extinction_coefficient < 0:
            raise ProcessingError("Canopy cover extinction coefficient must be zero or greater.")
        if not request.crs:
            raise ProcessingError("Canopy cover generation requires a dataset CRS.")
        output_path = Path(request.output_path)
        _validate_output_path(output_path)
        self._progress.start("Reading lidar for canopy cover")
        self._log(LogLevel.INFO, "Starting canopy cover generation", input=str(request.input_path), output=str(output_path))
        try:
            pyforestscan = _import_required("pyforestscan", ProcessingError)
            handlers = _import_required("pyforestscan.handlers", ProcessingError)
            point_cloud = handlers.read_lidar(str(request.input_path), request.crs, hag=True)
            if point_cloud is None:
                raise ProcessingError("PyForestScan returned no point data for canopy cover generation.")
            self._progress.update(25, "Point cloud loaded")
            point_array = _merge_point_cloud_arrays(point_cloud)
            names = getattr(point_array.dtype, "names", ()) or ()
            required = {"X", "Y", "HeightAboveGround"}
            missing = sorted(required.difference(names))
            if missing:
                raise ProcessingError(f"Canopy cover input is missing required dimensions: {', '.join(missing)}")
            voxel_returns, extent = pyforestscan.assign_voxels(
                point_array,
                (request.grid_resolution, request.grid_resolution, request.voxel_height),
            )
            self._progress.update(45, "Voxel returns calculated")
            pad = pyforestscan.calculate_pad(voxel_returns, voxel_height=request.voxel_height)
            self._progress.update(65, "Internal PAD prerequisite calculated")
            canopy_cover = pyforestscan.calculate_canopy_cover(
                pad,
                request.voxel_height,
                min_height=request.canopy_height_threshold,
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


def _validate_output_path(output_path: Path) -> None:
    """Validate that a CHM output path can be written."""
    if output_path.suffix.lower() not in {".tif", ".tiff"}:
        raise ProcessingError("CHM output filename must end with .tif or .tiff.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not output_path.parent.is_dir():
        raise ProcessingError(f"CHM output folder is not available: {output_path.parent}")
    probe = output_path.parent / f".{output_path.name}.write-test"
    try:
        probe.write_text("", encoding="utf-8")
    except OSError as exc:
        raise ProcessingError(f"CHM output folder is not writable: {output_path.parent}") from exc
    finally:
        try:
            probe.unlink()
        except OSError:
            pass


def _validate_created_output(output_path: Path) -> None:
    """Require the PyForestScan GeoTIFF writer to create a usable file."""
    if not output_path.exists():
        raise ProcessingError(f"CHM GeoTIFF was not created: {output_path}")
    try:
        if output_path.stat().st_size <= 0:
            raise ProcessingError(f"CHM GeoTIFF is empty: {output_path}")
    except OSError as exc:
        raise ProcessingError(f"CHM GeoTIFF could not be inspected: {output_path}") from exc


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
