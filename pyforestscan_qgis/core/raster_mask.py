"""Exact polygon masking services for generated raster outputs."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

RASTER_SUFFIXES = {".tif", ".tiff"}
DEFAULT_POLYGON_NODATA = -9999.0


@dataclass(frozen=True)
class RasterMaskOptions:
    engine: str = "automatic"
    all_touched: bool = False
    crop_to_polygon_extent: bool = False
    nodata: float = DEFAULT_POLYGON_NODATA
    retain_unmasked_intermediate: bool = False
    fallback_allowed: bool = True


@dataclass(frozen=True)
class RasterMaskResult:
    path: Path
    status: str
    message: str
    engine: str = "none"
    output_path: Path | None = None
    intermediate_path: Path | None = None
    masked: bool = False
    nodata: float | None = None
    band_count: int | None = None


class BackendRasterMaskService:
    """Rasterio/GDAL-backed exact polygon masking for PBM/headless finalization."""

    engine_name = "backend_rasterio_mask"

    def mask(
        self,
        path: Path | str,
        polygon_wkt: str,
        *,
        polygon_crs: str,
        processing_crs: str,
        options: RasterMaskOptions | None = None,
    ) -> RasterMaskResult:
        options = options or RasterMaskOptions()
        path = Path(path)
        try:
            import rasterio  # type: ignore
            from rasterio.features import geometry_mask  # type: ignore
            from rasterio.mask import mask as rasterio_mask  # type: ignore
            from shapely import wkt as shapely_wkt  # type: ignore
            from shapely.geometry import mapping  # type: ignore
        except Exception as exc:  # noqa: BLE001
            return RasterMaskResult(path, "skipped", f"Raster masking dependencies unavailable: {exc}", engine=self.engine_name)
        try:
            geometry = shapely_wkt.loads(polygon_wkt)
            if geometry.is_empty:
                return RasterMaskResult(path, "failed", "Raster masking failed: polygon geometry is empty.", engine=self.engine_name)
            if not geometry.is_valid:
                geometry = geometry.buffer(0)
            shapes = [mapping(geometry)]
            tmp_path = _temporary_mask_path(path)
            intermediate_path = None
            if options.retain_unmasked_intermediate:
                intermediate_path = path.with_name(f"{path.stem}_unmasked{path.suffix}")
                if not intermediate_path.exists():
                    intermediate_path.write_bytes(path.read_bytes())
            with rasterio.open(path) as source:
                nodata = source.nodata if source.nodata is not None else options.nodata
                profile = source.profile.copy()
                tags = source.tags()
                band_tags = {index: source.tags(index) for index in range(1, source.count + 1)}
                descriptions = tuple(source.descriptions)
                if options.crop_to_polygon_extent:
                    data, transform = rasterio_mask(source, shapes, crop=True, filled=True, nodata=nodata, all_touched=options.all_touched)
                    profile.update(height=data.shape[1], width=data.shape[2], transform=transform, nodata=nodata)
                else:
                    data = source.read()
                    inside = geometry_mask(
                        shapes,
                        out_shape=(source.height, source.width),
                        transform=source.transform,
                        invert=True,
                        all_touched=options.all_touched,
                    )
                    data[:, ~inside] = nodata
                    profile.update(nodata=nodata)
            profile.setdefault("compress", "deflate")
            with rasterio.open(tmp_path, "w", **profile) as target:
                target.write(data)
                target.update_tags(**tags)
                target.update_tags(
                    pyforestscan_polygon_clip="true",
                    pyforestscan_polygon_crs=polygon_crs,
                    pyforestscan_processing_crs=processing_crs,
                    pyforestscan_mask_engine=self.engine_name,
                    pyforestscan_mask_nodata=str(nodata),
                    pyforestscan_mask_all_touched=str(options.all_touched).lower(),
                    pyforestscan_mask_crop_to_polygon_extent=str(options.crop_to_polygon_extent).lower(),
                )
                for index, description in enumerate(descriptions, start=1):
                    if description:
                        target.set_band_description(index, description)
                    if band_tags.get(index):
                        target.update_tags(index, **band_tags[index])
            os.replace(tmp_path, path)
            return RasterMaskResult(path, "masked", "Raster cells outside the exact polygon were set to NoData.", engine=self.engine_name, output_path=path, intermediate_path=intermediate_path, masked=True, nodata=float(nodata), band_count=int(data.shape[0]))
        except Exception as exc:  # noqa: BLE001
            try:
                if "tmp_path" in locals() and Path(tmp_path).exists():
                    Path(tmp_path).unlink()
            except OSError:
                pass
            return RasterMaskResult(path, "failed", f"Raster masking failed: {exc}", engine=self.engine_name)


class QgisRasterMaskService:
    """Thin wrapper around QGIS/GDAL Clip Raster by Mask Layer when available."""

    engine_name = "qgis_gdal_mask"
    algorithm_id = "gdal:cliprasterbymasklayer"

    def __init__(self, processing_module: Any | None = None, registry: Any | None = None) -> None:
        self.processing_module = processing_module
        self.registry = registry

    def available(self) -> bool:
        try:
            registry = self.registry
            if registry is None:
                from qgis.core import QgsApplication  # type: ignore

                registry = QgsApplication.processingRegistry()
            return registry.algorithmById(self.algorithm_id) is not None
        except Exception:
            return False

    def build_parameters(
        self,
        *,
        input_path: Path,
        mask_path: Path,
        output_path: Path,
        nodata: float,
        all_touched: bool = False,
        crop_to_polygon_extent: bool = False,
    ) -> dict[str, Any]:
        return {
            "INPUT": str(input_path),
            "MASK": str(mask_path),
            "NODATA": nodata,
            "ALPHA_BAND": False,
            "CROP_TO_CUTLINE": crop_to_polygon_extent,
            "KEEP_RESOLUTION": True,
            "OPTIONS": "COMPRESS=DEFLATE",
            "DATA_TYPE": 0,
            "OUTPUT": str(output_path),
            "EXTRA": "-wo CUTLINE_ALL_TOUCHED=TRUE" if all_touched else "",
        }


def is_maskable_raster(path: Path | str) -> bool:
    return Path(path).suffix.lower() in RASTER_SUFFIXES


def apply_polygon_mask_to_outputs(
    paths: Iterable[Path | str],
    polygon_wkt: str,
    *,
    polygon_crs: str,
    processing_crs: str,
    options: RasterMaskOptions | None = None,
) -> tuple[RasterMaskResult, ...]:
    """Apply exact polygon NoData masking to GeoTIFF outputs."""
    results: list[RasterMaskResult] = []
    service = BackendRasterMaskService()
    for value in paths:
        path = Path(value)
        if not is_maskable_raster(path):
            continue
        results.append(service.mask(path, polygon_wkt, polygon_crs=polygon_crs, processing_crs=processing_crs, options=options))
    return tuple(results)


def mask_geotiff_to_polygon(
    path: Path | str,
    polygon_wkt: str,
    *,
    polygon_crs: str,
    processing_crs: str,
    nodata: float = DEFAULT_POLYGON_NODATA,
) -> RasterMaskResult:
    return BackendRasterMaskService().mask(
        path,
        polygon_wkt,
        polygon_crs=polygon_crs,
        processing_crs=processing_crs,
        options=RasterMaskOptions(nodata=nodata),
    )


def _temporary_mask_path(path: Path) -> Path:
    fd, text = tempfile.mkstemp(prefix=f".{path.stem}.masking.", suffix=path.suffix, dir=str(path.parent))
    os.close(fd)
    return Path(text)
