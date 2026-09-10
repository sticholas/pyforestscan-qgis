"""Qt-only editor controls. Scientific work belongs to the managed child."""
from __future__ import annotations
import json
from pathlib import Path
import queue
import subprocess
import threading
import time
from uuid import uuid4

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QThread, QUrl, pyqtSignal
from qgis.PyQt.QtGui import QColor, QDesktopServices, QIcon, QPalette, QPixmap
from qgis.PyQt.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel,
    QToolButton, QSpinBox, QMenu, QStyle, QFileDialog, QMessageBox, QListWidget,
    QInputDialog)
from ..compat.qt import qt_enum
from ..core.backend.process_env import hidden_subprocess_kwargs
from ..core.point_cloud.runtime import ViewerRuntimeService
from ..core.point_cloud.selection_impact import selection_impact, selection_impact_suffix

_WORKERS = set()


class EditorWorker(QThread):
    update = pyqtSignal(object)

    def __init__(self, initial, *, script_name="editor_worker.py", namespace="editor-runs"):
        super().__init__()
        self.initial = initial
        self.commands = queue.Queue(maxsize=32)
        self.stopping = threading.Event()
        self.stopped_event = threading.Event()
        self.folder = None
        self.script_name = script_name
        self.namespace = namespace

    def send(self, value):
        try:
            self.commands.put_nowait(value)
            return True
        except queue.Full:
            self.update.emit({"error": "Editor is busy; wait for the current operation."})
            return False

    def stop(self):
        self.stopping.set()

    def run(self):
        process = None
        try:
            from ..core.backend.service import BackendService
            engine = BackendService().processing_engine_service()
            token = engine.runtime_token_for(("dataset_inspection",))
            engine.validate_runtime_token_for_launch(token, ("dataset_inspection",))
            self.folder = ViewerRuntimeService().root / self.namespace / uuid4().hex
            self.folder.mkdir(parents=True, exist_ok=False)
            self.update.emit({"folder": str(self.folder)})
            script = Path(__file__).resolve().parents[1] / "viewer" / self.script_name
            with (self.folder / "stderr.log").open("w", encoding="utf-8") as errors:
                process = subprocess.Popen([token.executable, "-I", str(script), "--folder", str(self.folder)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
                    text=True, encoding="utf-8", env=engine.environment(), **hidden_subprocess_kwargs())
                received = queue.Queue(maxsize=32)
                def read():
                    with (self.folder / "stdout.log").open("w", encoding="utf-8") as log:
                        while True:
                            line = process.stdout.readline(2 * 1024 * 1024 + 1)
                            if not line:
                                break
                            log.write(line)
                            log.flush()
                            if len(line) > 2 * 1024 * 1024:
                                break
                            try:
                                received.put(json.loads(line), timeout=1)
                            except (ValueError, queue.Full):
                                continue
                reader = threading.Thread(target=read, daemon=True)
                reader.start()
                self.commands.put(self.initial)
                stop_time = None
                while process.poll() is None:
                    if self.stopping.is_set() and stop_time is None:
                        process.stdin.write('{"action":"close"}\n')
                        process.stdin.flush()
                        stop_time = time.monotonic()
                    if stop_time and time.monotonic() - stop_time > 5:
                        process.kill()
                        break
                    try:
                        value = self.commands.get(timeout=.05)
                        process.stdin.write(json.dumps(value, allow_nan=False) + "\n")
                        process.stdin.flush()
                    except queue.Empty:
                        pass
                    try:
                        self.update.emit(received.get_nowait())
                    except queue.Empty:
                        pass
                process.wait()
                reader.join(timeout=1)
                if not self.stopping.is_set():
                    self.update.emit({"error": "Editor process stopped. Reopen its autosaved session; the original source is unchanged."})
        except Exception as error:
            self.update.emit({"error": "Point Cloud editor: " + str(error)})
        finally:
            try:
                if process is not None:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
                    for stream in (process.stdin, process.stdout):
                        if stream:
                            stream.close()
            finally:
                self.stopped_event.set()


class EditorPanel(QWidget):
    exportReady = pyqtSignal(object)

    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self.worker = None
        self.source = ""
        self.state = {}
        self.busy = False
        self.viewer_ready = False
        self.event_id = None
        self.viewer_worker = None
        self.sent_overlay = None
        self.pending_initial = None
        self.pending_action = None
        self.cancel_requested = False
        self.folder = None
        self.restored_view = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        row = QHBoxLayout()
        from .point_cloud_tools import SelectionTools, spatial_button
        self.tool = SelectionTools(self)
        self.mode = QComboBox()
        self.mode.addItems(("Replace", "Add", "Subtract"))
        self.mode.setToolTip("Replace, add or subtract a filtered source region. Hold Shift for Add or Alt for Subtract when starting a shape in the viewer. Esc returns to navigation. Rendered point count is not edit membership.")
        self.tool.currentTextChanged.connect(self.change_tool)
        self.tool.brushRadiusChanged.connect(
            lambda _value: self.change_tool("Brush") if self.tool.currentText() == "Brush" else None)
        self.tool.spherePlacementChanged.connect(
            lambda _axis, _height: self.change_tool("Sphere") if self.tool.currentText() == "Sphere" else None)
        self.mode.currentTextChanged.connect(lambda _: self.change_tool(self.tool.currentText()))
        row.addWidget(self.tool)
        row.addWidget(self.mode, 1)
        self.clear = self.button("Clear Selection", "SP_DialogResetButton", lambda: self.send("clear"),
                                 "Clear only the current selection. Staged edits and history remain.")
        row.addWidget(self.clear)
        self.invert = spatial_button("Invert Selection", "mActionInvertSelection.svg",
            "Invert Selection: select every original source point not currently selected. This runs a full-source background query and may be large; the existing selection remains if cancelled.", self)
        self.invert.clicked.connect(lambda: self.send("invert"))
        row.addWidget(self.invert)
        self.resize_selection_button = QToolButton(self)
        self.resize_selection_button.setIcon(QgsApplication.getThemeIcon("/mActionOffsetCurve.svg"))
        self.resize_selection_button.setAccessibleName("Grow or Shrink Selection")
        self.resize_selection_button.setToolTip(
            "Grow or shrink one Replace selection by an exact dataset-unit distance. "
            "Circle, Brush, and polygon/Box outlines change in XY; Sphere radius changes in 3D. "
            "Existing height limits remain unchanged.")
        resize_menu = QMenu(self.resize_selection_button)
        resize_menu.addAction("Grow Selection...", lambda: self.resize_selection(1))
        resize_menu.addAction("Shrink Selection...", lambda: self.resize_selection(-1))
        self.resize_selection_button.setMenu(resize_menu)
        self.resize_selection_button.setPopupMode(qt_enum(QToolButton, "InstantPopup", "ToolButtonPopupMode"))
        row.addWidget(self.resize_selection_button)
        layout.addLayout(row)
        from .point_cloud_widgets import StableViewerStatus
        self.summary = StableViewerStatus("Editor: Open a local source")
        layout.addWidget(self.summary)
        self.edit_controls = QWidget()
        edit_layout = QVBoxLayout(self.edit_controls)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.setSpacing(2)
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        edit_layout.addLayout(actions)
        self.classes = QComboBox()
        from ..core.point_cloud.las_classification import STANDARD_CLASSES
        for item in STANDARD_CLASSES:
            swatch = QPixmap(12, 12)
            swatch.fill(QColor(item.color))
            self.classes.addItem(QIcon(swatch), item.label, item.code)
        self.classes.setCurrentIndex(self.classes.findData(5))
        self.classes.setToolTip("Choose a common original LAS classification target. Ground changes can affect terrain and height normalization.")
        self.code = QSpinBox()
        self.code.setRange(0, 255)
        self.code.setValue(5)
        self.code.setToolTip("LAS classification code 0-255. Legacy point formats remain restricted to 0-31 at export.")
        self.classes.currentIndexChanged.connect(lambda _: self.code.setValue(self.classes.currentData()))
        actions.addWidget(self.classes, 1)
        actions.addWidget(self.code)
        self.quick_targets = QToolButton()
        self.quick_targets.setText("Quick target")
        self.quick_targets.setAccessibleName("Quick classification target")
        self.quick_targets.setToolTip(
            "Choose a common forestry LAS class. This only changes the proposed target; "
            "Apply Classification or a later automatic Replace selection stages the edit.")
        quick_menu = QMenu(self.quick_targets)
        from ..core.point_cloud.las_classification import forestry_target_presets
        for item in forestry_target_presets():
            swatch = QPixmap(12, 12)
            swatch.fill(QColor(item.color))
            action = quick_menu.addAction(QIcon(swatch), item.label)
            action.triggered.connect(lambda _checked=False, code=item.code:
                                     self.set_classification_target(code))
        self.quick_targets.setMenu(quick_menu)
        self.quick_targets.setPopupMode(qt_enum(QToolButton, "InstantPopup", "ToolButtonPopupMode"))
        actions.addWidget(self.quick_targets)
        actions.addWidget(self.button("Apply Classification", "SP_DialogApplyButton",
            lambda: self.stage("Classification", self.code.value()),
            "Stage classification for all resolved source points. The original is never rewritten; export creates a new file."))
        self.classify_while = QToolButton()
        self.classify_while.setText("Classify each selection")
        self.classify_while.setCheckable(True)
        self.classify_while.setAccessibleName("Classify each new Replace selection")
        self.classify_while.setToolTip(
            "When enabled, each newly resolved non-empty Replace selection is staged with the chosen class. "
            "Add/Subtract composites, restores, inversion and resizing are never applied automatically.")
        self.classify_while.toggled.connect(lambda _checked: self.refresh_controls())
        actions.addWidget(self.classify_while)
        flags = QToolButton()
        flags.setText("Cleanup")
        flags.setToolTip("Noise changes Classification; Withheld retains flagged points; Removal omits them only from a new export.")
        menu = QMenu(flags)
        for label, attribute, value in (("Low Noise (7)", "Classification", 7), ("High Noise (18)", "Classification", 18),
                                        ("Mark Withheld", "Withheld", 1), ("Remove on Export", "DELETE_ON_EXPORT", 1)):
            action = menu.addAction(label)
            action.triggered.connect(lambda _=False, a=attribute, v=value: self.stage(a, v))
        flags.setMenu(menu)
        flags.setPopupMode(qt_enum(QToolButton, "InstantPopup", "ToolButtonPopupMode"))
        actions.addWidget(flags)
        self.target_guidance = StableViewerStatus()
        self.target_guidance.setAccessibleName("Classification target guidance")
        edit_layout.addWidget(self.target_guidance)
        self.code.valueChanged.connect(lambda _value: self.refresh_classification_guidance())
        layout.addWidget(self.edit_controls)
        self.edit_controls.hide()
        history_row = QHBoxLayout()
        self.undo_button = self.button("Undo", "SP_ArrowBack", lambda: self.send("undo"),
            "Undo the latest staged operation. Original points and existing exports remain unchanged. Viewer shortcut: Ctrl+Z.")
        self.redo_button = self.button("Redo", "SP_ArrowForward", lambda: self.send("redo"),
            "Redo the next journal operation. Viewer shortcut: Ctrl+Shift+Z.")
        history_row.addWidget(self.undo_button)
        history_row.addWidget(self.redo_button)
        self.history_toggle = QToolButton()
        self.history_toggle.setText("History")
        self.history_toggle.setCheckable(True)
        self.history_toggle.setToolTip("Show recent journal operations. Saved sessions retain complete undo/redo history.")
        history_row.addWidget(self.history_toggle)
        self.details_button = self.button("Editing Details", "SP_FileDialogDetailedView", lambda: None,
            "Selection statistics, autosave recovery and managed editor diagnostics. The original source remains read-only.")
        details_menu = QMenu(self.details_button)
        stats = details_menu.addAction("Selection Details")
        stats.triggered.connect(self.show_selection_details)
        self.audit_action = details_menu.addAction("Audit All Classifications")
        self.audit_action.setToolTip(
            "Explicitly scan the full original source in bounded chunks and replay staged edits to count effective classes. This can take time but never writes source points.")
        self.audit_action.triggered.connect(lambda: self.send("classification_audit"))
        self.audit_result_action = details_menu.addAction("Classification Audit Results")
        self.audit_result_action.triggered.connect(self.show_classification_audit)
        self.object_menu = details_menu.addMenu("Objects / Segments")
        self.object_discovery_action = self.object_menu.addAction("Discover Object Fields")
        self.object_discovery_action.setToolTip(
            "Explicitly scan nonstandard source dimensions for repeated categorical identifiers. "
            "Names improve ranking but no tree or segment schema is required; this does not edit points.")
        self.object_discovery_action.triggered.connect(lambda: self.send("discover_object_fields"))
        self.object_results_action = self.object_menu.addAction("Discovery Results")
        self.object_results_action.triggered.connect(self.show_object_field_discovery)
        self.build_object_catalog_action = self.object_menu.addAction("Build Exact Object Catalog...")
        self.build_object_catalog_action.triggered.connect(self.build_object_catalog)
        self.configure_object_ids_action = self.object_menu.addAction("Set Unassigned Object Value...")
        self.configure_object_ids_action.setToolTip(
            "Explicitly define the value that means unassigned before future add, remove, split or merge edits. "
            "This policy step does not edit points.")
        self.configure_object_ids_action.triggered.connect(self.configure_object_ids)
        self.object_menu.addSeparator()
        self.select_object_action = self.object_menu.addAction("Select Object ID...")
        self.select_object_action.triggered.connect(self.select_object_id)
        self.previous_object_action = self.object_menu.addAction("Previous Object")
        self.previous_object_action.triggered.connect(lambda: self.navigate_object(-1))
        self.next_object_action = self.object_menu.addAction("Next Object")
        self.next_object_action.triggered.connect(lambda: self.navigate_object(1))
        self.object_menu.addSeparator()
        self.assign_object_action = self.object_menu.addAction("Assign Selection to Object ID...")
        self.assign_object_action.setToolTip(
            "Stage the current authoritative source selection into an existing or new object ID. "
            "The source is unchanged until a new edited cloud is exported.")
        self.assign_object_action.triggered.connect(self.assign_selection_to_object)
        self.unassign_object_action = self.object_menu.addAction("Unassign Selected Points")
        self.unassign_object_action.setToolTip(
            "Stage the current authoritative source selection to the confirmed unassigned value. "
            "This is undoable and never rewrites the source.")
        self.unassign_object_action.triggered.connect(self.unassign_selection_from_object)
        self.object_catalog_results_action = self.object_menu.addAction("Catalog Details")
        self.object_catalog_results_action.triggered.connect(self.show_object_catalog)
        self.recover_action = details_menu.addAction("Recover Autosaved Session")
        self.recover_action.triggered.connect(self.recover_session)
        self.logs_action = details_menu.addAction("Open Editor Diagnostics")
        self.logs_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder)))
        self.details_button.setMenu(details_menu)
        self.details_button.setPopupMode(qt_enum(QToolButton, "InstantPopup", "ToolButtonPopupMode"))
        history_row.addWidget(self.details_button)
        history_row.addStretch(1)
        self.export_button = self.button("Export Edited Cloud", "SP_DialogSaveButton", self.export,
            "Create a NEW LAS/LAZ with staged edits. Extra temporary disk space is required. Dimensions and source SHA are verified before publication; COPC export is not yet qualified.")
        history_row.addWidget(self.export_button)
        self.cancel = self.button("Cancel Operation", "SP_DialogCancelButton", lambda: self.send("cancel"),
            "Request cancellation. A native writer step may need to finish before cancellation is acknowledged; the source and saved journal remain intact.")
        history_row.addWidget(self.cancel)
        self.use_button = self.button("Use in Process", "SP_ArrowRight", self.use_export,
            "Select the validated immutable export in Process without starting processing. The editing session remains open.")
        history_row.addWidget(self.use_button)
        layout.addLayout(history_row)
        self.history = QListWidget()
        self.history.setToolTip("Recent staged operations, newest first. The saved journal retains the full history and redo cursor.")
        self.history.setMaximumHeight(100)
        self.history.hide()
        self.history_toggle.toggled.connect(self.history.setVisible)
        layout.addWidget(self.history)
        self.refresh_controls()

    def button(self, label, icon, callback, help_text):
        button = QToolButton()
        button.setIcon(self.style().standardIcon(qt_enum(QStyle, icon, "StandardPixmap")))
        button.setAccessibleName(label)
        button.setToolTip(help_text)
        button.clicked.connect(callback)
        return button

    def refresh_controls(self):
        if hasattr(self.page, "linked"):
            self.tool.setSpherePlacement(self.page.linked.sphere_axis, self.page.linked.sphere_height,
                "HeightAboveGround" in self.state.get("dimensions", []))
            self.tool.setProfileToolsVisible(
                self.page.linked.active().view_type == "VERTICAL_SLICE")
        ready = bool(self.state.get("ready")) and not self.busy and self.viewer_ready
        for control in (self.tool, self.mode, self.clear):
            control.setEnabled(ready)
        self.invert.setEnabled(ready and bool(self.state.get("selection")))
        self.resize_selection_button.setEnabled(ready and bool(self.state.get("selection")))
        if hasattr(self.page, "linked"):
            self.page.linked.limits.refresh()
            self.tool.setEnabled(ready and not self.page.linked.depth_error)
        self.edit_controls.setVisible(bool((self.state.get("selection") or {}).get("resolved_point_count"))
                                      or self.classify_while.isChecked())
        self.edit_controls.setEnabled(ready)
        self.undo_button.setEnabled(ready and self.state.get("can_undo", False))
        self.redo_button.setEnabled(ready and self.state.get("can_redo", False))
        self.export_button.setEnabled(ready and self.state.get("edits", 0) > 0)
        self.use_button.setEnabled(bool(self.state.get("exported")) and not self.busy)
        self.cancel.setVisible(self.busy)
        self.cancel.setEnabled(self.busy and not self.cancel_requested)
        self.recover_action.setEnabled(not self.busy)
        self.logs_action.setEnabled(bool(self.folder))
        self.audit_action.setEnabled(ready)
        self.audit_result_action.setEnabled(bool(self.state.get("classification_audit")))
        self.object_discovery_action.setEnabled(ready)
        self.object_results_action.setEnabled(bool(self.state.get("object_field_discovery")))
        candidates = (self.state.get("object_field_discovery") or {}).get("candidate_fields", [])
        catalog = self.state.get("object_catalog") or {}
        active_object = self.state.get("active_object") or {}
        self.build_object_catalog_action.setEnabled(ready and bool(candidates))
        self.select_object_action.setEnabled(ready and bool(catalog))
        self.object_catalog_results_action.setEnabled(bool(catalog))
        self.configure_object_ids_action.setEnabled(ready and bool(catalog)
            and bool(catalog.get("editable_integer_ids")))
        current = active_object.get("object_id")
        self.previous_object_action.setEnabled(ready and current is not None
            and current != catalog.get("minimum_object_id"))
        self.next_object_action.setEnabled(ready and current is not None
            and current != catalog.get("maximum_object_id"))
        selected = (self.state.get("selection") or {}).get("resolved_point_count", 0) > 0
        has_policy = bool(self.state.get("object_id_policy"))
        self.assign_object_action.setEnabled(ready and selected and has_policy)
        self.unassign_object_action.setEnabled(ready and selected and has_policy)
        self.refresh_classification_guidance()

    def refresh_classification_guidance(self):
        from ..core.point_cloud.las_classification import classification_target_guidance
        self.target_guidance.setText("Target guidance | " + classification_target_guidance(self.code.value()))

    def set_classification_target(self, code):
        from ..core.point_cloud.las_classification import classification_entry
        classification_entry(code)
        self.code.setValue(code)
        index = self.classes.findData(code)
        if index >= 0:
            self.classes.setCurrentIndex(index)

    def attach(self, source):
        if str(source).lower().endswith("ept.json"):
            self.close_editor()
            self.state = {}
            self.source = source
            self.busy = False
            self.summary.setText("EPT is view-only. Editing requires an immutable local LAS/LAZ/COPC derivative; EPT metadata alone is not a safe edit identity.")
            self.refresh_controls()
            return
        if self.worker and self.source == source:
            return
        self.source = source
        self.start({"action": "open", "source": source})

    def start(self, initial):
        self.page.linked.dock_all(shutdown=True)
        self.page.workspace.detach_editor()
        if self.worker:
            self.pending_initial = initial
            self.busy = True
            self.state["ready"] = False
            self.summary.setText("Editor: Closing previous session")
            self.refresh_controls()
            self.worker.stop()
            return
        self.state = {}
        self.busy = True
        self.cancel_requested = False
        self.summary.setText("Editor: Verifying source")
        worker = EditorWorker(initial)
        self.worker = worker
        worker.update.connect(lambda value, owner=worker: self.update_state(value)
                              if self.worker is owner and self.pending_initial is None else None)
        worker.finished.connect(self.finished)
        _WORKERS.add(worker)
        worker.finished.connect(lambda: _WORKERS.discard(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()
        self.refresh_controls()

    def send(self, action, **values):
        if not self.worker:
            return
        if action not in ("cancel",) and self.busy:
            return
        if action == "cancel" and (not self.busy or self.cancel_requested):
            return
        command = {"action": action, **values}
        self.page.linked.capture()
        if self.state.get("ready"):
            command["workspace"] = self.page.workspace.to_dict()
        if self.page._view_state:
            command["view"] = self.page._view_state
        if self.page._source_info:
            command["view_cache"] = {key: self.page._source_info.get(key)
                                    for key in ("sha256", "strategy", "cache_fingerprint")}
        if self.worker.send(command):
            if action == "cancel":
                self.cancel_requested = True
                self.summary.setText("Cancellation requested | Waiting for the current bounded source read")
            else:
                self.pending_action = action
                self.cancel_requested = False
                self.busy = True
            self.refresh_controls()

    def change_tool(self, tool):
        if self.viewer_ready and not self.page.linked.depth_error:
            view = self.page.workspace.views[self.page.workspace.active_view_id]
            if tool in ("AboveLine", "BelowLine"):
                from ..core.point_cloud.linked_selection import profile_line_selection_error
                error = profile_line_selection_error(view.view_type)
                if error:
                    self.summary.setText(error)
                    self.tool.blockSignals(True)
                    self.tool.setCurrentText("Pointer")
                    self.tool.blockSignals(False)
                    self.page.send({"action": "selection_tool", "tool": "Pointer"})
                    return
            if tool == "Box":
                from ..core.point_cloud.linked_selection import box_selection_error
                error = box_selection_error(view.view_type, self.page.linked.depth)
                if error:
                    self.summary.setText(error)
                    self.tool.blockSignals(True)
                    self.tool.setCurrentText("Pointer")
                    self.tool.blockSignals(False)
                    self.page.send({"action": "selection_tool", "tool": "Pointer"})
                    return
            values = {"brush_radius": self.tool.brushRadius()} if tool == "Brush" else {}
            if tool == "Sphere":
                values = {"sphere_axis": self.tool.sphereAxis(),
                          "sphere_height": self.tool.sphereHeight()}
            self.page.send({"action": "selection_tool", "tool": tool,
                            "mode": self.mode.currentText().upper(), **values})

    def observe(self, telemetry):
        if self.viewer_worker is not self.page.worker:
            self.viewer_worker = self.page.worker
            self.sent_overlay = None
            self.event_id = None
            self.page.linked.event_id = None
        self.viewer_ready = bool(telemetry.get("ready") and telemetry.get("editor", {}).get("ready"))
        event = telemetry.get("editor", {}).get("event")
        self.viewer_ready = (self.viewer_ready and not self.page.linked.waiting and
                             self.page.linked.rendered_id == self.page.workspace.active_view_id)
        if event and event["id"] != self.event_id:
            self.event_id = event["id"]
            if self.page.linked.event(event):
                pass
            elif event.get("geometry"):
                try:
                    constraints = self.page.linked.selection_values(event)
                    values = {key: event[key] for key in (
                        "circle_center", "circle_radius", "brush_path", "brush_radius", "brush_tolerance",
                        "sphere_center", "sphere_radius", "sphere_axis", "profile_line",
                        "profile_line_side") if key in event}
                    self.send("select", geometry=event["geometry"], mode=event["mode"],
                              constraints=constraints, **values)
                except ValueError as error:
                    self.summary.setText(str(error))
            elif event.get("action") in ("undo", "redo"):
                self.send(event["action"])
            elif event.get("error"):
                self.summary.setText(event["error"])
            self.tool.blockSignals(True)
            self.tool.setCurrentText("Pointer")
            self.tool.blockSignals(False)
        signature = (self.state.get("overlay"), self.state.get("revision"))
        if self.viewer_ready and signature[0] and signature != self.sent_overlay:
            color = self.palette().color(qt_enum(QPalette, "Highlight", "ColorRole")).name()
            self.page.send({"action": "editor_overlay", "path": signature[0], "selection_color": color})
            self.sent_overlay = signature
        self.refresh_controls()

    def stage(self, attribute, value):
        selected = self.state.get("selection") or {}
        self.send("stage", attribute=attribute, value=value, selection_id=selected.get("selection_id"))

    def show_selection_details(self):
        selection = self.state.get("selection") or {}
        if not selection:
            QMessageBox.information(self, "Selection", "Draw a region to resolve source-point statistics.")
            return
        lines = [f"Source: {self.source}", f"Selected: {selection['resolved_point_count']:,} original points"]
        impact = selection_impact(selection["resolved_point_count"], self.state.get("point_count", 0))
        if impact.message:
            lines.append(impact.message + ".")
        from ..core.point_cloud.las_classification import classification_entry
        lines.extend(f"{classification_entry(code).label}: {count:,}"
                     for code, count in selection.get("classification_counts", []))
        for key in ("z_min", "z_max", "hag_min", "hag_max", "bounds", "source_partitions"):
            if selection.get(key) is not None:
                lines.append(f"{key.replace('_', ' ').title()}: {selection[key]}")
        lines.append("Counts describe the frozen original-source selection, not rendered LOD or staged attributes.")
        QMessageBox.information(self, "Authoritative Selection Details", "\n".join(lines))

    def show_classification_audit(self):
        report = self.state.get("classification_audit")
        if not report:
            return
        from ..core.point_cloud.las_classification import classification_entry
        lines = [
            "Full-resolution source-wide classification audit",
            f"Source points: {report['source_point_count']:,}",
            f"Effective points after staged removals: {report['effective_point_count']:,}",
            f"Reclassified by active journal: {report['classification_changed']:,}",
            f"Withheld: {report['withheld']:,}",
            f"Removed on export: {report['removed_on_export']:,}",
            "",
            "Effective classes:",
        ]
        lines.extend(f"{classification_entry(int(code)).label}: {count:,}"
                     for code, count in report["effective_classification_counts"].items())
        if report.get("findings"):
            lines.extend(["", "Review:", *report["findings"]])
        lines.extend(("", "The audit streamed the immutable source in bounded chunks and replayed the active journal."))
        QMessageBox.information(self, "Classification Audit Results", "\n".join(lines))

    def show_object_field_discovery(self):
        report = self.state.get("object_field_discovery")
        if not report:
            return
        lines = [
            "Full-resolution object / segment field discovery",
            f"Source points inspected: {report['source_point_count']:,}",
            "",
        ]
        candidates = report.get("candidate_fields", [])
        if not candidates:
            lines.append("No categorical object or segment candidates were found.")
        else:
            lines.append("Candidates:")
            for item in candidates[:12]:
                lines.append(
                    f"{item['name']} | {item['role'].title()} | {item['confidence'].title()} confidence | "
                    f"{item['sample_unique_count']:,} sampled values")
                lines.append("  " + item["reason"])
            if len(candidates) > 12:
                lines.append(f"{len(candidates) - 12} additional candidates are available when building a catalog.")
        rejected = len(report.get("nonstandard_numeric_fields", [])) - len(candidates)
        if rejected:
            lines.extend(("", f"Other nonstandard numeric fields reviewed: {rejected}"))
        lines.extend(("", "Discovery is read-only. Object editing is not enabled by this report."))
        QMessageBox.information(self, "Object Field Results", "\n".join(lines))

    def build_object_catalog(self):
        candidates = (self.state.get("object_field_discovery") or {}).get("candidate_fields", [])
        names = [item["name"] for item in candidates]
        if not names:
            return
        field, accepted = QInputDialog.getItem(self, "Build Exact Object Catalog",
            "Categorical source field", names, 0, False)
        if accepted:
            self.send("build_object_catalog", field=field)

    def select_object_id(self):
        catalog = self.state.get("object_catalog") or {}
        if not catalog:
            return
        active = self.state.get("active_object") or {}
        default = str(active.get("object_id", catalog.get("minimum_object_id", "")))
        value, accepted = QInputDialog.getText(self, "Select Object",
            f"{catalog['field']} object ID", text=default)
        if accepted:
            self.send("select_object", object_id=value)

    def configure_object_ids(self):
        catalog = self.state.get("object_catalog") or {}
        if not catalog or not catalog.get("editable_integer_ids"):
            return
        current = self.state.get("object_id_policy") or {}
        default = str(current.get("unassigned_id", 0))
        value, accepted = QInputDialog.getText(self, "Set Unassigned Object Value",
            f"Value in {catalog['field']} that means unassigned", text=default)
        if not accepted:
            return
        answer = QMessageBox.question(self, "Confirm Object ID Semantics",
            f"Treat {value} as the unassigned value for {catalog['field']}? "
            "This records an editing policy but does not change source points or stage an edit.")
        if answer == qt_enum(QMessageBox, "Yes", "StandardButton"):
            self.send("configure_object_id_policy", unassigned_id=value)

    def navigate_object(self, direction):
        if direction in (-1, 1):
            self.send("neighbor_object", direction=direction)

    def assign_selection_to_object(self):
        policy = self.state.get("object_id_policy") or {}
        selection = self.state.get("selection") or {}
        if not policy or not selection.get("resolved_point_count"):
            return
        active = self.state.get("active_object") or {}
        default = str(active.get("object_id", policy.get("next_available_object_id", "")))
        value, accepted = QInputDialog.getText(self, "Assign Selection to Object",
            f"Target {policy['field']} object ID", text=default)
        if accepted:
            self.send("stage_object_id", selection_id=selection["selection_id"], value=value)

    def unassign_selection_from_object(self):
        policy = self.state.get("object_id_policy") or {}
        selection = self.state.get("selection") or {}
        if policy and selection.get("resolved_point_count"):
            self.send("stage_object_id", selection_id=selection["selection_id"],
                      value=str(policy["unassigned_id"]))

    def show_object_catalog(self):
        report = self.state.get("object_catalog")
        if not report:
            return
        lines = [
            f"Field: {report['field']}",
            f"Exact objects: {report['object_count']:,}",
            f"Cataloged points: {report['cataloged_point_count']:,}",
            f"Missing values: {report['missing_value_count']:,}",
            f"ID range: {report['minimum_object_id']} to {report['maximum_object_id']}",
            ("Integer storage: ID editing policy can be configured."
             if report.get("editable_integer_ids") else
             "Non-integer storage: navigation is available, but object ID editing remains read-only."),
            "",
            "Largest objects:",
        ]
        lines.extend(f"ID {identifier}: {count:,} points"
                     for identifier, count in report.get("largest_objects", []))
        lines.extend(("", "Counts and bounds are exact original-source values. The catalog does not edit points."))
        policy = self.state.get("object_id_policy") or {}
        if policy:
            lines.extend(("", f"Confirmed unassigned value: {policy['unassigned_id']}",
                f"Next safe object ID: {policy['next_available_object_id']}"))
        QMessageBox.information(self, "Exact Object Catalog", "\n".join(lines))

    def update_state(self, value):
        completed_action = self.pending_action
        if value.get("ready") or value.get("error"):
            self.pending_action = None
        auto_classify = None
        if value.get("folder"):
            self.folder = value["folder"]
        if value.get("progress"):
            stage = str(value["progress"])
            count = value.get("count", 0)
            selection_progress = stage in ("Resolving original source points",
                                           "Restoring original source selection",
                                           "Resolving inverted original-source selection",
                                           "Resolving resized original-source selection")
            suffix = (f" | {count:,} source points checked" if count and selection_progress
                      else f" | {count:,}" if count else "")
            self.summary.setText(stage + suffix)
        if value.get("ready"):
            self.page.send({"action": "selection_resolution"})
            old_export = self.state.get("exported")
            self.state = value
            self.state["exported"] = value.get("exported") or old_export
            self.page.workspace.accept_editor_snapshot(self.state)
            self.page.linked.sync_tabs()
            self.busy = False
            self.cancel_requested = False
            self.source = value["source"]
            selection = value.get("selection") or {}
            count = selection.get("resolved_point_count", 0)
            from ..core.point_cloud.las_classification import classify_while_selecting_decision
            auto_classify = classify_while_selecting_decision(
                self.classify_while.isChecked(), completed_action,
                value.get("selection_definitions", []), count)
            from ..core.point_cloud.las_classification import classification_counts_summary
            classes = classification_counts_summary(selection.get("classification_counts", []))
            suffix = f" | {classes}" if classes else ""
            impact = selection_impact_suffix(count, value.get("point_count", 0))
            self.summary.setText(f"Selected: {count:,} source points | {value['edits']} staged edits" + suffix + impact)
            if auto_classify.message:
                self.summary.setText(self.summary.text() + " | " + auto_classify.message)
            if completed_action == "classification_audit" and value.get("classification_audit"):
                from ..core.point_cloud.classification_audit import classification_audit_summary
                self.summary.setText(classification_audit_summary(value["classification_audit"]))
            if completed_action == "discover_object_fields" and value.get("object_field_discovery"):
                from ..core.point_cloud.object_fields import object_field_discovery_summary
                self.summary.setText(object_field_discovery_summary(value["object_field_discovery"]))
            if completed_action == "build_object_catalog" and value.get("object_catalog"):
                from ..core.point_cloud.object_catalog import object_catalog_summary
                self.summary.setText(object_catalog_summary(value["object_catalog"]))
            if completed_action == "configure_object_id_policy" and value.get("object_id_policy"):
                from ..core.point_cloud.object_id_policy import ObjectIdPolicy, object_id_policy_summary
                payload = dict(value["object_id_policy"])
                next_id = payload.pop("next_available_object_id")
                self.summary.setText(object_id_policy_summary(ObjectIdPolicy(**payload), next_id))
            if completed_action in ("select_object", "neighbor_object") and value.get("active_object"):
                active = value["active_object"]
                self.summary.setText(
                    f"Selected object: {active['field']} = {active['object_id']} | "
                    f"{active['point_count']:,} authoritative source points")
            self.page.session_status.setText(f"Session: Autosaved | {value['edits']} staged edits, not a source rewrite")
            self.history.clear()
            self.history.addItems(value.get("history", []))
            if value.get("restored"):
                self.restored_view = value["restored"]
                self.page.source.setText(value["source"])
                self.page.start_source(value["source"])
                if value.get("linked_workspace"):
                    self.page.linked.restore(value["linked_workspace"])
            if value.get("exported"):
                report = value["exported"]
                changed = report.get("attribute_changes", {}).get("classification_changed", 0)
                self.summary.setText(f"Export validated | {changed:,} reclassified | {report['removed_point_count']:,} removed | Original unchanged")
            if value.get("last_attribute") == "Classification" or value.get("last_action") in ("undo", "redo"):
                self.page.mode.setCurrentText("Classification")
        if value.get("saved"):
            self.page.session_status.setText("Session: Saved | Edited cloud requires explicit export")
            self.busy = False
            self.cancel_requested = False
        if value.get("error"):
            self.page.send({"action": "selection_resolution", "error": str(value["error"])})
            suffix = (" Previous authoritative selection retained."
                      if self.pending_action in ("select", "invert", "resize_selection") else "")
            self.summary.setText(value["error"] + suffix)
            self.sent_overlay = None
            self.busy = False
            self.cancel_requested = False
        if value.get("handoff_ready"):
            self.busy = False
            self.exportReady.emit(value["handoff_ready"])
        if value.get("source_changed"):
            self.source_changed(value)
        if value.get("confirm"):
            self.busy = False
            object_edit = value.get("edit_kind") == "OBJECT_ID"
            answer = QMessageBox.question(self, "Large edit",
                f"{value.get('impact', 'Very large selection')}. This stages an edit for "
                f"{value['count']:,} source points ({value['fraction']:.1%}). "
                + ("Object membership changes will appear only in a new explicit export. Continue?"
                   if object_edit else
                   "Large classification changes may affect terrain and canopy products. Continue?"))
            if answer == qt_enum(QMessageBox, "Yes", "StandardButton"):
                command = dict(value["command"])
                next_action = command.pop("action", "stage")
                command.pop("view", None)
                self.send(next_action, **command, confirmed=True)
        self.refresh_controls()
        if auto_classify and auto_classify.apply and not self.busy:
            self.stage("Classification", self.code.value())

    def save_to(self, path):
        self.send("save", path=path)

    def resize_selection(self, direction):
        distance, ok = QInputDialog.getDouble(self, "Grow Selection" if direction > 0 else "Shrink Selection",
            "Distance in dataset horizontal units", 1, .001, 1000000, 3)
        if ok:
            self.send("resize_selection", distance=distance * direction)

    def load(self, path):
        self.start({"action": "load", "path": path})

    def recover_session(self):
        root = self.folder or str(ViewerRuntimeService().root / "editor-runs")
        path, _ = QFileDialog.getOpenFileName(self, "Recover autosaved editing session", root,
                                             "Session metadata (*.json)")
        if path:
            self.load(path)

    def export(self):
        source = Path(self.source)
        default = str(source.with_name(source.stem + "_edited_" + time.strftime("%Y%m%d_%H%M%S") + ".laz"))
        path, _ = QFileDialog.getSaveFileName(self, "Export NEW edited cloud", default, "LAZ (*.laz);;LAS (*.las)")
        if path:
            answer = QMessageBox.question(self, "Export edited cloud",
                "Create a new point cloud and validation report? The original remains unchanged. "
                "Temporary disk staging is required; PDAL regenerates compression, CRS and Extra Bytes layout records.")
            if answer == qt_enum(QMessageBox, "Yes", "StandardButton"):
                self.send("export", path=path)

    def use_export(self):
        if self.state.get("exported"):
            self.send("verify_handoff", export_id=self.state["exported"]["export_id"])

    def source_changed(self, value):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Source changed")
        dialog.setText("Saved source is unavailable. Restore access or locate the original; edits were not replayed."
            if value.get("source_unavailable") else "Source changed since this editing session was saved. Edits were not replayed.")
        locate = dialog.addButton("Locate Original", qt_enum(QMessageBox, "ActionRole", "ButtonRole"))
        unedited = dialog.addButton("Open Without Edits", qt_enum(QMessageBox, "ActionRole", "ButtonRole"))
        recovery = dialog.addButton("Advanced Recovery", qt_enum(QMessageBox, "ActionRole", "ButtonRole"))
        discard = dialog.addButton("Discard Session", qt_enum(QMessageBox, "RejectRole", "ButtonRole"))
        dialog.exec() if hasattr(dialog, "exec") else dialog.exec_()
        choice = dialog.clickedButton()
        if choice is locate:
            path, _ = QFileDialog.getOpenFileName(self, "Locate unchanged original", "", "Point clouds (*.las *.laz)")
            if path:
                self.start({"action": "load", "path": value["session_path"], "source_override": path})
        elif choice is unedited:
            self.source = ""
            self.page.source.setText(value["source_changed"])
            self.page.start_source(value["source_changed"])
        elif choice is recovery:
            QMessageBox.information(self, "Recovery safety", "Restore the original from backup or locate a byte-identical copy. "
                "Automatic rebasing onto changed points is not supported. The saved session has not been modified.\n" + value["session_path"])
        elif choice is discard:
            self.close_editor()
            if self.page.worker:
                self.page.worker.stop()
            self.state = {}
            self.summary.setText("Session closed. The saved session file remains available.")

    def finished(self):
        self.worker = None
        self.busy = False
        self.cancel_requested = False
        self.state["ready"] = False
        self.refresh_controls()
        if self.pending_initial:
            initial, self.pending_initial = self.pending_initial, None
            self.start(initial)

    def close_editor(self):
        self.page.workspace.detach_editor()
        self.pending_initial = None
        self.cancel_requested = False
        if self.worker:
            try:
                self.worker.update.disconnect()
                self.worker.finished.disconnect(self.finished)
            except (TypeError, RuntimeError):
                pass
            self.worker.stop()
            self.worker = None
