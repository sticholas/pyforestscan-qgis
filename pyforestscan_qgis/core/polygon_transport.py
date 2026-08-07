"""Polygon transport contract between QGIS/Mission Control and PBM."""

from __future__ import annotations

import json
import math
import re
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PolygonExecutionInput:
    """Serializable polygon geometry plus CRS metadata for backend execution."""

    source_kind: str
    geometry_wkt: str
    geometry_geojson: dict[str, Any] | None = None
    source_crs_authid: str = ""
    source_crs_wkt: str = ""
    processing_crs_authid: str = ""
    processing_crs_wkt: str = ""
    transformed_geometry_wkt: str | None = None
    envelope: tuple[float, float, float, float] | None = None
    area: float | None = None
    feature_count: int = 1
    temporary_vector_format: str = "GPKG"
    temporary_vector_path: str | None = None
    layer_name: str = "clipping_polygon"
    cleanup_policy: str = "retain_on_failure"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: "PolygonExecutionInput | dict[str, Any]") -> "PolygonExecutionInput":
        if isinstance(value, cls):
            return value
        data = dict(value)
        if data.get("envelope") is not None:
            data["envelope"] = tuple(float(item) for item in data["envelope"])
        return cls(**{key: data[key] for key in cls.__dataclass_fields__ if key in data})


@dataclass(frozen=True)
class PreparedPolygonInput:
    """Materialized backend polygon dataset ready for PyForestScan."""

    execution_input: PolygonExecutionInput
    temporary_vector_path: Path
    temporary_vector_format: str
    layer_name: str
    cleanup_policy: str


def polygon_execution_input_from_selection(selection: Any, *, transformed_wkt: str | None = None, source_kind: str = "selected_features") -> PolygonExecutionInput:
    """Build the backend polygon transport model from a normalized selection."""
    geometry_wkt = str(getattr(selection, "geometry_wkt", ""))
    envelope = getattr(getattr(selection, "bounds", None), "__dict__", None)
    envelope_tuple = None
    if envelope:
        envelope_tuple = (
            float(envelope["xmin"]),
            float(envelope["ymin"]),
            float(envelope["xmax"]),
            float(envelope["ymax"]),
        )
    return PolygonExecutionInput(
        source_kind=source_kind,
        geometry_wkt=geometry_wkt,
        geometry_geojson=wkt_to_geojson_geometry(transformed_wkt or geometry_wkt),
        source_crs_authid=str(getattr(selection, "source_crs", "")),
        processing_crs_authid=str(getattr(selection, "processing_crs", "")),
        transformed_geometry_wkt=transformed_wkt,
        envelope=envelope_tuple,
        area=float(getattr(selection, "area", 0.0) or 0.0),
        feature_count=int(getattr(selection, "feature_count", 1) or 1),
    )


def polygon_execution_input_from_mapping(value: PolygonExecutionInput | dict[str, Any] | None) -> PolygonExecutionInput | None:
    if value is None:
        return None
    return PolygonExecutionInput.from_mapping(value)


def materialize_polygon_input(value: PolygonExecutionInput | dict[str, Any], job_workspace: Path | str) -> PreparedPolygonInput:
    """Write a durable vector dataset and return the path that PyForestScan expects."""
    polygon_input = PolygonExecutionInput.from_mapping(value)
    workspace = Path(job_workspace)
    inputs_dir = workspace / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    preferred = polygon_input.temporary_vector_format.upper()
    if preferred == "GPKG":
        try:
            return _write_gpkg(polygon_input, inputs_dir)
        except Exception:
            pass
    return _write_geojson(polygon_input, inputs_dir)


def looks_like_wkt(value: object) -> bool:
    text = str(value or "").strip().upper()
    return text.startswith(("POLYGON", "MULTIPOLYGON", "GEOMETRYCOLLECTION"))


def wkt_to_geojson_geometry(wkt: str) -> dict[str, Any]:
    """Convert simple Polygon/MultiPolygon WKT into GeoJSON geometry."""
    text = wkt.strip()
    upper = text.upper()
    if upper.startswith("POLYGON"):
        return {"type": "Polygon", "coordinates": _parse_polygon_coordinates(_body(text))}
    if upper.startswith("MULTIPOLYGON"):
        return {"type": "MultiPolygon", "coordinates": [_parse_polygon_coordinates(part) for part in _split_multipolygon(_body(text))]}
    raise ValueError("Polygon transport supports Polygon and MultiPolygon WKT.")


