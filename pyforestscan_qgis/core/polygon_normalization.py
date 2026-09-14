"""QGIS-free polygon normalization helpers."""

from __future__ import annotations

from .polygon_source import NormalizedPolygonSelection, PolygonSource, normalize_wkt_source, polygon_source_summary
from .spatial_selection import Bounds2D, polygon_selection_from_wkt


def normalized_selection_from_wkt(wkt: str, crs: str, *, source_description: str = "Advanced WKT polygon") -> NormalizedPolygonSelection:
    """Build a normalized selection from WKT text."""
    selection = polygon_selection_from_wkt(wkt, crs, source_label=source_description)
    geometry_type = "MultiPolygon" if selection.wkt.upper().startswith("MULTIPOLYGON") else "Polygon"
    return NormalizedPolygonSelection(
        geometry_wkt=selection.wkt,
        source_crs=selection.crs,
        processing_crs=selection.crs,
        geometry_type=geometry_type,
        source_description=source_description,
        feature_count=1,
        bounds=selection.bounds,
        area=selection.bounds.area,
        warnings=(),
    )


def normalize_polygon_source(source: PolygonSource) -> NormalizedPolygonSelection:
    """Normalize source modes that do not require live QGIS geometry extraction."""
    if source.source_mode != "wkt":
        raise ValueError("QGIS layer and vector-file sources must be normalized by the QGIS UI adapter.")
    return normalize_wkt_source(source)


__all__ = [
    "Bounds2D",
    "NormalizedPolygonSelection",
    "PolygonSource",
    "normalize_polygon_source",
    "normalized_selection_from_wkt",
    "polygon_source_summary",
]
