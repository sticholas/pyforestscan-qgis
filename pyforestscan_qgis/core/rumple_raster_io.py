"""GDAL-backed adaptive Rumple raster generation and scalar inspection."""
from __future__ import annotations
from pathlib import Path

from .localized_rumple import calculate_local_rumple_surface
from .rumple_adaptive import RumpleTotals, totals_from_values


def create_rumple_raster_from_chm(chm_path: Path | str, output_path: Path | str, *, min_height: float | None = None, nodata: float = -9999.0) -> RumpleTotals:
    from osgeo import gdal
    import numpy as np
    source = gdal.Open(str(chm_path), gdal.GA_ReadOnly)
    if source is None:
        raise RuntimeError(f"Could not open supporting CHM: {chm_path}")
    band = source.GetRasterBand(1)
    values = band.ReadAsArray().astype(float)
    source_nodata = band.GetNoDataValue()
    if source_nodata is not None:
        values[values == source_nodata] = np.nan
    transform = source.GetGeoTransform()
    resolution = (abs(float(transform[1])), abs(float(transform[5])))
    surface = calculate_local_rumple_surface(values, resolution, min_height)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".partial.tif")
    dataset = gdal.GetDriverByName("GTiff").Create(str(temporary), surface.values.shape[1], surface.values.shape[0], 1, gdal.GDT_Float32, options=("TILED=YES", "COMPRESS=DEFLATE"))
    if dataset is None:
        raise RuntimeError("Could not create adaptive Rumple raster.")
    dataset.SetGeoTransform((transform[0] + resolution[0] / 2.0, transform[1], 0.0, transform[3] - resolution[1] / 2.0, 0.0, transform[5]))
    dataset.SetProjection(source.GetProjection())
    out_band = dataset.GetRasterBand(1)
    out_band.SetNoDataValue(nodata)
    out_band.SetDescription("Rumple Index")
    written = np.where(np.isfinite(surface.values), surface.values, nodata).astype("float32")
    out_band.WriteArray(written)
    dataset.SetMetadata({"PRODUCT": "Rumple Index", "METHOD": "pyforestscan_qgis_patch_surface_v1", "RUMPLE_ANALYSIS_SCALE": "2x2 CHM patch", "CHM_RESOLUTION": str(resolution), "MIN_HEIGHT": str(min_height), "UNITS": "dimensionless"})
    out_band.FlushCache()
    dataset = None
    source = None
    temporary.replace(target)
    return totals_from_values(written, resolution[0], nodata=nodata)


def raster_totals(path: Path | str) -> RumpleTotals:
    from osgeo import gdal
    dataset = gdal.Open(str(path), gdal.GA_ReadOnly)
    if dataset is None:
        raise RuntimeError(f"Could not open Rumple raster: {path}")
    band = dataset.GetRasterBand(1)
    values = band.ReadAsArray()
    transform = dataset.GetGeoTransform()
    totals = totals_from_values(values, abs(float(transform[1])), nodata=band.GetNoDataValue() if band.GetNoDataValue() is not None else -9999.0)
    dataset = None
    return totals


def write_rumple_summary(path: Path | str, totals: RumpleTotals, *, valid_primary: Path | str, method: str = "planar-area-weighted valid final raster cores") -> Path:
    import csv
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("metric", "value"))
        writer.writerow(("rumple_index", f"{totals.rumple_index:.12g}"))
        writer.writerow(("surface_area_sum", f"{totals.surface_area_sum:.12g}"))
        writer.writerow(("planar_area_sum", f"{totals.planar_area_sum:.12g}"))
        writer.writerow(("valid_patch_count", totals.valid_patch_count))
        writer.writerow(("aggregation", method))
        writer.writerow(("primary_raster", str(valid_primary)))
    return target


__all__ = ["create_rumple_raster_from_chm", "raster_totals", "write_rumple_summary"]
