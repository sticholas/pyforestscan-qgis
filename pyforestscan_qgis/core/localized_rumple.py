"""Localized Rumple raster extension helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LocalizedRumpleSpec:
    """Parameters for the plugin-derived localized Rumple extension."""

    output_path: Path
    cell_resolution: tuple[float, float]
    window_width: int = 5
    window_height: int = 5
    stride: int = 1
    min_valid_fraction: float = 0.75
    min_height: float | None = None
    nodata: float = -9999.0


def calculate_rumple_from_chm_window(chm_window, cell_resolution: tuple[float, float], *, min_height: float | None = None, min_valid_fraction: float = 0.75, nodata: float = -9999.0) -> float:
    """Calculate surface-area ratio for one CHM window."""
    import numpy

    data = numpy.asarray(chm_window, dtype=float)
    if data.ndim != 2 or data.size == 0:
        return nodata
    valid = numpy.isfinite(data)
    if min_height is not None:
        valid &= data >= min_height
    if valid.sum() / data.size < min_valid_fraction:
        return nodata
    masked = numpy.where(valid, data, numpy.nan)
    if masked.shape[0] < 2 or masked.shape[1] < 2:
        return nodata
    dx, dy = float(cell_resolution[0]), float(cell_resolution[1])
    if dx <= 0 or dy <= 0:
        raise ValueError("Cell resolution must be positive.")
    z00 = masked[:-1, :-1]
    z10 = masked[1:, :-1]
    z01 = masked[:-1, 1:]
    z11 = masked[1:, 1:]
    quad_valid = numpy.isfinite(z00) & numpy.isfinite(z10) & numpy.isfinite(z01) & numpy.isfinite(z11)
    if not quad_valid.any():
        return nodata
    p00 = numpy.stack([numpy.zeros_like(z00), numpy.zeros_like(z00), z00], axis=-1)
    p10 = numpy.stack([numpy.full_like(z10, dx), numpy.zeros_like(z10), z10], axis=-1)
    p01 = numpy.stack([numpy.zeros_like(z01), numpy.full_like(z01, dy), z01], axis=-1)
    p11 = numpy.stack([numpy.full_like(z11, dx), numpy.full_like(z11, dy), z11], axis=-1)
    tri1 = 0.5 * numpy.linalg.norm(numpy.cross(p10 - p00, p01 - p00), axis=-1)
    tri2 = 0.5 * numpy.linalg.norm(numpy.cross(p11 - p10, p01 - p10), axis=-1)
    surface_area = numpy.nansum(numpy.where(quad_valid, tri1 + tri2, numpy.nan))
    planimetric_area = float(quad_valid.sum()) * dx * dy
    if planimetric_area <= 0:
        return nodata
    return float(surface_area / planimetric_area)


def calculate_localized_rumple(chm, spec: LocalizedRumpleSpec):
    """Calculate a localized Rumple raster from a CHM using moving windows."""
    import numpy

    data = numpy.asarray(chm, dtype=float)
    if data.ndim != 2:
        raise ValueError("Localized Rumple requires a 2D CHM array.")
    if spec.window_width < 2 or spec.window_height < 2:
        raise ValueError("Localized Rumple windows must be at least 2 by 2 cells.")
    if spec.stride <= 0:
        raise ValueError("Localized Rumple stride must be positive.")
    rows = max(0, (data.shape[0] - spec.window_height) // spec.stride + 1)
    cols = max(0, (data.shape[1] - spec.window_width) // spec.stride + 1)
    result = numpy.full((rows, cols), spec.nodata, dtype=float)
    for row in range(rows):
        for col in range(cols):
            y = row * spec.stride
            x = col * spec.stride
            window = data[y : y + spec.window_height, x : x + spec.window_width]
            result[row, col] = calculate_rumple_from_chm_window(
                window,
                spec.cell_resolution,
                min_height=spec.min_height,
                min_valid_fraction=spec.min_valid_fraction,
                nodata=spec.nodata,
            )
    return result
