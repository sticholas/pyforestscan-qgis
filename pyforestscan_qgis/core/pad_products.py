"""PAD volume metadata and derived visualization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

PadDerivativeType = Literal["slice", "maximum", "mean", "integrated"]


@dataclass(frozen=True)
class PadBandMapping:
    """Height interval represented by one PAD GeoTIFF band."""

    band_index: int
    min_height: float
    max_height: float
    description: str


@dataclass(frozen=True)
class PadDerivativeSpec:
    """Specification for one 2D visualization derived from a full PAD volume."""

    derivative_type: PadDerivativeType
    output_path: Path
    voxel_height: float
    min_height: float | None = None
    max_height: float | None = None
    slice_height: float | None = None
    band_index: int | None = None


def pad_band_mapping(band_count: int, voxel_height: float, *, drop_ground: bool = True) -> tuple[PadBandMapping, ...]:
    """Return one-based PAD band descriptions for height-bin metadata."""
    if band_count <= 0:
        raise ValueError("PAD band count must be greater than zero.")
    if voxel_height <= 0:
        raise ValueError("PAD voxel height must be greater than zero.")
    ground_offset = 1 if drop_ground else 0
    mapping: list[PadBandMapping] = []
    for band in range(1, band_count + 1):
        lower = (band - 1 + ground_offset) * voxel_height
        upper = lower + voxel_height
        mapping.append(PadBandMapping(band, lower, upper, f"PAD {lower:g}-{upper:g} m"))
    return tuple(mapping)


def pad_metadata_tags(voxel_height: float, beer_lambert_constant: float, drop_ground: bool, band_count: int) -> dict[str, str]:
    """Return dataset-level metadata tags for authoritative PAD volume outputs."""
    mapping = pad_band_mapping(band_count, voxel_height, drop_ground=drop_ground)
    return {
        "pyforestscan_product": "Plant Area Density (PAD)",
        "pyforestscan_representation": "3D height-binned volume stored as multiband GeoTIFF",
        "voxel_height": f"{voxel_height:g}",
        "beer_lambert_constant": f"{beer_lambert_constant:g}",
        "drop_ground": str(bool(drop_ground)).lower(),
        "height_bin_count": str(band_count),
        "band_height_mapping": "; ".join(f"{item.band_index}:{item.min_height:g}-{item.max_height:g}m" for item in mapping),
        "units": "PAD per height bin; heights in CRS vertical/map units, normally meters",
    }


def select_pad_slice_band(slice_height: float | None, band_index: int | None, band_count: int, voxel_height: float, *, drop_ground: bool = True) -> int:
    """Select a one-based PAD band for a requested height or explicit band index."""
    if band_count <= 0:
        raise ValueError("PAD band count must be greater than zero.")
    if band_index is not None:
        if not 1 <= band_index <= band_count:
            raise ValueError("PAD band index is outside the available band range.")
        return band_index
    if slice_height is None:
        return min(band_count, max(1, round(10.0 / voxel_height)))
    if slice_height < 0:
        raise ValueError("PAD slice height must be zero or greater.")
    ground_offset = 1 if drop_ground else 0
    selected = int(slice_height // voxel_height) + 1 - ground_offset
    return min(band_count, max(1, selected))


def pad_band_indices_for_range(band_count: int, voxel_height: float, min_height: float | None, max_height: float | None, *, drop_ground: bool = True) -> tuple[int, ...]:
    """Return one-based PAD bands whose height intervals overlap a vertical range."""
    if min_height is not None and min_height < 0:
        raise ValueError("PAD minimum height must be zero or greater.")
    if max_height is not None and max_height <= (min_height or 0.0):
        raise ValueError("PAD maximum height must be greater than minimum height.")
    selected = []
    for item in pad_band_mapping(band_count, voxel_height, drop_ground=drop_ground):
        overlaps_min = min_height is None or item.max_height > min_height
        overlaps_max = max_height is None or item.min_height < max_height
        if overlaps_min and overlaps_max:
            selected.append(item.band_index)
    if not selected:
        raise ValueError("No PAD bands overlap the requested vertical range.")
    return tuple(selected)


def pad_derivative_filename(derivative_type: PadDerivativeType, *, slice_height: float | None = None, min_height: float | None = None, max_height: float | None = None) -> str:
    """Return a meaningful default filename for a PAD visualization derivative."""
    if derivative_type == "slice":
        height = 10.0 if slice_height is None else slice_height
        return f"pad_slice_{_height_label(height)}.tif"
    if derivative_type in {"maximum", "mean", "integrated"}:
        prefix = {"maximum": "pad_max", "mean": "pad_mean", "integrated": "pad_integrated"}[derivative_type]
        if min_height is None and max_height is None:
            return f"{prefix}_all_heights.tif"
        return f"{prefix}_{_height_label(min_height or 0.0)}_{_height_label(max_height or 0.0)}.tif"
    raise ValueError(f"Unsupported PAD derivative type: {derivative_type}")


def calculate_pad_derivative(pad_volume, spec: PadDerivativeSpec, *, drop_ground: bool = True):
    """Calculate a 2D PAD derivative from a full X/Y/Z PAD volume."""
    try:
        import numpy
    except Exception as exc:  # pragma: no cover - numpy is available in test/runtime envs.
        raise RuntimeError("PAD derivatives require numpy.") from exc
    data = numpy.asarray(pad_volume)
    if data.ndim != 3:
        raise ValueError("PAD derivatives require a 3D X/Y/Z PAD volume.")
    band_count = int(data.shape[2])
    if spec.derivative_type == "slice":
        band = select_pad_slice_band(spec.slice_height, spec.band_index, band_count, spec.voxel_height, drop_ground=drop_ground)
        return data[:, :, band - 1]
    bands = pad_band_indices_for_range(band_count, spec.voxel_height, spec.min_height, spec.max_height, drop_ground=drop_ground)
    subset = data[:, :, [band - 1 for band in bands]]
    if spec.derivative_type == "maximum":
        return numpy.nanmax(subset, axis=2)
    if spec.derivative_type == "mean":
        return numpy.nanmean(subset, axis=2)
    if spec.derivative_type == "integrated":
        return numpy.nansum(subset, axis=2) * spec.voxel_height
    raise ValueError(f"Unsupported PAD derivative type: {spec.derivative_type}")


def _height_label(value: float) -> str:
    text = f"{value:g}".replace("-", "minus_").replace(".", "p")
    return f"{text}m"
