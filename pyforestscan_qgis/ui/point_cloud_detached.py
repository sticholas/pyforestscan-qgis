"""Detachable linked view windows; editor authority stays in the owning workspace."""
from dataclasses import asdict
from qgis.PyQt.QtCore import Qt, QEvent, QPointF, QTimer, pyqtSignal
from qgis.PyQt.QtGui import QMouseEvent
from qgis.PyQt.QtWidgets import (QTabBar, QDialog, QVBoxLayout, QHBoxLayout,
                                QToolButton, QComboBox, QInputDialog, QMenu)
from ..compat.qt import qt_enum
from ..core.point_cloud.linked_query import view_ring
from ..core.point_cloud.selection_impact import selection_impact_suffix
from .point_cloud_widgets import StableViewerStatus, StableViewerHelp


class LinkedTabBar(QTabBar):
    detachRequested = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.drag_id = None

    def mouseMoveEvent(self, event):
        point = event.position().toPoint() if hasattr(event,"position") else event.pos()
        left = qt_enum(Qt, "LeftButton", "MouseButton")
        # Finish Qt's tab-reorder grab before a foreign renderer can receive
        # the release. Deferring the window change avoids reparenting mid-event.
        outside = point.y() < -12 or point.y() > self.height() + 12
        if self.drag_id and event.buttons() & left and outside:
            key, self.drag_id = self.drag_id, None
            position = event.globalPosition().toPoint() if hasattr(event,"globalPosition") else event.globalPos()
            release = QMouseEvent(qt_enum(QEvent, "MouseButtonRelease", "Type"),
                QPointF(point), QPointF(position), left,
                qt_enum(Qt, "NoButton", "MouseButton"), event.modifiers())
            super().mouseReleaseEvent(release)
            self.releaseMouse()
            QTimer.singleShot(0, lambda: self.detachRequested.emit(key, position))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        point = event.position().toPoint() if hasattr(event,"position") else event.pos()
        index = self.tabAt(point)
        self.drag_id = self.tabData(index) if index >= 0 and event.button() == qt_enum(Qt,"LeftButton","MouseButton") else None
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        point = event.position().toPoint() if hasattr(event,"position") else event.pos()
        key, self.drag_id = self.drag_id, None
        outside = point.y() < -36 or point.y() > self.height() + 36
        super().mouseReleaseEvent(event)
        if key and outside:
            position = event.globalPosition().toPoint() if hasattr(event,"globalPosition") else event.globalPos()
            self.detachRequested.emit(key,position)


