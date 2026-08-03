"""CRS-aware polygon alignment helpers for source selection."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from .ept_spatial_reference import is_incomplete_crs_identifier
from .lidar_catalog_query import transform_wkt_coordinates
from .polygon_source import NormalizedPolygonSelection
from .spatial_selection import Bounds2D, polygon_selection_from_wkt

CoordinateTransformer = Callable[[float, float], tuple[float, float]]
TransformerFactory = Callable[[str, str], CoordinateTransformer]


@dataclass(frozen=True)
class SpatialAlignmentResult:
    status: str
    original_crs: str
    target_crs: str
    transformed_wkt: str
    transformed_bounds: Bounds2D | None
    transformation_required: bool
    transformation_source: str = ""
    user_message: str = ""
    technical_details: str = ""
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return self.status == "ready" and self.transformed_bounds is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "original_crs": self.original_crs,
            "target_crs": self.target_crs,
            "transformed_bounds": None if self.transformed_bounds is None else self.transformed_bounds.__dict__,
            "transformation_required": self.transformation_required,
            "transformation_source": self.transformation_source,
            "user_message": self.user_message,
            "technical_details": self.technical_details,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


def align_polygon_to_crs(
    polygon: NormalizedPolygonSelection,
    target_crs: str | None,
    *,
    transformer_factory: TransformerFactory | None = None,
) -> SpatialAlignmentResult:
    """Transform exact polygon WKT to a target CRS when a safe transformer is available."""
    source_crs = (polygon.processing_crs or polygon.source_crs or "").strip()
    target = (target_crs or "").strip()
    if is_incomplete_crs_identifier(source_crs):
        return _failed("crs_unresolved", source_crs, target, polygon.geometry_wkt, "The polygon coordinate system could not be determined.", "Polygon CRS is missing or incomplete.", ("POLYGON_CRS_INVALID",))
    if is_incomplete_crs_identifier(target):
        return _failed("crs_malformed", source_crs, target, polygon.geometry_wkt, "The EPT coordinate-system metadata is incomplete.", f"Repository CRS is missing or incomplete: {target or 'empty'}", ("REPOSITORY_CRS_INVALID",))
    if crs_equivalent(source_crs, target):
        selection = polygon_selection_from_wkt(polygon.geometry_wkt, target, source_label=polygon.source_description)
        return SpatialAlignmentResult(
            "ready",
            source_crs,
            target,
            polygon.geometry_wkt,
            selection.bounds,
            False,
            "same_crs",
            "The polygon and LiDAR data use compatible coordinate systems.",
            "Semantic CRS equivalence was accepted; no transformation was required.",
        )
    factory = transformer_factory or default_transformer_factory
    try:
        transformer = factory(source_crs, target)
    except Exception as exc:
        return _failed("transformation_unavailable", source_crs, target, polygon.geometry_wkt, "The polygon could not be transformed into the EPT coordinate system.", f"Transformer unavailable for {source_crs} to {target}: {exc}", ("CRS_TRANSFORM_FAILED",))
    try:
        transformed = transform_wkt_coordinates(polygon.geometry_wkt, transformer)
        selection = polygon_selection_from_wkt(transformed, target, source_label=polygon.source_description)
    except Exception as exc:
        return _failed("transformation_failed", source_crs, target, polygon.geometry_wkt, "The polygon could not be transformed into the EPT coordinate system.", f"Transformation failed for {source_crs} to {target}: {exc}", ("CRS_TRANSFORM_FAILED",))
    values = (selection.bounds.xmin, selection.bounds.ymin, selection.bounds.xmax, selection.bounds.ymax)
    if not all(math.isfinite(value) for value in values):
        return _failed("transformation_failed", source_crs, target, polygon.geometry_wkt, "The polygon could not be transformed into the EPT coordinate system.", "Transformation produced non-finite coordinates.", ("CRS_TRANSFORM_FAILED",))
    return SpatialAlignmentResult(
        "ready",
        source_crs,
        target,
        transformed,
        selection.bounds,
        True,
        getattr(transformer, "__pyforestscan_source__", "automatic"),
        "The polygon will be transformed automatically to match the LiDAR data.",
        f"Transformed exact polygon geometry from {source_crs} to {target}.",
    )


def crs_equivalent(left: str | None, right: str | None) -> bool:
    left_text = (left or "").strip()
    right_text = (right or "").strip()
    if not left_text or not right_text:
        return False
    if left_text.upper() == right_text.upper():
        return True
    try:
        from pyproj import CRS  # type: ignore

        return CRS.from_user_input(left_text).equals(CRS.from_user_input(right_text), ignore_axis_order=True)
    except Exception:
        return False


def default_transformer_factory(source_crs: str, target_crs: str) -> CoordinateTransformer:
    try:
        from pyproj import Transformer  # type: ignore

        transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)

        def _transform(x: float, y: float) -> tuple[float, float]:
            return transformer.transform(x, y)

        setattr(_transform, "__pyforestscan_source__", "pyproj")
        return _transform
    except Exception:
        pass
    try:
        from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsPointXY, QgsProject  # type: ignore

        source = QgsCoordinateReferenceSystem(source_crs)
        target = QgsCoordinateReferenceSystem(target_crs)
        if not source.isValid() or not target.isValid():
            raise ValueError("QGIS could not construct one or both CRS values.")
        transform = QgsCoordinateTransform(source, target, QgsProject.instance())

        def _transform(x: float, y: float) -> tuple[float, float]:
            point = transform.transform(QgsPointXY(x, y))
            return float(point.x()), float(point.y())

        setattr(_transform, "__pyforestscan_source__", "qgis")
        return _transform
    except Exception as exc:
        raise ValueError("No CRS transformer is available in this runtime.") from exc


def _failed(status: str, source_crs: str, target_crs: str, wkt: str, user: str, technical: str, errors: tuple[str, ...]) -> SpatialAlignmentResult:
    return SpatialAlignmentResult(status, source_crs, target_crs, wkt, None, False, "", user, technical, errors=errors)


__all__ = ["SpatialAlignmentResult", "align_polygon_to_crs", "crs_equivalent", "default_transformer_factory"]
