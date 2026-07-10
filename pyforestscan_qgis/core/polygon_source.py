"""Typed polygon source models for guided folder processing.

This module is intentionally QGIS-free. UI adapters can populate these models
from QGIS layers, vector files, or WKT before the folder preflight consumes the
normalized WKT/CRS/bounds representation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from .spatial_selection import Bounds2D, PolygonSelection, polygon_selection_from_wkt

PolygonSourceMode = Literal["qgis_selected_features", "qgis_full_layer", "vector_file", "wkt"]

POLYGON_SOURCE_MODES: tuple[str, ...] = (
    "qgis_selected_features",
    "qgis_full_layer",
    "vector_file",
    "wkt",
)

SUPPORTED_VECTOR_EXTENSIONS: dict[str, str] = {
    ".gpkg": "GeoPackage",
    ".shp": "ESRI Shapefile",
    ".geojson": "GeoJSON",
    ".json": "GeoJSON / OGR vector JSON",
    ".fgb": "FlatGeobuf",
    ".kml": "KML",
}

POLYGON_VECTOR_FILE_FILTER = (
    "Vector files (*.gpkg *.shp *.geojson *.json *.fgb *.kml);;"
    "GeoPackage (*.gpkg);;"
    "ESRI Shapefile (*.shp);;"
    "GeoJSON (*.geojson *.json);;"
    "FlatGeobuf (*.fgb);;"
    "KML (*.kml);;"
    "All files (*.*)"
)


@dataclass(frozen=True)
class PolygonSource:
    """User-facing polygon source selection before geometry extraction."""

    source_mode: PolygonSourceMode
    layer_id: str | None = None
    layer_name: str | None = None
    selected_feature_ids: tuple[int, ...] = ()
    vector_file_path: Path | None = None
    vector_layer_name: str | None = None
    feature_index: int | None = None
    feature_ids: tuple[int, ...] = ()
    dissolve_selected: bool = True
    polygon_wkt: str | None = None
    source_crs: str | None = None
    processing_crs: str | None = None
    geometry_type: str | None = None
    feature_count: int = 0


@dataclass(frozen=True)
class NormalizedPolygonSelection:
    """Single polygon representation consumed by folder preflight."""

    geometry_wkt: str
    source_crs: str
    processing_crs: str
    geometry_type: str
    source_description: str
    feature_count: int
    bounds: Bounds2D
    area: float
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_polygon_selection(self) -> PolygonSelection:
        """Return the legacy planner selection object."""
        return PolygonSelection(
            wkt=self.geometry_wkt,
            crs=self.processing_crs or self.source_crs,
            bounds=self.bounds,
            source_label=self.source_description,
        )


def is_supported_polygon_vector_extension(path: str | Path) -> bool:
    """Return whether the file suffix is a guided polygon-vector candidate."""
    return Path(str(path)).suffix.lower() in SUPPORTED_VECTOR_EXTENSIONS


def vector_format_label(path: str | Path) -> str:
    """Return a concise format label for a vector file path."""
    return SUPPORTED_VECTOR_EXTENSIONS.get(Path(str(path)).suffix.lower(), "QGIS-supported vector file")


def validate_polygon_source(source: PolygonSource) -> None:
    """Validate source metadata before QGIS/UI extraction work begins."""
    if source.source_mode not in POLYGON_SOURCE_MODES:
        raise ValueError(f"Unsupported polygon source mode: {source.source_mode}")
    if source.source_mode == "qgis_selected_features":
        if not source.layer_id:
            raise ValueError("Choose a polygon layer before using selected features.")
        if not source.selected_feature_ids:
            raise ValueError("Select one or more polygon features, or choose Use Entire Layer.")
    elif source.source_mode == "qgis_full_layer":
        if not source.layer_id:
            raise ValueError("Choose a polygon layer before using the entire layer.")
    elif source.source_mode == "vector_file":
        if source.vector_file_path is None:
            raise ValueError("Choose a polygon vector file.")
        if not is_supported_polygon_vector_extension(source.vector_file_path):
            raise ValueError("Choose a supported polygon vector file: GeoPackage, Shapefile, GeoJSON, FlatGeobuf, or KML.")
    elif source.source_mode == "wkt":
        polygon_selection_from_wkt(source.polygon_wkt or "", source.source_crs or source.processing_crs or "")


def normalize_wkt_source(source: PolygonSource) -> NormalizedPolygonSelection:
    """Normalize an Advanced WKT source without requiring QGIS."""
    validate_polygon_source(source)
    selection = polygon_selection_from_wkt(
        source.polygon_wkt or "",
        source.processing_crs or source.source_crs or "",
        source_label="Advanced WKT polygon",
    )
    geometry_type = "MultiPolygon" if selection.wkt.upper().startswith("MULTIPOLYGON") else "Polygon"
    return NormalizedPolygonSelection(
        geometry_wkt=selection.wkt,
        source_crs=source.source_crs or selection.crs,
        processing_crs=source.processing_crs or selection.crs,
        geometry_type=geometry_type,
        source_description="Advanced WKT polygon",
        feature_count=1,
        bounds=selection.bounds,
        area=selection.bounds.area,
        warnings=("WKT is an Advanced fallback; guided polygon layer/file selection is preferred.",),
    )


def selected_feature_count_text(count: int) -> str:
    """Return compact selected-feature count text for the Dataset page."""
    if count == 1:
        return "1 selected feature"
    return f"{max(0, count)} selected features"


def polygon_source_summary(selection: NormalizedPolygonSelection) -> str:
    """Return a concise source summary for preflight output."""
    warnings = "" if not selection.warnings else "\n" + "\n".join(f"Warning: {item}" for item in selection.warnings)
    return (
        f"Polygon source: {selection.source_description}\n"
        f"Geometry: {selection.geometry_type}; features: {selection.feature_count}\n"
        f"CRS: {selection.processing_crs}; bounds: "
        f"{selection.bounds.xmin:g}, {selection.bounds.ymin:g}, {selection.bounds.xmax:g}, {selection.bounds.ymax:g}"
        f"{warnings}"
    )

def stale_layer_message(layer_name: str | None = None) -> str:
    """Return guidance when a selected QGIS layer is no longer present."""
    name = f" '{layer_name}'" if layer_name else ""
    return f"Polygon layer{name} is no longer available. Refresh Layers and choose another polygon source."
