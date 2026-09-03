"""QGIS-facing polygon source helpers for Mission Control."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..core.polygon_source import NormalizedPolygonSelection, POLYGON_VECTOR_FILE_FILTER, stale_layer_message
from ..core.spatial_selection import Bounds2D


@dataclass(frozen=True)
class PolygonLayerItem:
    """Compact metadata for a polygon layer shown in Mission Control."""

    layer_id: str
    name: str
    crs: str
    geometry_type: str
    feature_count: int
    selected_feature_count: int

    @property
    def label(self) -> str:
        selected = f", {self.selected_feature_count} selected" if self.selected_feature_count else ""
        return f"{self.name} ({self.geometry_type}, {self.feature_count} features{selected})"


@dataclass(frozen=True)
class VectorLayerOption:
    """One polygon layer available from a vector file or container."""

    name: str
    uri: str
    geometry_type: str = "Polygon"
    feature_count: int | None = None
    crs: str | None = None

    @property
    def label(self) -> str:
        count = "unknown features" if self.feature_count is None else f"{self.feature_count} features"
        return f"{self.name} ({self.geometry_type}, {count})"


def polygon_layer_items(iface) -> list[PolygonLayerItem]:
    """Return polygon/multipolygon vector layers currently loaded in QGIS."""
    try:
        from qgis.core import QgsProject
    except Exception:  # noqa: BLE001 - non-QGIS tests cannot enumerate layers.
        return []
    project = None
    try:
        project = iface.mapCanvas().project() if iface is not None and iface.mapCanvas() is not None else None
    except Exception:  # noqa: BLE001 - fall back to global project.
        project = None
    project = project or QgsProject.instance()
    items: list[PolygonLayerItem] = []
    for layer in project.mapLayers().values():
        if not _is_polygon_vector_layer(layer):
            continue
        items.append(
            PolygonLayerItem(
                layer_id=layer.id(),
                name=layer.name(),
                crs=_layer_crs_text(layer),
                geometry_type=_geometry_type_name(layer.wkbType()),
                feature_count=_safe_feature_count(layer),
                selected_feature_count=len(layer.selectedFeatureIds()),
            )
        )
    return items


def vector_file_layer_options(path: str | Path) -> list[VectorLayerOption]:
    """Inspect a vector file and return polygon layers QGIS/OGR can read."""
    file_path = str(path)
    options: list[VectorLayerOption] = []
    try:
        from qgis.core import QgsProviderRegistry, QgsVectorLayer
    except Exception:  # noqa: BLE001 - QGIS is required for file inspection.
        return options

    try:
        details = QgsProviderRegistry.instance().querySublayers(file_path)
    except Exception:  # noqa: BLE001 - older QGIS versions may not expose querySublayers.
        details = []
    for detail in details or []:
        try:
            uri = detail.uri()
            name = detail.name() or Path(file_path).stem
            geom_type = detail.geometryType()
        except Exception:  # noqa: BLE001 - provider details vary by QGIS version.
            continue
        if not _is_polygon_geometry_family(geom_type):
            continue
        layer = QgsVectorLayer(uri, name, "ogr")
        if layer.isValid() and _is_polygon_vector_layer(layer):
            options.append(
                VectorLayerOption(
                    name=layer.name(),
                    uri=uri,
                    geometry_type=_geometry_type_name(layer.wkbType()),
                    feature_count=_safe_feature_count(layer),
                    crs=_layer_crs_text(layer),
                )
            )

    if not options:
        layer = QgsVectorLayer(file_path, Path(file_path).stem, "ogr")
        if layer.isValid() and _is_polygon_vector_layer(layer):
            options.append(
                VectorLayerOption(
                    name=layer.name(),
                    uri=file_path,
                    geometry_type=_geometry_type_name(layer.wkbType()),
                    feature_count=_safe_feature_count(layer),
                    crs=_layer_crs_text(layer),
                )
            )
    return options


def normalize_qgis_layer_selection(iface, layer_id: str, *, use_selected: bool, dissolve: bool = True, processing_crs: str | None = None) -> NormalizedPolygonSelection:
    """Normalize a loaded QGIS polygon layer or selected features."""
    layer = _project_layer(iface, layer_id)
    if layer is None:
        raise ValueError(stale_layer_message())
    if not _is_polygon_vector_layer(layer):
        raise ValueError("Choose a polygon or multipolygon vector layer.")
    selected_ids = set(layer.selectedFeatureIds())
    if use_selected:
        if not selected_ids:
            raise ValueError("Select one or more polygon features, or choose Use Entire Layer.")
        features = [feature for feature in layer.getFeatures() if feature.id() in selected_ids]
        description = f"selected features from {layer.name()}"
    else:
        features = list(layer.getFeatures())
        description = f"entire layer {layer.name()}"
    return _normalize_layer_features(layer, features, description=description, dissolve=dissolve, processing_crs=processing_crs)


def normalize_vector_file_selection(path: str | Path, *, layer_uri: str | None = None, layer_name: str | None = None, processing_crs: str | None = None) -> NormalizedPolygonSelection:
    """Normalize all polygon features from a vector file layer."""
    try:
        from qgis.core import QgsVectorLayer
    except Exception as exc:  # noqa: BLE001
        raise ValueError("QGIS vector support is required to read polygon files.") from exc
    uri = layer_uri or str(path)
    name = layer_name or Path(str(path)).stem
    layer = QgsVectorLayer(uri, name, "ogr")
    if not layer.isValid():
        raise ValueError("QGIS could not read the selected vector file/layer.")
    if not _is_polygon_vector_layer(layer):
        raise ValueError("The selected vector file layer is not polygon geometry.")
    features = list(layer.getFeatures())
    description = f"vector file {Path(str(path)).name}"
    if layer_name:
        description += f" / {layer_name}"
    return _normalize_layer_features(layer, features, description=description, dissolve=True, processing_crs=processing_crs)


def _normalize_layer_features(layer, features: Iterable[object], *, description: str, dissolve: bool, processing_crs: str | None) -> NormalizedPolygonSelection:
    geometries = []
    warnings: list[str] = []
    for feature in features:
        geom = feature.geometry()
        if geom is None or geom.isEmpty():
            continue
        if not _is_polygon_geometry_family(geom.wkbType()):
            raise ValueError("Only Polygon and MultiPolygon features are supported.")
        geometries.append(geom)
    if not geometries:
        raise ValueError("The polygon source has no usable polygon geometry.")
    geom = _dissolve_geometries(geometries) if dissolve or len(geometries) > 1 else geometries[0]
    if geom is None or geom.isEmpty():
        raise ValueError("The polygon source dissolved to an empty geometry.")
    try:
        if not geom.isGeosValid():
            repaired = geom.makeValid()
            if repaired is not None and not repaired.isEmpty() and repaired.isGeosValid():
                geom = repaired
                warnings.append("Geometry was repaired before preflight.")
    except Exception:  # noqa: BLE001 - older QGIS may not expose GEOS validity methods consistently.
        warnings.append("Geometry validity could not be fully checked in this QGIS version.")
    try:
        if hasattr(geom, "isGeosValid") and not geom.isGeosValid():
            raise ValueError("The polygon geometry is invalid and could not be repaired.")
    except ValueError:
        raise
    except Exception:  # noqa: BLE001
        pass
    source_crs = _layer_crs_text(layer)
    processing = (processing_crs or "").strip() or source_crs
    if processing and source_crs and processing != source_crs:
        _transform_geometry(layer, geom, processing)
        warnings.append(f"Polygon was transformed from {source_crs} to {processing}.")
    rect = geom.boundingBox()
    bounds = Bounds2D(float(rect.xMinimum()), float(rect.yMinimum()), float(rect.xMaximum()), float(rect.yMaximum()))
    if bounds.area <= 0:
        raise ValueError("The polygon geometry has empty bounds.")
    return NormalizedPolygonSelection(
        geometry_wkt=geom.asWkt(),
        source_crs=source_crs,
        processing_crs=processing,
        geometry_type=_geometry_type_name(geom.wkbType()),
        source_description=description,
        feature_count=len(geometries),
        bounds=bounds,
        area=float(geom.area()),
        warnings=tuple(warnings),
        area_hectares=_measure_area_hectares(geom, processing or source_crs),
    )


def _measure_area_hectares(geometry, crs_text: str) -> float | None:
    """Measure area geodesically in hectares; never convert square degrees directly."""
    try:
        from qgis.core import QgsCoordinateReferenceSystem, QgsDistanceArea, QgsProject

        crs = QgsCoordinateReferenceSystem(crs_text)
        if not crs.isValid():
            return None
        measurement = QgsDistanceArea()
        measurement.setSourceCrs(crs, QgsProject.instance().transformContext())
        measurement.setEllipsoid("WGS84")
        square_metres = float(measurement.measureArea(geometry))
        return square_metres / 10000.0 if square_metres >= 0 else None
    except Exception:  # noqa: BLE001 - area display must not block processing.
        return None


def _dissolve_geometries(geometries: list[object]):
    try:
        from qgis.core import QgsGeometry

        return QgsGeometry.unaryUnion(geometries)
    except Exception:  # noqa: BLE001 - fallback for older QGIS.
        result = geometries[0]
        for geom in geometries[1:]:
            try:
                result = result.combine(geom)
            except Exception:  # noqa: BLE001
                result = result.combineGeometry(geom)
        return result


def _transform_geometry(layer, geom, target_crs_text: str) -> None:
    from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject

    source_crs = layer.crs()
    target = QgsCoordinateReferenceSystem(target_crs_text)
    if target.isValid() and source_crs.isValid() and source_crs != target:
        geom.transform(QgsCoordinateTransform(source_crs, target, QgsProject.instance()))


def _project_layer(iface, layer_id: str):
    try:
        from qgis.core import QgsProject
    except Exception:  # noqa: BLE001
        return None
    project = None
    try:
        project = iface.mapCanvas().project() if iface is not None and iface.mapCanvas() is not None else None
    except Exception:  # noqa: BLE001
        project = None
    return (project or QgsProject.instance()).mapLayer(layer_id)


def _is_polygon_vector_layer(layer) -> bool:
    try:
        from qgis.core import QgsMapLayer

        if layer.type() != QgsMapLayer.VectorLayer:
            return False
    except Exception:  # noqa: BLE001
        pass
    return _is_polygon_geometry_family(layer.wkbType())


def _is_polygon_geometry_family(wkb_type) -> bool:
    try:
        from qgis.core import QgsWkbTypes

        return QgsWkbTypes.geometryType(wkb_type) == QgsWkbTypes.PolygonGeometry
    except Exception:  # noqa: BLE001
        return False


def _geometry_type_name(wkb_type) -> str:
    try:
        from qgis.core import QgsWkbTypes

        return QgsWkbTypes.displayString(wkb_type) or "Polygon"
    except Exception:  # noqa: BLE001
        return "Polygon"


def _layer_crs_text(layer) -> str:
    crs = layer.crs()
    if crs is not None and crs.isValid():
        return crs.authid() or crs.toWkt()
    return ""


def _safe_feature_count(layer) -> int:
    try:
        count = layer.featureCount()
        return int(count) if count is not None and count >= 0 else 0
    except Exception:  # noqa: BLE001
        return 0


__all__ = [
    "POLYGON_VECTOR_FILE_FILTER",
    "PolygonLayerItem",
    "VectorLayerOption",
    "normalize_qgis_layer_selection",
    "normalize_vector_file_selection",
    "polygon_layer_items",
    "vector_file_layer_options",
]
