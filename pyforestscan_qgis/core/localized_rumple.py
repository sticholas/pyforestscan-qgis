"""Localized Rumple raster extension helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class LocalRumpleSurface:
    """Patch-centered Rumple field and scalar compatibility evidence."""
    values: object
    surface_areas: object
    valid_mask: object
    cell_resolution: tuple[float,float]
    valid_patch_count: int
    surface_area: float
    planar_area: float
    aggregate_rumple: float

def calculate_local_rumple_surface(chm, cell_resolution, min_height=None):
    """Calculate the exact two-triangle Rumple ratio for every 2x2 CHM patch."""
    import numpy as np
    data=np.asarray(chm,dtype=float)
    if data.ndim!=2:raise ValueError(f"chm must be a 2D array (got shape {data.shape})")
    if len(cell_resolution)!=2:raise ValueError("cell_resolution must be a (dx, dy) tuple")
    dx,dy=map(float,cell_resolution)
    if dx<=0 or dy<=0:raise ValueError("cell_resolution components must be > 0")
    if min_height is not None:data=np.where(data>=float(min_height),data,np.nan)
    shape=(max(0,data.shape[0]-1),max(0,data.shape[1]-1))
    if data.shape[0]<2 or data.shape[1]<2:
        empty=np.full(shape,np.nan,dtype=float);valid=np.zeros(shape,dtype=bool)
        return LocalRumpleSurface(empty,empty.copy(),valid,(dx,dy),0,0.0,0.0,float("nan"))
    z00,z10,z01,z11=data[:-1,:-1],data[1:,:-1],data[:-1,1:],data[1:,1:]
    valid=np.isfinite(z00)&np.isfinite(z10)&np.isfinite(z01)&np.isfinite(z11)
    tri1=.5*np.sqrt((dy*(z10-z00))**2+(dx*(z01-z00))**2+(dx*dy)**2)
    tri2=.5*np.sqrt((dy*(z01-z11))**2+(dx*(z11-z10))**2+(dx*dy)**2)
    areas=np.where(valid,tri1+tri2,np.nan);values=areas/(dx*dy)
    count=int(np.count_nonzero(valid));surface=float(np.sum(areas[valid],dtype=float)) if count else 0.0;planar=count*dx*dy
    return LocalRumpleSurface(values,areas,valid,(dx,dy),count,surface,planar,surface/planar if planar else float("nan"))

def rumple_patch_extent(chm_extent, cell_resolution):
    """Return bounds inset half a CHM cell so pixels are patch-centered."""
    xmin,xmax,ymin,ymax=map(float,chm_extent);dx,dy=map(float,cell_resolution)
    return (xmin+dx/2,xmax-dx/2,ymin+dy/2,ymax-dy/2)


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
    surface=calculate_local_rumple_surface(masked,cell_resolution)
    return surface.aggregate_rumple if surface.valid_patch_count else nodata


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