def _write_geojson(polygon_input: PolygonExecutionInput, inputs_dir: Path) -> PreparedPolygonInput:
    path = inputs_dir / "clipping_polygon.geojson"
    geometry = polygon_input.geometry_geojson or wkt_to_geojson_geometry(polygon_input.transformed_geometry_wkt or polygon_input.geometry_wkt)
    payload = {
        "type": "FeatureCollection",
        "name": polygon_input.layer_name,
        "crs": {"type": "name", "properties": {"name": polygon_input.processing_crs_authid or polygon_input.source_crs_authid}},
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "source_kind": polygon_input.source_kind,
                    "area": polygon_input.area,
                    "feature_count": polygon_input.feature_count,
                },
                "geometry": geometry,
            }
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return PreparedPolygonInput(polygon_input, path, "GeoJSON", polygon_input.layer_name, polygon_input.cleanup_policy)


def _write_gpkg(polygon_input: PolygonExecutionInput, inputs_dir: Path) -> PreparedPolygonInput:
    from osgeo import ogr, osr  # type: ignore

    path = inputs_dir / "clipping_polygon.gpkg"
    if path.exists():
        path.unlink()
    driver = ogr.GetDriverByName("GPKG")
    if driver is None:
        raise RuntimeError("GDAL GPKG driver is unavailable.")
    ds = driver.CreateDataSource(str(path))
    if ds is None:
        raise RuntimeError("Could not create GeoPackage polygon input.")
    srs = osr.SpatialReference()
    crs = polygon_input.processing_crs_authid or polygon_input.source_crs_authid
    if crs.upper().startswith("EPSG:"):
        srs.ImportFromEPSG(int(crs.split(":", 1)[1]))
    elif polygon_input.processing_crs_wkt or polygon_input.source_crs_wkt:
        srs.ImportFromWkt(polygon_input.processing_crs_wkt or polygon_input.source_crs_wkt)
    layer = ds.CreateLayer(polygon_input.layer_name, srs, ogr.wkbUnknown)
    feature_def = layer.GetLayerDefn()
    feature = ogr.Feature(feature_def)
    geometry = ogr.CreateGeometryFromWkt(polygon_input.transformed_geometry_wkt or polygon_input.geometry_wkt)
    if geometry is None:
        raise ValueError("Invalid polygon WKT.")
    feature.SetGeometry(geometry)
    if layer.CreateFeature(feature) != 0:
        raise RuntimeError("Could not write clipping polygon feature.")
    feature = None
    ds = None
    return PreparedPolygonInput(polygon_input, path, "GPKG", polygon_input.layer_name, polygon_input.cleanup_policy)


def _body(wkt: str) -> str:
    start = wkt.find("(")
    end = wkt.rfind(")")
    if start < 0 or end <= start:
        raise ValueError("Invalid polygon WKT.")
    return wkt[start + 1 : end].strip()


def _split_multipolygon(body: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = None
    for index, char in enumerate(body):
        if char == "(":
            if depth == 0:
                start = index + 1
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and start is not None:
                parts.append(body[start:index].strip())
                start = None
    if depth != 0 or not parts:
        raise ValueError("Invalid MultiPolygon WKT.")
    return parts


def _parse_polygon_coordinates(body: str) -> list[list[list[float]]]:
    rings: list[list[list[float]]] = []
    ring_parts = _split_rings(body)
    for ring in ring_parts:
        coords: list[list[float]] = []
        for pair in ring.split(","):
            values = [float(item) for item in pair.strip().split()[:2]]
            if len(values) != 2 or not all(math.isfinite(item) for item in values):
                raise ValueError("Invalid polygon coordinate.")
            coords.append(values)
        if len(coords) < 4:
            raise ValueError("Polygon rings require at least four coordinates.")
        rings.append(coords)
    return rings


def _split_rings(body: str) -> list[str]:
    text = body.strip()
    rings: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(text):
        if char == "(":
            if depth == 0:
                start = index + 1
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                rings.append(text[start:index])
    if rings:
        return rings
    return [text]


def unique_polygon_job_id(prefix: str = "polygon") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"
