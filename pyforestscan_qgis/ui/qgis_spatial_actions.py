"""Live QGIS spatial actions for repository coverage and polygon preview."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..core.repository_coverage import RepositoryCoverageModel
from ..core.spatial_selection import Bounds2D


@dataclass(frozen=True)
class QgisSpatialActionResult:
    success: bool
    message: str
    layer_ids: tuple[str, ...] = ()
    feature_count: int = 0
    extent: Bounds2D | None = None


def add_repository_coverage_to_qgis(model: RepositoryCoverageModel, iface: Any) -> QgisSpatialActionResult:
    if iface is None:
        return QgisSpatialActionResult(False, "No live QGIS project is available.")
    if not model.crs or model.crs == "unknown":
        return QgisSpatialActionResult(False, "Repository coverage cannot be mapped until its coordinate system is known.")
    if model.union_extent is None:
        return QgisSpatialActionResult(False, "Repository coverage extent is unavailable.")
    try:
        from qgis.PyQt.QtGui import QColor
        from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer
        from qgis.PyQt.QtCore import QVariant
    except Exception as exc:  # noqa: BLE001
        return QgisSpatialActionResult(False, f"QGIS map APIs are unavailable: {exc}")
    layer = QgsVectorLayer(f"Polygon?crs={model.crs}", "PyForestScan Repository Coverage", "memory")
    if not layer.isValid():
        return QgisSpatialActionResult(False, "Could not create repository coverage layer.")
    provider = layer.dataProvider()
    provider.addAttributes([QgsField("repository", QVariant.String), QgsField("source_count", QVariant.Int), QgsField("crs_status", QVariant.String), QgsField("catalog_status", QVariant.String)])
    layer.updateFields()
    feature = QgsFeature(layer.fields())
    feature.setGeometry(_rect_geometry(model.union_extent, QgsPointXY, QgsGeometry))
    feature.setAttributes(["active", len(model.features), "effective", model.features[0].metadata_status if model.features else "unknown"])
    provider.addFeatures([feature])
    layer.updateExtents()
    try:
        symbol = layer.renderer().symbol()
        symbol.setColor(QColor(46, 125, 50, 35))
        symbol.symbolLayer(0).setStrokeColor(QColor(27, 94, 32))
        symbol.symbolLayer(0).setStrokeWidth(0.8)
    except Exception:
        pass
    project = QgsProject.instance()
    project.addMapLayer(layer, False)
    root = project.layerTreeRoot()
    group = root.findGroup(model.group_name) or root.addGroup(model.group_name)
    group.addLayer(layer)
    canvas = iface.mapCanvas() if iface is not None else None
    if canvas is not None:
        canvas.refresh()
    return QgisSpatialActionResult(True, "Repository coverage was added to the map.", (layer.id(),), 1, model.union_extent)



def preview_spatial_selection_in_qgis(report: Any, iface: Any) -> QgisSpatialActionResult:
    if iface is None:
        return QgisSpatialActionResult(False, "No live QGIS project is available.")
    selection = getattr(report, "source_selection", None)
    if selection is None:
        return QgisSpatialActionResult(False, "No current polygon source-selection report is available.")
    try:
        from qgis.PyQt.QtGui import QColor
        from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer
        from qgis.PyQt.QtCore import QVariant
    except Exception as exc:  # noqa: BLE001
        return QgisSpatialActionResult(False, f"QGIS preview APIs are unavailable: {exc}")
    project = QgsProject.instance()
    _remove_group_layers(project, "PyForestScan - Spatial Selection Preview")
    group = project.layerTreeRoot().findGroup("PyForestScan - Spatial Selection Preview") or project.layerTreeRoot().addGroup("PyForestScan - Spatial Selection Preview")
    layer_ids: list[str] = []
    feature_count = 0
    crs = selection.transformed_envelope.crs
    polygon_layer = QgsVectorLayer(f"Polygon?crs={crs}", "Selected Polygon", "memory")
    if polygon_layer.isValid():
        provider = polygon_layer.dataProvider()
        provider.addAttributes([QgsField("kind", QVariant.String)])
        polygon_layer.updateFields()
        feature = QgsFeature(polygon_layer.fields())
        feature.setGeometry(QgsGeometry.fromWkt(selection.transformed_polygon))
        feature.setAttributes(["polygon"])
        provider.addFeatures([feature])
        polygon_layer.updateExtents()
        _style_layer(polygon_layer, QColor(25, 118, 210, 30), QColor(25, 118, 210))
        project.addMapLayer(polygon_layer, False)
        group.addLayer(polygon_layer)
        layer_ids.append(polygon_layer.id())
        feature_count += 1
    envelope_layer = _extent_layer("Polygon Envelope", selection.transformed_envelope.to_bounds(), crs, "polygon_envelope", QColor(251, 192, 45, 25), QColor(245, 124, 0), QgsFeature, QgsField, QgsPointXY, QgsGeometry, QgsVectorLayer, QVariant)
    if envelope_layer is not None:
        project.addMapLayer(envelope_layer, False)
        group.addLayer(envelope_layer)
        layer_ids.append(envelope_layer.id())
        feature_count += 1
    if selection.source_extent is not None:
        repo_layer = _extent_layer("Repository Coverage", selection.source_extent.to_bounds(), selection.source_extent.crs, "repository", QColor(46, 125, 50, 25), QColor(46, 125, 50), QgsFeature, QgsField, QgsPointXY, QgsGeometry, QgsVectorLayer, QVariant)
        if repo_layer is not None:
            project.addMapLayer(repo_layer, False)
            group.addLayer(repo_layer)
            layer_ids.append(repo_layer.id())
            feature_count += 1
    candidate_layer = QgsVectorLayer(f"Polygon?crs={crs}", "Candidate LiDAR Sources", "memory")
    if candidate_layer.isValid():
        provider = candidate_layer.dataProvider()
        provider.addAttributes([QgsField("filename", QVariant.String), QgsField("source_type", QVariant.String)])
        candidate_layer.updateFields()
        features = []
        for source in getattr(selection, "selected_sources", ())[:1000]:
            bounds = getattr(source, "bounds", None)
            if bounds is None:
                continue
            feature = QgsFeature(candidate_layer.fields())
            feature.setGeometry(_rect_geometry(bounds, QgsPointXY, QgsGeometry))
            feature.setAttributes([str(getattr(source, "path", "")), str(getattr(source, "source_type", ""))])
            features.append(feature)
        if features:
            provider.addFeatures(features)
            candidate_layer.updateExtents()
            _style_layer(candidate_layer, QColor(123, 31, 162, 25), QColor(123, 31, 162))
            project.addMapLayer(candidate_layer, False)
            group.addLayer(candidate_layer)
            layer_ids.append(candidate_layer.id())
            feature_count += len(features)
    canvas = iface.mapCanvas()
    if canvas is not None:
        canvas.refresh()
    return QgisSpatialActionResult(bool(layer_ids), "Spatial selection preview layers were added to the map." if layer_ids else "No preview layers could be added.", tuple(layer_ids), feature_count, combine_bounds(selection.transformed_envelope.to_bounds(), None if selection.source_extent is None else selection.source_extent.to_bounds()))


def remove_spatial_preview_layers(iface: Any) -> QgisSpatialActionResult:
    if iface is None:
        return QgisSpatialActionResult(False, "No live QGIS project is available.")
    try:
        from qgis.core import QgsProject
    except Exception as exc:  # noqa: BLE001
        return QgisSpatialActionResult(False, f"QGIS project APIs are unavailable: {exc}")
    project = QgsProject.instance()
    removed = _remove_group_layers(project, "PyForestScan - Spatial Selection Preview")
    canvas = iface.mapCanvas()
    if canvas is not None:
        canvas.refresh()
    return QgisSpatialActionResult(True, f"Removed {removed} spatial preview layer(s).", feature_count=removed)


def _extent_layer(name: str, bounds: Bounds2D, crs: str, kind: str, fill: Any, stroke: Any, feature_cls: Any, field_cls: Any, point_cls: Any, geometry_cls: Any, layer_cls: Any, variant_cls: Any) -> Any:
    layer = layer_cls(f"Polygon?crs={crs}", name, "memory")
    if not layer.isValid():
        return None
    provider = layer.dataProvider()
    provider.addAttributes([field_cls("kind", variant_cls.String)])
    layer.updateFields()
    feature = feature_cls(layer.fields())
    feature.setGeometry(_rect_geometry(bounds, point_cls, geometry_cls))
    feature.setAttributes([kind])
    provider.addFeatures([feature])
    layer.updateExtents()
    _style_layer(layer, fill, stroke)
    return layer


def _style_layer(layer: Any, fill: Any, stroke: Any) -> None:
    try:
        symbol = layer.renderer().symbol()
        symbol.setColor(fill)
        symbol.symbolLayer(0).setStrokeColor(stroke)
        symbol.symbolLayer(0).setStrokeWidth(0.8)
    except Exception:
        pass


def _remove_group_layers(project: Any, group_name: str) -> int:
    group = project.layerTreeRoot().findGroup(group_name)
    if group is None:
        return 0
    ids: list[str] = []
    for child in list(group.children()):
        layer = child.layer() if hasattr(child, "layer") else None
        if layer is not None:
            ids.append(layer.id())
    if ids:
        project.removeMapLayers(ids)
    return len(ids)

def zoom_canvas_to_bounds(bounds: Bounds2D | None, crs: str | None, iface: Any, *, label: str = "extent") -> QgisSpatialActionResult:
    if iface is None:
        return QgisSpatialActionResult(False, "QGIS map canvas is unavailable.")
    if bounds is None or not _finite_bounds(bounds):
        return QgisSpatialActionResult(False, f"Cannot zoom to {label}: extent is unavailable or invalid.")
    if not crs or crs == "unknown":
        return QgisSpatialActionResult(False, f"Cannot zoom to {label}: CRS is unknown.")
    try:
        from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject, QgsRectangle
    except Exception as exc:  # noqa: BLE001
        return QgisSpatialActionResult(False, f"QGIS map canvas APIs are unavailable: {exc}")
    canvas = iface.mapCanvas()
    if canvas is None:
        return QgisSpatialActionResult(False, "QGIS map canvas is unavailable.")
    rect = QgsRectangle(bounds.xmin, bounds.ymin, bounds.xmax, bounds.ymax)
    source_crs = QgsCoordinateReferenceSystem(crs)
    target_crs = QgsProject.instance().crs()
    if source_crs.isValid() and target_crs.isValid() and source_crs != target_crs:
        rect = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance()).transformBoundingBox(rect)
    rect.scale(1.08)
    canvas.setExtent(rect)
    canvas.refresh()
    return QgisSpatialActionResult(True, f"Zoomed to {label}.", extent=bounds)


def combine_bounds(left: Bounds2D | None, right: Bounds2D | None) -> Bounds2D | None:
    if left is None:
        return right
    if right is None:
        return left
    return Bounds2D(min(left.xmin, right.xmin), min(left.ymin, right.ymin), max(left.xmax, right.xmax), max(left.ymax, right.ymax))


def _rect_geometry(bounds: Bounds2D, point_cls: Any, geometry_cls: Any) -> Any:
    points = [point_cls(bounds.xmin, bounds.ymin), point_cls(bounds.xmax, bounds.ymin), point_cls(bounds.xmax, bounds.ymax), point_cls(bounds.xmin, bounds.ymax), point_cls(bounds.xmin, bounds.ymin)]
    return geometry_cls.fromPolygonXY([points])


def _finite_bounds(bounds: Bounds2D) -> bool:
    return all(math.isfinite(value) for value in (bounds.xmin, bounds.ymin, bounds.xmax, bounds.ymax)) and bounds.xmin < bounds.xmax and bounds.ymin < bounds.ymax
