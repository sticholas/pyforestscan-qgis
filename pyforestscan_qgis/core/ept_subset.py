"""QGIS-free request models and validation for EPT subset extraction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ept_bounds import EptBounds
from .exceptions import ProcessingError

BoundsTuple = tuple[tuple[float, float], ...]
LAS_LAZ_SUFFIXES = {".las", ".laz"}


@dataclass(frozen=True)
class EptSubsetRequest:
    """A validated request to read an EPT subset and write LAS/LAZ output."""

    input_path: Path | str
    crs: str
    output_path: Path
    bounds: BoundsTuple | None = None
    thin_radius: float | None = None
    hag: bool = False
    hag_dtm: bool = False
    dtm_path: Path | None = None
    crop_poly: bool = False
    poly: str | Path | None = None
    reproject: bool = False
    compress: bool = True


@dataclass(frozen=True)
class EptSubsetResult:
    """Result returned after an EPT subset has been written."""

    output_path: Path
    point_count: int | None
    written: bool
    message: str


def build_ept_subset_request(
    *,
    input_path: Path | str,
    crs: str,
    output_path: Path | str,
    bounds_text: str = "",
    bounds: BoundsTuple | None = None,
    thin_radius: float | None = None,
    hag: bool = False,
    hag_dtm: bool = False,
    dtm_path: Path | str | None = None,
    crop_poly: bool = False,
    poly: str | Path | None = None,
    reproject: bool = False,
    compress: bool = True,
) -> EptSubsetRequest:
    """Validate EPT subset inputs and return a typed adapter request."""
    source = Path(str(input_path))
    target = Path(str(output_path))
    parsed_bounds = bounds if bounds is not None else parse_ept_bounds(bounds_text)
    if source.name.lower() != "ept.json":
        raise ProcessingError("EPT subset extraction requires an ept.json source.")
    if not str(crs).strip():
        raise ProcessingError("EPT subset extraction requires an SRS/CRS value.")
    if target.suffix.lower() not in LAS_LAZ_SUFFIXES:
        raise ProcessingError("EPT subset output must end with .las or .laz.")
    if thin_radius is not None and thin_radius <= 0:
        raise ProcessingError("thin_radius must be greater than zero when provided.")
    if hag and hag_dtm:
        raise ProcessingError("Choose either Delaunay HAG or DTM-backed HAG, not both.")
    dtm = Path(str(dtm_path)) if dtm_path else None
    if hag_dtm and dtm is None:
        raise ProcessingError("DTM-backed HAG requires a DTM path.")
    polygon = _clean_poly(poly)
    if crop_poly and polygon is None:
        raise ProcessingError("Crop polygon requires a polygon WKT value or polygon file path.")
    return EptSubsetRequest(
        input_path=source,
        crs=str(crs).strip(),
        output_path=target,
        bounds=parsed_bounds,
        thin_radius=thin_radius,
        hag=bool(hag),
        hag_dtm=bool(hag_dtm),
        dtm_path=dtm,
        crop_poly=bool(crop_poly),
        poly=polygon,
        reproject=bool(reproject),
        compress=bool(compress),
    )


def parse_ept_bounds(text: str | None) -> BoundsTuple | None:
    """Parse xmin,xmax,ymin,ymax[,zmin,zmax] into read_lidar bounds."""
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    values = [part.strip() for part in cleaned.replace(";", ",").split(",") if part.strip()]
    if len(values) not in {4, 6}:
        raise ProcessingError("Bounds must be xmin,xmax,ymin,ymax or xmin,xmax,ymin,ymax,zmin,zmax.")
    try:
        numbers = [float(value) for value in values]
    except ValueError as exc:
        raise ProcessingError("Bounds must contain numeric values.") from exc
    pairs = tuple((numbers[index], numbers[index + 1]) for index in range(0, len(numbers), 2))
    for minimum, maximum in pairs:
        if maximum <= minimum:
            raise ProcessingError("Each bounds maximum must be greater than its minimum.")
    return pairs


def ept_read_lidar_kwargs(request: EptSubsetRequest) -> dict[str, Any]:
    """Return kwargs that map directly to pyforestscan.handlers.read_lidar."""
    bounds = None
    if request.bounds is not None:
        bounds = EptBounds.from_value(request.bounds, crs=request.crs, source="user_override").to_pyforestscan_value()
    return {
        "bounds": bounds,
        "thin_radius": request.thin_radius,
        "hag": request.hag,
        "hag_dtm": request.hag_dtm,
        "dtm": str(request.dtm_path) if request.dtm_path is not None else None,
        "crop_poly": request.crop_poly,
        "poly": str(request.poly) if request.poly is not None else None,
        "reproject": request.reproject,
    }


def compact_ept_subset_summary(result: EptSubsetResult) -> str:
    """Return a concise user-facing completion message."""
    count = "unknown point count" if result.point_count is None else f"{result.point_count:,} points"
    return f"EPT subset written: {result.output_path} ({count})."


def _clean_poly(poly: str | Path | None) -> str | Path | None:
    if poly is None:
        return None
    if isinstance(poly, Path):
        return poly
    text = str(poly).strip()
    return text or None