class DetachedView(QDialog):
    dockRequested = pyqtSignal(str)

    def __init__(self, controller, view_id, entry):
        super().__init__(controller.page, qt_enum(Qt,"Window","WindowType"))
        from .point_cloud_page import ViewerSurface
        self.controller, self.view_id = controller, view_id
        self.worker = None
        self.telemetry = {}
        self.overlay = None
        self.event_id = None
        self.context_sent = False
        self.closing = False
        self.selection_error = ""
        controller.limitsChanged.connect(self.clear_selection_error)
        self.resident_state = entry
        self.setWindowTitle(controller.page.workspace.views[view_id].title)
        self.resize(960,720)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8,8,8,8)
        row = QHBoxLayout()
        self.action_buttons = {}
        for text, action in (("Fit","fit"),("Undo","undo"),("Redo","redo"),("Invert","invert")):
            button = QToolButton()
            button.setText(text)
            if action == "invert":
                button.setToolTip("Select every original source point not currently selected. Runs a cancellable full-source query.")
                button.setAccessibleName("Invert Selection")
            button.clicked.connect(lambda _=False,a=action:self.action(a))
            row.addWidget(button)
            self.action_buttons[action] = button
        self.resize_button = QToolButton()
        self.resize_button.setText("Resize")
        self.resize_button.setAccessibleName("Grow or Shrink Selection")
        self.resize_button.setToolTip(
            "Grow or shrink one Replace selection in dataset units. XY outlines change; "
            "existing height limits remain unchanged.")
        resize_menu = QMenu(self.resize_button)
        resize_menu.addAction("Grow Selection...", lambda:self.controller.page.editor.resize_selection(1))
        resize_menu.addAction("Shrink Selection...", lambda:self.controller.page.editor.resize_selection(-1))
        self.resize_button.setMenu(resize_menu)
        self.resize_button.setPopupMode(qt_enum(QToolButton,"InstantPopup","ToolButtonPopupMode"))
        row.addWidget(self.resize_button)
        self.mode = QComboBox()
        self.mode.addItems(("Classification","Elevation","RGB","Intensity"))
        self.mode.currentTextChanged.connect(lambda value:self.send({"action":"mode","mode":value}))
        row.addWidget(self.mode)
        from .point_cloud_appearance import PointAppearance
        self.appearance = PointAppearance(self._send_point_display, self)
        row.addWidget(self.appearance)
        from .point_cloud_class_visibility import ClassVisibilityMenu
        self.class_visibility = ClassVisibilityMenu(self.send, self)
        row.addWidget(self.class_visibility)
        from .point_cloud_tools import SelectionTools
        self.tool = SelectionTools(self)
        self.tool.setProfileToolsVisible(
            controller.page.workspace.views[view_id].view_type == "VERTICAL_SLICE")
        row.addWidget(self.tool)
        self.selection_mode = QComboBox()
        from ..core.point_cloud.selection_presentation import SELECTION_COMBINE_OPTIONS
        for label, value in SELECTION_COMBINE_OPTIONS:
            self.selection_mode.addItem(label, value)
        self.selection_mode.setAccessibleName("How this shape changes the current selection")
        self.selection_mode.setToolTip(
            "Start new selection clears the previous selection. Add keeps it. Remove subtracts "
            "matching original-source points.")
        row.addWidget(self.selection_mode)
        self.tool.setBrushRadius(controller.brush_radius)
        self.tool.currentTextChanged.connect(self.change_tool)
        self.tool.brushRadiusChanged.connect(controller.set_brush_radius)
        controller.brushRadiusChanged.connect(self.tool.setBrushRadius)
        self.tool.setSpherePlacement(controller.sphere_axis, controller.sphere_height,
            "HeightAboveGround" in controller.page.editor.state.get("dimensions", []))
        self.tool.spherePlacementChanged.connect(controller.set_sphere_placement)
        controller.spherePlacementChanged.connect(self.tool.setSpherePlacement)
        classify = QToolButton()
        classify.setText("Classify")
        classify.clicked.connect(self.classify)
        self.classify_button = classify
        row.addWidget(classify)
        dock = QToolButton()
        dock.setText("Dock to tabs")
        dock.setToolTip("Return this view to the workspace tabs without changing selection or edits.")
        dock.clicked.connect(lambda:self.dockRequested.emit(self.view_id))
        row.addWidget(dock)
        layout.addLayout(row)
        from .point_cloud_selection_limits import SelectionLimits
        self.limits = SelectionLimits(controller, view_id, self)
        layout.addWidget(self.limits)
        self.surface = ViewerSurface(self)
        layout.addWidget(self.surface,1)
        self.status = StableViewerStatus("Opening linked view...")
        layout.addWidget(self.status)
        self.help = StableViewerHelp(self)
        self.help.set_help("This window shares the original source, selection and edit journal. Dock to tabs returns it to the workspace.")
        layout.addWidget(self.help)
        self.surface.resized.connect(lambda w,h:self.send({"action":"resize","width":w,"height":h}))
        self.surface.visibility.connect(lambda visible:self.send({"action":"visible","visible":visible}))
        self.show()
        from .point_cloud_resident_views import transfer_surface
        worker = entry["worker"]
        self.worker = worker
        self.telemetry = entry["state"]["_view_state"] or {}
        self.context_sent = True
        self.event_id = (self.telemetry.get("editor", {}).get("event") or {}).get("id")
        self.mode.blockSignals(True)
        self.mode.setCurrentText(self.telemetry.get("mode", "Classification"))
        self.mode.blockSignals(False)
        self.refresh_edit_controls()
        worker.update.connect(self.update_view)
        worker.finished.connect(self.finished)
        transfer_surface(worker, self.surface, entry["surface"])

    def send(self, value):
        if self.worker and not self.closing:
            self.worker.send(value)

    def _send_point_display(self, value):
        self.send(value)
        self.controller.set_point_display(
            self.view_id,
            value.get("style", "Circular"),
            value.get("size", 0),
        )

    def clear_selection_error(self):
        self.selection_error = ""

    def change_tool(self, value):
        view = self.controller.page.workspace.views[self.view_id]
        if value in ("AboveLine", "BelowLine"):
            from ..core.point_cloud.linked_selection import profile_line_selection_error
            self.selection_error = profile_line_selection_error(view.view_type)
            if self.selection_error:
                self.tool.blockSignals(True)
                self.tool.setCurrentText("Pointer")
                self.tool.blockSignals(False)
                self.send({"action":"selection_tool", "tool":"Pointer"})
                self.status.setText(self.selection_error)
                return
        if value == "Box":
            from ..core.point_cloud.linked_selection import box_selection_error
            self.selection_error = box_selection_error(view.view_type, self.controller.depth)
            if self.selection_error:
                self.tool.blockSignals(True)
                self.tool.setCurrentText("Pointer")
                self.tool.blockSignals(False)
                self.send({"action":"selection_tool", "tool":"Pointer"})
                self.status.setText(self.selection_error)
                return
        options = {"brush_radius": self.tool.brushRadius()} if value == "Brush" else {}
        if value == "Sphere":
            options = {"sphere_axis": self.tool.sphereAxis(),
                       "sphere_height": self.tool.sphereHeight()}
        self.send({"action":"selection_tool", "tool":value,
                   "mode":self.selection_mode.currentData() or "REPLACE", **options})

    def refresh_edit_controls(self):
        editor = self.controller.page.editor
        ready = bool(editor.worker and editor.state.get("ready")) and not editor.busy
        self.tool.setEnabled(ready and not self.controller.depth_error)
        self.selection_mode.setEnabled(ready)
        self.classify_button.setEnabled(ready and bool(
            (editor.state.get("selection") or {}).get("resolved_point_count")))
        self.action_buttons["undo"].setEnabled(ready and bool(editor.state.get("can_undo")))
        self.action_buttons["redo"].setEnabled(ready and bool(editor.state.get("can_redo")))
        self.action_buttons["invert"].setEnabled(ready and bool(editor.state.get("selection")))
        self.resize_button.setEnabled(ready and bool(editor.state.get("selection")))

    def action(self, action):
        if action in ("undo","redo","invert"):
            self.controller.page.editor.send(action)
        else:
            self.send({"action":action})

    def classify(self):
        editor = self.controller.page.editor
        if editor.busy or not editor.state.get("selection"):
            return
        value,ok = QInputDialog.getInt(self,"Classification","New LAS classification",editor.code.value(),0,255)
        if ok:
            editor.stage("Classification",value)

    def update_view(self,value):
        if self.closing:
            return
        if value.get("started"):
            self.send({"action":"resize","width":self.surface.width(),"height":self.surface.height()})
        if value.get("error"):
            self.status.setText(value["error"])
        telemetry = value.get("telemetry",{})
        if not telemetry.get("ready") or not telemetry.get("editor",{}).get("ready"):
            return
        self.telemetry = telemetry
        self.appearance.sync(telemetry)
        self.class_visibility.sync(telemetry)
        view = self.controller.page.workspace.views.get(self.view_id)
        if view is None:
            return
        if not self.context_sent:
            context = asdict(view)
            if view.view_type != "OVERVIEW_3D":
                context["corridor"] = view_ring(context)
            result = self.controller.query_results.get(view.view_id) or {}
            context["display_projection"] = result.get(
                "display_projection", view.geometry.get("display_projection", "SOURCE_XY"))
            self.send({"action":"linked_view","view":context})
            self.send({"action":"scene_visibility", "visibility":view.scene_visibility})
            if view.camera:
                self.send({"action":"camera","camera":view.camera})
            self.mode.setCurrentText(view.render_mode)
            self.send({"action":"mode","mode":view.render_mode})
            if view.display_filters.get("classes") is not None:
                self.send({"action":"classes","classes":view.display_filters["classes"]})
            self.context_sent = True
        acknowledged = telemetry["editor"].get("view_id") == self.view_id
        editor = self.controller.page.editor
        self.limits.refresh()
        self.refresh_edit_controls()
        event = telemetry["editor"].get("event")
        if acknowledged and event and event["id"] != self.event_id:
            self.event_id = event["id"]
            self.selection_error = ""
            if event.get("geometry") and not editor.busy:
                try:
                    constraints = self.controller.selection_values_for(view, event, telemetry)
                    values = {key: event[key] for key in (
                        "circle_center", "circle_radius", "brush_path", "brush_radius", "brush_tolerance",
                        "profile_brush_path", "profile_brush_radius", "profile_brush_tolerance",
                        "sphere_center", "sphere_radius", "sphere_axis", "profile_line",
                        "profile_line_side") if key in event}
                    editor.send("select", geometry=event["geometry"], mode=event["mode"],
                                constraints=constraints, **values)
                except ValueError as error:
                    self.selection_error = str(error)
            elif event.get("action") in ("undo","redo"):
                editor.send(event["action"])
            self.tool.blockSignals(True)
            self.tool.setCurrentText("Pointer")
            self.tool.blockSignals(False)
        if acknowledged:
            self.controller.observe_cursor(self.view_id, telemetry["editor"].get("cursor"))
            view = self.controller.page.workspace.views[self.view_id]
            lod = dict(view.lod)
            lod["quality"] = telemetry.get("quality", lod.get("quality", "Automatic"))
            self.controller.page.workspace.update_view(self.view_id,camera=telemetry.get("camera",{}),
                render_mode=telemetry.get("mode","Classification"),
                display_filters={"classes":telemetry.get("classes"),"height_filter":telemetry.get("height_filter")},
                lod=lod)
        signature = (editor.state.get("overlay"),editor.state.get("revision"))
        if signature[0] and signature != self.overlay:
            self.send({"action":"editor_overlay","path":signature[0]})
            self.overlay = signature
        selected = (editor.state.get("selection") or {}).get("resolved_point_count",0)
        impact = selection_impact_suffix(selected, editor.state.get("point_count", 0))
        read_only = str(editor.source).lower().endswith("ept.json")
        cursor = self.controller.cursor_summary(self.view_id)
        self.status.setText(cursor["text"] or (
            "EPT view-only | Editing requires an immutable local derivative." if read_only else
            self.selection_error or f"Selected: {selected:,} source points | {editor.state.get('edits',0)} staged edits{impact}"))
        self.status.setToolTip(cursor["details"])
        self.controller.coordinate_resources()

    def finished(self):
        self.worker = None

    def release(self):
        if not self.worker or getattr(self.worker, "_surface_transfer", None):
            return None
        self.closing = True
        worker, self.worker = self.worker, None
        worker.update.disconnect(self.update_view)
        worker.finished.disconnect(self.finished)
        entry = self.resident_state
        entry["state"]["_view_state"] = self.telemetry
        entry["geometry"] = self.controller.page.workspace.views[self.view_id].geometry
        self.hide()
        return entry

    def shutdown(self):
        if self.closing:
            return
        self.controller.clear_cursor(self.view_id)
        self.closing = True
        if self.worker:
            self.worker.update.disconnect(self.update_view)
            self.worker.finished.connect(self.deleteLater)
            self.worker.stop("linked_window_close")
        else:
            self.deleteLater()

    def closeEvent(self,event):
        if not self.closing:
            self.dockRequested.emit(self.view_id)
            if not self.closing:
                event.ignore()
                return
        self.shutdown()
        event.accept()
