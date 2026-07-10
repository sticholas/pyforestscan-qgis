"""Best-effort exact polygon masking for generated raster outputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

RASTER_SUFFIXES = {".tif", ".tiff"}
DEFAULT_POLYGON_NODATA = -9999.0


@dataclass(frozen=True)
class RasterMaskResult:
    path: Path
    status: str
    message: str


def is_maskable_raster(path: Path | str) -> bool:
    return Path(path).suffix.lower() in RASTER_SUFFIXES


def apply_polygon_mask_to_outputs(paths: Iterable[Path | str], polygon_wkt: str, *, polygon_crs: str, processing_crs: str, nodata: float = DEFAULT_POLYGON_NODATA) -> tuple[RasterMaskResult, ...]:
    """Apply polygon NoData masking to GeoTIFF outputs when rasterio/shapely are available."""
    results: list[RasterMaskResult] = []
    for value in paths:
        path = Path(value)
        if not is_maskable_raster(path):
            continue
        results.append(mask_geotiff_to_polygon(path, polygon_wkt, polygon_crs=polygon_crs, processing_crs=processing_crs, nodata=nodata))
    return tuple(results)


def mask_geotiff_to_polygon(path: Path | str, polygon_wkt: str, *, polygon_crs: str, processing_crs: str, nodata: float = DEFAULT_POLYGON_NODATA) -> RasterMaskResult:
    path = Path(path)
    try:
        import rasterio  # type: ignore
        from rasterio.features import geometry_mask  # type: ignore
        from shapely import wkt as shapely_wkt  # type: ignore
        from shapely.geometry import mapping  # type: ignore
    except Exception as exc:  # noqa: BLE001
        return RasterMaskResult(path, "skipped", f"Raster masking dependencies unavailable: {exc}")
    try:
        geometry = shapely_wkt.loads(polygon_wkt)
        with rasterio.open(path, "r+") as dataset:
            existing_nodata = dataset.nodata if dataset.nodata is not None else nodata
            outside = geometry_mask(
                [mapping(geometry)],
                out_shape=(dataset.height, dataset.width),
                transform=dataset.transform,
                invert=True,
            )
            for band_index in range(1, dataset.count + 1):
                data = dataset.read(band_index)
                data[~outside] = existing_nodata
                dataset.write(data, band_index)
            dataset.nodata = existing_nodata
            dataset.update_tags(
                pyforestscan_polygon_clip="true",
                pyforestscan_polygon_crs=polygon_crs,
                pyforestscan_processing_crs=processing_crs,
                pyforestscan_mask_nodata=str(existing_nodata),
            )
        return RasterMaskResult(path, "masked", "Raster cells outside the exact polygon were set to NoData.")
    except Exception as exc:  # noqa: BLE001
        return RasterMaskResult(path, "failed", f"Raster masking failed: {exc}")
