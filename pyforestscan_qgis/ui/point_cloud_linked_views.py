"""One active native renderer, many lightweight source-linked view definitions."""
from dataclasses import asdict
import json
from pathlib import Path
from uuid import uuid4

from qgis.PyQt.QtCore import QObject, Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (QToolButton, QMenu, QInputDialog, QCheckBox, QDialog,
    QFormLayout, QDialogButtonBox, QDoubleSpinBox, QComboBox, QStyle)
from ..compat.qt import qt_enum
from ..core.point_cloud.workspace import ViewType
from ..core.point_cloud.linked_query import view_ring
from ..core.point_cloud.linked_selection import linked_constraints, selection_limit_values
from .point_cloud_editor import EditorWorker, _WORKERS


class LinkedViews(QObject):
    limitsChanged = pyqtSignal()
    brushRadiusChanged = pyqtSignal(float)
    spherePlacementChanged = pyqtSignal(str, float)

    def __init__(self, page, toolbar):
        super().__init__(page)
        self.page = page
        self.query_worker = None
        self.request_id = None
        self.cache = {}
        self.rendered_id = "overview"
        self.context_sent = False
        self.waiting = False
        self.event_id = None
        self.closing = False
        self.depth = {}
        self.original_info = {}
        self.detached = {}
        self.resource_signature = None
        from .point_cloud_resident_views import ResidentViews
        self.residents = ResidentViews(page)
        from .point_cloud_tools import spatial_button
        self.area_button = spatial_button("Area Detail", "mActionZoomToSelected.svg",
            "Area Detail: draw a rectangle in Overview to open a closer view of that region. It shares the original cloud, selection and staged edits.")
        self.area_button.clicked.connect(lambda: self.draw("Rectangle", "CREATE_AREA"))
        toolbar.addWidget(self.area_button)
        self.slice_button = spatial_button("Vertical Slice", "mActionMeasure.svg",
            "Vertical Slice: choose two endpoints in Overview, then set the corridor thickness. Opens a profile of the same cloud; it does not write or edit points.")
        self.slice_button.clicked.connect(lambda: self.draw("Line", "CREATE_SLICE"))
        toolbar.addWidget(self.slice_button)
        self.create = QToolButton()
        self.create.setText("View options")
        self.create.setAccessibleName("View options")
        self.create.setToolTip("View options: adjust the current region, open the selected area or manage linked windows. Selection and edit history remain shared.")
        menu = QMenu(self.create)
        for label, tool, purpose in (("Area Detail: Polygon", "Polygon", "CREATE_AREA"),):
            action = menu.addAction(label)
            action.triggered.connect(lambda _=False, t=tool, p=purpose: self.draw(t,p))
        menu.addAction("Open Selection in Area Detail", self.from_selection)
        menu.addAction("Adjust Active View", self.adjust)
        menu.addAction("Selection Depth", self.adjust_depth)
        menu.addAction("Move Active View to Window", lambda:self.detach(self.page.workspace.active_view_id))
        menu.addAction("Dock All Views", self.dock_all)
        self.create.setMenu(menu)
        self.create.setPopupMode(qt_enum(QToolButton, "InstantPopup", "ToolButtonPopupMode"))
        toolbar.addWidget(self.create)
        self.detach_button = QToolButton()
        self.detach_button.setIcon(page.style().standardIcon(
            qt_enum(QStyle, "SP_TitleBarNormalButton", "StandardPixmap")))
        self.detach_button.setText("Detach View")
        self.detach_button.setAccessibleName("Detach View")
        self.detach_button.setToolTip("Detach View: open the loaded view in its own window. Selection, edits and undo history stay shared. Use Dock to tabs to return it.")
        self.detach_button.clicked.connect(lambda: self.detach(page.workspace.active_view_id))
        toolbar.addWidget(self.detach_button)
        self.select_filtered = QCheckBox("Select filtered points")
        self.select_filtered.setToolTip("Opt in to applying visible class and height filters to authoritative selection. Unchecked: display filters do not limit edits.")
        toolbar.addWidget(self.select_filtered)
        page.view_tabs.currentChanged.connect(self.activate_tab)
        page.view_tabs.tabCloseRequested.connect(self.close_tab)
        page.view_tabs.tabMoved.connect(lambda *_: self.persist())
        page.view_tabs.detachRequested.connect(self.detach)
        from .point_cloud_selection_limits import SelectionLimits
        self.limits = SelectionLimits(self, parent=page.editor)
        page.editor.layout().insertWidget(1, self.limits)
        page.editor.tool.setBrushRadius(self.brush_radius)
        page.editor.tool.brushRadiusChanged.connect(self.set_brush_radius)
        self.brushRadiusChanged.connect(page.editor.tool.setBrushRadius)
        page.editor.tool.setSpherePlacement(self.sphere_axis, self.sphere_height,
            "HeightAboveGround" in page.editor.state.get("dimensions", []))
        page.editor.tool.spherePlacementChanged.connect(self.set_sphere_placement)
        self.spherePlacementChanged.connect(page.editor.tool.setSpherePlacement)
        self.sync_tabs()

    @property
    def depth(self):
        return self.page.workspace.global_filters.get("selection_limits", {})

    @depth.setter
    def depth(self, values):
        self.page.workspace.global_filters["selection_limits"] = selection_limit_values(values)

    def set_depth(self, values, *, persist=True):
        self.depth = values
        self.limitsChanged.emit()
        self.page.editor.refresh_controls()
        if persist:
            self.persist()

    @property
    def brush_radius(self):
        value = self.page.workspace.global_filters.get("brush_radius", 1.0)
        return value if type(value) in (int, float) and .001 <= value <= 1000000 else 1.0

    def set_brush_radius(self, value, *, persist=True):
        if type(value) not in (int, float) or not .001 <= value <= 1000000:
            return
        self.page.workspace.global_filters["brush_radius"] = float(value)
        self.brushRadiusChanged.emit(float(value))
        if persist:
            self.persist()

    @property
    def sphere_axis(self):
        value = self.page.workspace.global_filters.get("sphere_axis", "Z")
        return value if value in ("Z", "HeightAboveGround") else "Z"

    @property
    def sphere_height(self):
        value = self.page.workspace.global_filters.get("sphere_height", 0.0)
        return float(value) if type(value) in (int, float) and -10000000 <= value <= 10000000 else 0.0

    def set_sphere_placement(self, axis, height, *, persist=True):
        if (axis not in ("Z", "HeightAboveGround") or type(height) not in (int, float)
                or not -10000000 <= height <= 10000000):
            return
        if axis == "HeightAboveGround" and "HeightAboveGround" not in self.page.editor.state.get("dimensions", []):
            return
        self.page.workspace.global_filters.update(sphere_axis=axis, sphere_height=float(height))
        self.spherePlacementChanged.emit(axis, float(height))
        if persist:
            self.persist()

    @property
    def depth_error(self):
        for key, limits in self.depth.items():
            if limits[0] > limits[1]:
                return "Minimum exceeds maximum"
            elif key == "hag_filter" and "HeightAboveGround" not in self.page.editor.state.get("dimensions", []):
                return "Source has no stored HAG"
        return ""

    def active(self):
        return self.page.workspace.views[self.page.workspace.active_view_id]

    def source_descriptor(self):
        return self.page.editor.state.get("source_identity") or self.original_info.get("source_identity")

    def source_crs(self):
        if self.page.editor.state.get("source_crs"):
            return self.page.editor.state["source_crs"]
        srs = self.original_info.get("metadata",{}).get("srs",{})
        return srs.get("wkt") or (str(srs.get("authority","EPSG"))+":"+str(srs["horizontal"]) if srs.get("horizontal") else "")

    def restore(self, payload):
        from ..core.point_cloud.workspace import PointCloudWorkspaceModel
        restored = PointCloudWorkspaceModel.restore(payload,
            self.page.editor.state["source_fingerprint"], self.page.editor.send)
        self.page.workspace = restored
        self.brushRadiusChanged.emit(self.brush_radius)
        self.spherePlacementChanged.emit(self.sphere_axis, self.sphere_height)
        self.sync_tabs()
        self.open_active()

    def sync_tabs(self):
        tabs = self.page.view_tabs
        current = self.page.workspace.active_view_id
        keys = [tabs.tabData(i) for i in range(tabs.count())]
        desired = {key:view for key,view in self.page.workspace.views.items()
                   if key not in self.detached or view.view_type == ViewType.OVERVIEW_3D}
        if set(keys) == set(desired):
            return
        tabs.blockSignals(True)
        while tabs.count():
            tabs.removeTab(0)
        for key, view in desired.items():
            index = tabs.addTab(view.title)
            tabs.setTabData(index, key)
            if view.view_type == ViewType.OVERVIEW_3D:
                for side in ("LeftSide", "RightSide"):
                    tabs.setTabButton(index, qt_enum(type(tabs), side, "ButtonPosition"), None)
            if key == current:
                tabs.setCurrentIndex(index)
        tabs.blockSignals(False)

    def capture(self):
        page = self.page
        if self.rendered_id != page.workspace.active_view_id or not page._view_state:
            return
        state = page._view_state
        page.workspace.update_view(self.rendered_id, camera=state.get("camera", {}),
            render_mode=state.get("mode","Classification"),
            display_filters={"classes":state.get("classes"),"height_filter":state.get("height_filter")},
            lod={"quality":state.get("quality","Automatic"),
                 "point_style":state.get("point_style","Circular"), "point_size":state.get("point_size",0)})

    def persist(self):
        page = self.page
        if not page.editor.worker or not page.editor.state.get("ready"):
            return
        self.capture()
        payload = page.workspace.to_dict()
        order = [page.view_tabs.tabData(i) for i in range(page.view_tabs.count())]
        payload["views"].sort(key=lambda v: order.index(v["view_id"]) if v["view_id"] in order else len(order))
        page.editor.worker.send({"action":"workspace", "workspace":payload})

    def draw(self, tool, purpose):
        if self.active().view_type != ViewType.OVERVIEW_3D:
            self.page.status.setText("Open 3D Overview to draw a new region.")
            return
        if not self.source_descriptor() or self.page.editor.busy or not self.page._view_state:
            self.page.status.setText("Wait for source verification before creating linked views.")
            return
        self.page.send({"action":"selection_tool","tool":tool,"purpose":purpose})

    def event(self, value):
        if value.get("action") not in ("CREATE_AREA","CREATE_SLICE"):
            return False
        if value["id"] == self.event_id:
            return True
        self.event_id = value["id"]
        crs = self.source_crs()
        if not crs:
            self.page.status.setText("The source does not declare a usable CRS for linked views.")
            return True
        points = value["geometry"]
        if value["action"] == "CREATE_SLICE":
            thickness, ok = QInputDialog.getDouble(self.page, "Vertical Slice",
                "Thickness (source coordinate units)", 5, .001, 1000000, 3)
            if not ok:
                return True
            geometry = {"a":points[0],"b":points[1],"thickness":thickness,"crs":crs}
            kind = ViewType.VERTICAL_SLICE
        else:
            geometry = {"shape":"POLYGON","vertices":points,"crs":crs}
            kind = ViewType.AREA_DETAIL
        self.add(kind, geometry)
        return True

    def add(self, kind, geometry):
        self.capture()
        count = sum(v.view_type == kind for v in self.page.workspace.views.values()) + 1
        title = ("Area Detail" if kind == ViewType.AREA_DETAIL else "Vertical Slice") + f" {count}"
        key = self.page.workspace.register(kind, title, geometry=geometry)
        self.sync_tabs()
        self.page.view_tabs.setCurrentIndex(next(i for i in range(self.page.view_tabs.count())
                                                if self.page.view_tabs.tabData(i)==key))
        return key

    def from_selection(self):
        result = self.page.editor.state.get("selection") or {}
        bounds = result.get("bounds")
        if not bounds:
            self.page.status.setText("Resolve a source selection before opening its area.")
            return
        padding, ok = QInputDialog.getDouble(self.page, "Area Detail",
            "Extra margin on each side (dataset XY units)", 0, 0, 1000000, 3)
        if ok:
            x,y,_,xx,yy,_ = bounds
            self.add(ViewType.AREA_DETAIL, {"shape":"RECTANGLE","crs":self.page.editor.state["source_crs"],
                "center":[(x+xx)/2,(y+yy)/2],"width":max(xx-x+2*padding,.001),"height":max(yy-y+2*padding,.001)})

    def adjust(self):
        view = self.active()
        geometry = dict(view.geometry)
        if view.view_type == ViewType.OVERVIEW_3D:
            return
        if view.view_type == ViewType.VERTICAL_SLICE:
            dialog = QDialog(self.page)
            dialog.setWindowTitle(view.title)
            form = QFormLayout(dialog)
            thickness = QDoubleSpinBox()
            thickness.setRange(.001,1000000)
            thickness.setDecimals(3)
            thickness.setValue(geometry["thickness"])
            thickness.setToolTip("Total corridor width perpendicular to A-B, in source coordinate units. Updates query original records in the background.")
            form.addRow("Thickness",thickness)
            axis = QComboBox()
            axis.addItem("Elevation", "Z")
            if "HeightAboveGround" in self.page.editor.state.get("dimensions", []):
                axis.addItem("Height above ground", "HeightAboveGround")
            axis.setCurrentIndex(max(0,axis.findData(geometry.get("vertical_axis","Z"))))
            axis.setToolTip("Choose the stored source height dimension for the profile's vertical axis. This does not calculate or rewrite height.")
            form.addRow("Vertical axis",axis)
            enabled, low, high = self.range_controls(form,geometry.get("vertical_limits"))
            self.dialog_buttons(form,dialog)
            if not (dialog.exec() if hasattr(dialog,"exec") else dialog.exec_()):
                return
            if enabled.isChecked() and low.value() >= high.value():
                self.page.status.setText("Height minimum must be below maximum.")
                return
            geometry.update(thickness=thickness.value(),vertical_axis=axis.currentData(),
                vertical_limits=[low.value(),high.value()] if enabled.isChecked() else None)
        else:
            ring = view_ring(asdict(view))
            x,xx = min(p[0] for p in ring),max(p[0] for p in ring)
            y,yy = min(p[1] for p in ring),max(p[1] for p in ring)
            width, ok = QInputDialog.getDouble(self.page, view.title, "Width (source coordinate units)", xx-x,.001,1000000,3)
            if not ok:
                return
            height, ok = QInputDialog.getDouble(self.page, view.title, "Height (source coordinate units)", yy-y,.001,1000000,3)
            if not ok:
                return
            geometry = {"shape":"POLYGON","crs":geometry["crs"],"vertices":[
                ((px-(x+xx)/2)*width/(xx-x)+(x+xx)/2,(py-(y+yy)/2)*height/(yy-y)+(y+yy)/2)
                for px,py in ring]}
        self.page.workspace.update_view(view.view_id,geometry=geometry)
        self.open_active()

    def range_controls(self, form, limits=None):
        enabled = QCheckBox("Limit height")
        enabled.setChecked(limits is not None)
        enabled.setToolTip("Intersect selection with this explicit height interval, including its boundaries.")
        low, high = QDoubleSpinBox(), QDoubleSpinBox()
        for control in (low,high):
            control.setRange(-10000000,10000000)
            control.setDecimals(3)
        low.setValue(limits[0] if limits else 0)
        high.setValue(limits[1] if limits else 50)
        form.addRow(enabled)
        form.addRow("Minimum",low)
        form.addRow("Maximum",high)
        return enabled,low,high

    def dialog_buttons(self,form,dialog):
        buttons = QDialogButtonBox(qt_enum(QDialogButtonBox,"Ok","StandardButton") |
                                  qt_enum(QDialogButtonBox,"Cancel","StandardButton"))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

    def adjust_depth(self):
        self.limits.mode.setFocus()
        self.limits.mode.showPopup()

    def activate_tab(self, index):
        if index < 0 or self.closing:
            return
        key = self.page.view_tabs.tabData(index)
        if key not in self.page.workspace.views:
            return
        self.capture()
        self.page.workspace.activate(key)
        self.open_active()

    def open_active(self):
        page = self.page
        view = self.active()
        if view.view_id in self.detached:
            self.detached[view.view_id].raise_()
            self.detached[view.view_id].activateWindow()
            return
        self.persist()
        if self.residents.prepare(view):
            self.request_id = None
            if self.query_worker:
                self.query_worker.send({"action":"cancel"})
            return
        self.context_sent = False
        self.rendered_id = None
        self.waiting = False
        if view.view_type == ViewType.OVERVIEW_3D:
            self.request_id = None
            if self.query_worker:
                self.query_worker.send({"action":"cancel"})
            page.start_source(page.source.text(), render_only=True)
            return
        identity = self.source_descriptor()
        if not identity:
            page.status.setText("Linked views require a verified source.")
            return
        key = json.dumps([identity["sha256"],view.geometry,view.view_type],sort_keys=True)
        page.status.setText("Updating linked view...")
        self.waiting = True
        self.request_id = uuid4().hex
        from ..core.point_cloud.view_policy import next_view_budget, system_memory_pressure
        memory = system_memory_pressure() or {}
        telemetry = page._view_state or {}
        budget = next_view_budget(int(telemetry.get("budget",0)),
            viewport_pixels=max(1,page.surface.width()*page.surface.height()), moving=False,
            frame_ms=telemetry.get("frame_ms"), available_bytes=memory.get("available_bytes"),
            memory_pressure=memory.get("pressure",0), source_points=page.editor.state.get("point_count") or self.original_info.get("point_count"),
            quality=page.quality.currentText())
        allocations = page.workspace.resources.allocations(page.workspace.views,view.view_id,
            point_budget=budget.ceiling, available_ram=memory.get("available_bytes",budget.ceiling*128),
            frame_ms=telemetry.get("frame_ms",0))
        command = {"action":"query","request_id":self.request_id,"source_identity":identity,
                   "view":asdict(view),"point_budget":max(1,allocations[view.view_id]["points"])}
        if key in self.cache and self.query_worker:
            command["cached"] = self.cache[key]
        command["view_cache_key"] = self.original_info.get("cache_fingerprint")
        self.request_key = key
        if self.query_worker:
            self.query_worker.send({"action":"cancel"})
            self.query_worker.send(command)
        else:
            worker = EditorWorker(command,script_name="linked_query_worker.py",namespace="linked-queries")
            self.query_worker = worker
            worker.update.connect(self.result)
            worker.finished.connect(self.finished)
            _WORKERS.add(worker)
            worker.finished.connect(lambda: _WORKERS.discard(worker))
            worker.finished.connect(worker.deleteLater)
            worker.start()

    def result(self, value):
        if self.closing:
            return
        if value.get("progress"):
            self.page.status.setText(str(value["progress"]))
        if value.get("error") and "request_id" not in value:
            self.waiting = False
            self.page.status.setText("Linked view worker unavailable: " + value["error"])
            return
        if value.get("request_id") != self.request_id:
            return
        if value.get("linked_ready"):
            self.waiting = False
            result = value["linked_ready"]
            self.cache[self.request_key] = result
            self.page.start_source(result["path"],render_only=True)
        elif value.get("error"):
            self.waiting = False
            self.page.status.setText("Linked view unavailable: " + value["error"] + " Open Overview to continue.")

    def observe(self, telemetry):
        if not telemetry.get("ready") or not telemetry.get("editor",{}).get("ready") or self.page._pending_source or self.waiting:
            return
        if self.context_sent:
            if telemetry.get("editor",{}).get("view_id") == self.page.workspace.active_view_id:
                self.rendered_id = self.page.workspace.active_view_id
            return
        # Querying leaves the previous renderer intact but never routes its gestures to a new view.
        if self.rendered_id is None and self.page._render_only is False:
            return
        view = self.active()
        context = asdict(view)
        if view.view_type != ViewType.OVERVIEW_3D:
            context["corridor"] = view_ring(context)
        self.page.send({"action":"linked_view","view":context})
        self.page.send({"action":"point_display","style":view.lod.get("point_style","Circular"),
                        "size":view.lod.get("point_size",0)})
        self.page._restore_after_open = {"camera":view.camera or telemetry["camera"],
            "mode":view.render_mode,"classes":view.display_filters.get("classes"),
            "height_filter":view.display_filters.get("height_filter"),
            "quality":view.lod.get("quality","Automatic")}
        if not view.camera:
            self.page._restore_after_open = None
            self.page.send({"action":"mode","mode":view.render_mode})
            if view.view_type != ViewType.VERTICAL_SLICE:
                self.page.send({"action":"fit"})
        self.apply_navigation(view)
        self.rendered_id = None
        self.context_sent = True

    def apply_navigation(self, view):
        profile = view.view_type == ViewType.VERTICAL_SLICE
        self.page.navigation_mode.setEnabled(not profile)
        for button in self.page.view_buttons[1:]:
            button.setEnabled(not profile)

    def selection_values(self, event):
        if self.rendered_id != self.page.workspace.active_view_id:
            raise ValueError("Wait for the active linked view to finish opening.")
        return self.selection_values_for(self.active(), event, self.page._view_state)

    def selection_values_for(self, view, event, telemetry):
        if self.depth_error:
            raise ValueError(self.depth_error)
        values = linked_constraints(asdict(view), profile_geometry=event.get("profile_geometry"),
            select_filtered=self.select_filtered.isChecked(),display=telemetry,**self.depth)
        for key in ("z_filter", "hag_filter"):
            limits = values.get(key)
            if limits is not None and limits[0] > limits[1]:
                raise ValueError("Selection limits do not overlap the active view or filters.")
        return values

    def close_tab(self, index):
        key = self.page.view_tabs.tabData(index)
        if self.page.workspace.views[key].view_type == ViewType.OVERVIEW_3D:
            return
        self.residents.discard(key)
        was_active = key == self.page.workspace.active_view_id
        self.page.workspace.close_view(key)
        self.sync_tabs()
        if was_active:
            self.open_active()
        self.persist()

    def finished(self):
        self.query_worker = None

    def close(self):
        self.closing = True
        self.residents.clear()
        self.dock_all(shutdown=True)
        if self.query_worker:
            self.query_worker.update.disconnect(self.result)
            self.query_worker.stop()

    def detach(self, key, position=None):
        if key in self.detached:
            self.detached[key].raise_()
            return
        if key != self.rendered_id or not self.page.worker or self.waiting:
            self.page.status.setText("Open the view before moving it to a separate window.")
            return
        if getattr(self.page.worker, "_surface_transfer", None):
            self.page.status.setText("Finishing the view transfer. Please wait.")
            return
        self.capture()
        from .point_cloud_detached import DetachedView
        entry = self.residents.take_current()
        if entry is None:
            self.page.status.setText("Wait for the view to finish opening before detaching.")
            return
        window = DetachedView(self,key,entry)
        self.detached[key] = window
        window.dockRequested.connect(self.dock)
        if position is not None:
            window.move(position)
        self.rendered_id = None
        attached = [view_id for view_id in self.page.workspace.views if view_id not in self.detached]
        if attached:
            self.page.workspace.activate(attached[0])
            self.open_active()
        else:
            self.page.status.setText("View is open in a separate window. Use Dock All Views to return it.")
        self.sync_tabs()
        self.persist()

    def dock(self, key):
        window = self.detached.get(key)
        if window is None:
            return
        if window.worker is None:
            self.detached.pop(key)
            window.shutdown()
            window.close()
            self.page.workspace.activate(key)
            self.sync_tabs()
            if not self.closing:
                self.open_active()
            return
        entry = window.release()
        if entry is None:
            window.status.setText("Finishing the view transfer. Please wait.")
            return
        self.detached.pop(key)
        self.residents.receive_window(key,entry,window)
        window.close()
        self.sync_tabs()
        if not self.closing:
            self.page.workspace.activate(key)
            self.sync_tabs()
            self.open_active()
        self.persist()

    def dock_all(self, *, shutdown=False):
        for key in list(self.detached):
            if shutdown:
                window = self.detached.pop(key)
                window.shutdown()
                window.close()
            else:
                self.dock(key)

    def coordinate_resources(self):
        from ..core.point_cloud.view_policy import next_view_budget, system_memory_pressure
        page = self.page
        visible = []
        if page.worker and self.rendered_id:
            visible.append((self.rendered_id,page.worker,page._view_state or {}))
        visible.extend((key,window.worker,window.telemetry) for key,window in self.detached.items()
                       if window.worker and window.isVisible())
        if not visible:
            return
        memory = system_memory_pressure() or {}
        policy = next_view_budget(0,viewport_pixels=max(1,page.surface.width()*page.surface.height()),
            moving=False,available_bytes=memory.get("available_bytes"),memory_pressure=memory.get("pressure",0),
            quality=page.quality.currentText())
        roots = {key:max(0,int(telemetry.get("render_diagnostics",{}).get("root_points",0)))
                 for key,_,telemetry in visible}
        focused = next((key for key,window in self.detached.items()
                        if key in roots and window.isActiveWindow()), visible[0][0])
        allocation = page.workspace.resources.visible_allocations(roots,focused,point_budget=policy.ceiling)
        signature = tuple((key,id(worker),allocation[key]) for key,worker,_ in visible)
        if signature != self.resource_signature:
            for key,worker,_ in visible:
                worker.send({"action":"resource_limit","points":allocation[key]})
            self.resource_signature = signature
        for key,window in self.detached.items():
            if key in allocation and allocation[key] == 0:
                window.status.setText("View suspended to preserve graphics resources. Dock or close another view to resume.")
