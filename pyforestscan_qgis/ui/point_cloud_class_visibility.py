"""Compact class visibility menu shared by docked and detached viewer surfaces."""
from qgis.PyQt.QtGui import QColor, QIcon, QPixmap
from qgis.PyQt.QtWidgets import QMenu, QToolButton

from ..compat.qt import qt_enum
from ..core.point_cloud.view_filters import (
    class_visibility_rows, isolated_class, visible_classes_after_changes)


def class_swatch_icon(color):
    pixmap = QPixmap(12, 12)
    pixmap.fill(QColor(color))
    return QIcon(pixmap)


class ClassVisibilityMenu(QToolButton):
    """View-local rendering controls; this widget never sends edit commands."""
    def __init__(self, send, parent=None):
        super().__init__(parent)
        self.send = send
        self.state = {}
        self.setText("Classes")
        self.setAccessibleName("Class visibility")
        self.setToolTip(
            "Show, hide or isolate LAS classes in this view. This changes rendering only; "
            "it never reclassifies points or changes authoritative selection membership.")
        self.setPopupMode(qt_enum(QToolButton, "InstantPopup", "ToolButtonPopupMode"))
        self.setMenu(QMenu(self))

    def sync(self, telemetry):
        editor = telemetry.get("editor") or {}
        rows = class_visibility_rows(telemetry.get("observed_classes", ()),
                                     telemetry.get("classes"),
                                     editor.get("effective_classes", {}))
        signature = tuple((row.code, row.visible, row.resident_count) for row in rows)
        if signature == self.state.get("signature"):
            return
        self.state = {"signature": signature, "classes": telemetry.get("classes")}
        menu = self.menu()
        menu.clear()
        show = menu.addAction("Show all classes")
        show.triggered.connect(self.show_all)
        isolate = menu.addMenu("Isolate class")
        menu.addSeparator()
        if not rows:
            waiting = menu.addAction("Waiting for class data")
            waiting.setEnabled(False)
        for row in rows:
            action = menu.addAction(class_swatch_icon(row.color), row.text)
            action.setCheckable(True)
            action.setChecked(row.visible)
            action.setToolTip("Approximate count covers resident points in this view after staged edits.")
            action.triggered.connect(lambda checked=False, code=row.code: self.change(code, checked))
            only = isolate.addAction(class_swatch_icon(row.color), row.label)
            only.triggered.connect(lambda _checked=False, code=row.code: self.isolate(code))

    def change(self, code, shown):
        visible = visible_classes_after_changes(self.state.get("classes"), {code: bool(shown)})
        self.state["classes"] = visible
        self.send({"action": "classes", "classes": visible})

    def isolate(self, code):
        visible = isolated_class(code)
        self.state["classes"] = visible
        self.send({"action": "classes", "classes": visible})

    def show_all(self):
        visible = list(range(256))
        self.state["classes"] = visible
        self.send({"action": "classes", "classes": visible})
