"""QGIS footprint preview helpers for Mission Control.

Pure preview construction is kept independent from QGIS imports so it can be
unit tested without QGIS. Layer creation and canvas zoom import QGIS APIs inside
functions at the UI boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.dataset_report import DatasetExplorerReport


@dataclass(frozen=True)
class FootprintPreview:
    """Dataset footprint preview built from Dataset Explorer bounds."""

    dataset_stem: str
    crs: str | None
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    area: float
    center_x: float
    center_y: float
    warnings: tuple[str, ...] = ()

    @property
    def layer_name(self) -> str:
        """Return the QGIS layer name for this footprint."""
        return f"PyForestScan Footprint - {self.dataset_stem}"

    @property
    def extent_text(self) -> str:
        """Return a compact coordinate extent string."""
        return f"X {self.xmin:g} to {self.xmax:g}; Y {self.ymin:g} to {self.ymax:g}"

    @property
    def center_text(self) -> str:
        """Return a compact center point string."""
        return f"{self.center_x:g}, {self.center_y:g}"


@dataclass(frozen=True)
class FootprintActionResult:
    """Result message from a QGIS footprint action."""

    success: bool
    message: str


def preview_from_report(report: DatasetExplorerReport, dataset_path: str | Path) -> FootprintPreview | None:
    """Create a footprint preview from Dataset Explorer bounds."""
    if report.bounds is None:
        return None
    xmin = float(report.bounds.min_x)
    xmax = float(report.bounds.max_x)
    ymin = float(report.bounds.min_y)
    ymax = float(report.bounds.max_y)
    if xmax <= xmin or ymax <= ymin:
        return None
    warnings: list[str] = []
    if not report.crs:
        warnings.append("CRS is unknown; footprint will use source coordinates without map reprojection metadata.")
    return FootprintPreview(
        dataset_stem=_dataset_stem(Path(dataset_path)),
        crs=report.crs,
        xmin=xmin,
        ymin=ymin,
        xmax=xmax,
        ymax=ymax,
        area=(xmax - xmin) * (ymax - ymin),
        center_x=(xmin + xmax) / 2.0,
        center_y=(ymin + ymax) / 2.0,
        warnings=tuple(warnings),
    )


def add_footprint_layer(preview: FootprintPreview, iface: Any) -> FootprintActionResult:
    """Add a footprint polygon as an in-memory QGIS layer."""
    try:
        from qgis.PyQt.QtGui import QColor
        from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer
    except Exception as exc:  # noqa: BLE001 - QGIS imports are UI-bound optional dependencies.
        return FootprintActionResult(False, f"QGIS footprint APIs are unavailable: {exc}")

    source = "Polygon"
    if preview.crs:
        source = f"Polygon?crs={preview.crs}"
    layer = QgsVectorLayer(source, preview.layer_name, "memory")
    if not layer.isValid():
        return FootprintActionResult(False, "Could not create in-memory footprint layer.")

    points = _polygon_points(preview, QgsPointXY)
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPolygonXY([points]))
    provider = layer.dataProvider()
    provider.addFeatures([feature])
    layer.updateExtents()
    try:
        symbol = layer.renderer().symbol()
        symbol.setColor(QColor(30, 136, 229, 45))
        symbol.symbolLayer(0).setStrokeColor(QColor(13, 71, 161))
        symbol.symbolLayer(0).setStrokeWidth(0.8)
    except Exception:
        pass
    QgsProject.instance().addMapLayer(layer)
    return FootprintActionResult(True, f"Added footprint layer: {preview.layer_name}")


def zoom_to_footprint(preview: FootprintPreview, iface: Any) -> FootprintActionResult:
    """Zoom the main QGIS map canvas to the footprint extent."""
    try:
        from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject, QgsRectangle
    except Exception as exc:  # noqa: BLE001 - QGIS imports are UI-bound optional dependencies.
        return FootprintActionResult(False, f"QGIS map canvas APIs are unavailable: {exc}")

    canvas = iface.mapCanvas() if iface is not None else None
    if canvas is None:
        return FootprintActionResult(False, "QGIS map canvas is unavailable.")
    rect = QgsRectangle(preview.xmin, preview.ymin, preview.xmax, preview.ymax)
    if preview.crs:
        try:
            source_crs = QgsCoordinateReferenceSystem(preview.crs)
            target_crs = QgsProject.instance().crs()
            if source_crs.isValid() and target_crs.isValid() and source_crs != target_crs:
                transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
                rect = transform.transformBoundingBox(rect)
        except Exception as exc:  # noqa: BLE001 - report transform failures clearly.
            return FootprintActionResult(False, f"Could not transform footprint to project CRS: {exc}")
    else:
        return FootprintActionResult(False, "Cannot zoom reliably because dataset CRS is unknown.")
    canvas.setExtent(rect)
    canvas.refresh()
    return FootprintActionResult(True, "Zoomed QGIS map canvas to dataset footprint.")


def _polygon_points(preview: FootprintPreview, point_cls: Any) -> list[Any]:
    return [
        point_cls(preview.xmin, preview.ymin),
        point_cls(preview.xmax, preview.ymin),
        point_cls(preview.xmax, preview.ymax),
        point_cls(preview.xmin, preview.ymax),
        point_cls(preview.xmin, preview.ymin),
    ]


def _dataset_stem(path: Path) -> str:
    if path.name.lower() == "ept.json" and path.parent.name:
        return path.parent.name
    return path.stem or "dataset"
