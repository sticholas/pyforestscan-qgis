"""One active native renderer, many lightweight source-linked view definitions."""
from dataclasses import asdict
import json
from pathlib import Path
from uuid import uuid4

from qgis.PyQt.QtCore import QObject, Qt
from qgis.PyQt.QtWidgets import (QToolButton, QMenu, QInputDialog, QCheckBox, QDialog,
    QFormLayout, QDialogButtonBox, QDoubleSpinBox, QComboBox)
from ..compat.qt import qt_enum
from ..core.point_cloud.workspace import ViewType
from ..core.point_cloud.linked_query import view_ring
from ..core.point_cloud.linked_selection import linked_constraints
from .point_cloud_editor import EditorWorker, _WORKERS


class LinkedViews(QObject):
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
        self.create = QToolButton()
        self.create.setText("Linked views")
        self.create.setToolTip("Draw an Area Detail region or a two-endpoint Vertical Slice in Overview. All edits share the original source.")
        menu = QMenu(self.create)
        for label, tool, purpose in (("Area Detail: Rectangle", "Rectangle", "CREATE_AREA"),
                                    ("Area Detail: Polygon", "Polygon", "CREATE_AREA"),
                                    ("Vertical Slice", "Line", "CREATE_SLICE")):
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
        self.select_filtered = QCheckBox("Select filtered points")
        self.select_filtered.setToolTip("Opt in to applying visible class and height filters to authoritative selection. Unchecked: display filters do not limit edits.")
        toolbar.addWidget(self.select_filtered)
        page.view_tabs.currentChanged.connect(self.activate_tab)
        page.view_tabs.tabCloseRequested.connect(self.close_tab)
        page.view_tabs.tabMoved.connect(lambda *_: self.persist())
        page.view_tabs.detachRequested.connect(self.detach)
        self.sync_tabs()

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
            lod={"quality":state.get("quality","Automatic")})

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
        padding, ok = QInputDialog.getDouble(self.page, "Area Detail", "Padding (source coordinate units)", 2, 0, 1000000, 3)
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
        dialog = QDialog(self.page)
        dialog.setWindowTitle("Authoritative selection depth")
        form = QFormLayout(dialog)
        axis = QComboBox()
        axis.addItem("Absolute elevation", "z_filter")
        if "HeightAboveGround" in self.page.editor.state.get("dimensions", []):
            axis.addItem("Height above ground", "hag_filter")
        form.addRow("Height dimension",axis)
        key = next(iter(self.depth),"z_filter")
        axis.setCurrentIndex(max(0,axis.findData(key)))
        enabled,low,high = self.range_controls(form,self.depth.get(key))
        self.dialog_buttons(form,dialog)
        if dialog.exec() if hasattr(dialog,"exec") else dialog.exec_():
            if enabled.isChecked() and low.value() >= high.value():
                self.page.status.setText("Height minimum must be below maximum.")
                return
            self.depth = {axis.currentData():[low.value(),high.value()]} if enabled.isChecked() else {}
            self.page.status.setText("Selection depth: custom height range" if self.depth else "Selection depth: full column within the active region")

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
        return linked_constraints(asdict(self.active()), profile_geometry=event.get("profile_geometry"),
            select_filtered=self.select_filtered.isChecked(),display=self.page._view_state,**self.depth)

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
        self.capture()
        from .point_cloud_detached import DetachedView
        window = DetachedView(self,key,self.page.worker.source)
        self.detached[key] = window
        window.dockRequested.connect(self.dock)
        if position is not None:
            window.move(position)
        self.page.worker.stop("view_detached")
        self.residents.key = None
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
        window = self.detached.pop(key,None)
        if window is None:
            return
        window.shutdown()
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
