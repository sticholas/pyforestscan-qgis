"""Qt-only editor controls. Scientific work belongs to the managed child."""
from __future__ import annotations
from dataclasses import asdict
import json
from pathlib import Path
import queue
import subprocess
import threading
import time
from uuid import uuid4

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QThread, QUrl, Qt, pyqtSignal
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
    selectionProcessingRequested = pyqtSignal(object)

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
        self.pending_annotation = None
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
        from ..core.point_cloud.selection_presentation import SELECTION_COMBINE_OPTIONS
        for label, value in SELECTION_COMBINE_OPTIONS:
            self.mode.addItem(label, value)
        self.mode.setAccessibleName("How this shape changes the current selection")
        self.mode.setToolTip(
            "Start new selection clears the previous selection first. Add keeps it and adds matching "
            "points. Remove subtracts matching points. Hold Shift for Add or Alt for Remove when "
            "starting a shape. Rendered points are never edit membership.")
        self.tool.currentTextChanged.connect(self.change_tool)
        self.tool.brushRadiusChanged.connect(
            lambda _value: self.change_tool("Brush") if self.tool.currentText() == "Brush" else None)
        self.tool.spherePlacementChanged.connect(
            lambda _axis, _height: self.change_tool("Sphere") if self.tool.currentText() == "Sphere" else None)
        self.mode.currentTextChanged.connect(lambda _: self.change_tool(self.tool.currentText()))
        row.addWidget(self.tool)
        self.mode_label = QLabel("New shape:")
        self.mode_label.setToolTip(self.mode.toolTip())
        row.addWidget(self.mode_label)
        row.addWidget(self.mode)
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
        self.measurement_button = spatial_button("Measure Point-to-Point", "mActionMeasure.svg",
            "Measure between two displayed source points without changing the camera. Both picks are re-resolved "
            "against the immutable full-resolution source before distance values are saved.", self)
        self.measurement_button.setCheckable(True)
        self.measurement_button.clicked.connect(self.start_measurement)
        measurement_menu = QMenu(self.measurement_button)
        distance_menu = measurement_menu.addMenu("Distance")
        point_measurement_action = distance_menu.addAction("3D Point-to-Point")
        point_measurement_action.setToolTip(
            "Pick two source points in Overview or Area Detail and report horizontal, vertical, "
            "and 3D distance with source units.")
        point_measurement_action.triggered.connect(self.start_measurement)
        self.profile_measurement_action = distance_menu.addAction(
            "Cross-Section Distance (Profile)")
        self.profile_measurement_action.setToolTip(
            "In Profile, pick two points and report distance along the profile, vertical change, "
            "and cross-section distance in source units.")
        self.profile_measurement_action.triggered.connect(self.start_profile_measurement)
        self.tree_height_action = distance_menu.addAction("Tree Height (Profile)")
        self.tree_height_action.setToolTip(
            "In Profile, pick the tree base and top. Original source records are resolved; HAG is "
            "used when the profile vertical axis is Height Above Ground.")
        self.tree_height_action.triggered.connect(self.start_tree_height_measurement)
        measurement_menu.addSeparator()
        self.area_measurement_action = measurement_menu.addAction("Planar Area from Polygon")
        self.area_measurement_action.setToolTip(
            "Draw a horizontal boundary in source coordinates and report its area and perimeter.")
        self.area_measurement_action.triggered.connect(self.start_area_measurement)
        self.annotation_action = measurement_menu.addAction("Place Linked Marker...")
        self.annotation_action.setToolTip(
            "Place a named reference point shared across views. This is an annotation, not a "
            "distance measurement or point-cloud edit.")
        self.annotation_action.triggered.connect(self.start_annotation)
        self.measurement_button.setMenu(measurement_menu)
        self.measurement_button.setPopupMode(
            qt_enum(QToolButton, "MenuButtonPopup", "ToolButtonPopupMode"))
        row.addWidget(self.measurement_button)
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
        self.quick_targets.setText("Class presets")
        self.quick_targets.setAccessibleName("Classification presets")
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
        self.apply_classification = self.button("Stage Classification", "SP_DialogApplyButton",
            lambda: self.stage("Classification", self.code.value()),
            "Review and stage this class for all selected original-source points. The change is "
            "undoable and appears in a new export only; the original is never rewritten.")
        self.apply_classification.setText("Stage Classification")
        self.apply_classification.setToolButtonStyle(
            qt_enum(Qt, "ToolButtonTextBesideIcon", "ToolButtonStyle"))
        actions.addWidget(self.apply_classification)
        self.classify_while = QToolButton()
        self.classify_while.setText("Auto-stage new selections")
        self.classify_while.setCheckable(True)
        self.classify_while.setAccessibleName("Classify each new Replace selection")
        self.classify_while.setToolTip(
            "When enabled, each newly resolved non-empty Replace selection is staged with the chosen class. "
            "Add/Subtract composites, restores, inversion and resizing are never applied automatically.")
        self.classify_while.toggled.connect(lambda _checked: self.refresh_controls())
        actions.addWidget(self.classify_while)
        flags = QToolButton()
        flags.setText("Point flags")
        flags.setToolTip("Stage a clear point treatment: noise changes Classification; Withheld "
                         "retains flagged points; Remove on Export affects only a new derivative.")
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
        self.measurements_action = details_menu.addAction("Measurements")
        self.measurements_action.triggered.connect(self.show_measurements)
        self.clear_measurements_action = details_menu.addAction("Clear Measurements")
        self.clear_measurements_action.triggered.connect(
            lambda: self.send("clear_measurements"))
        self.annotations_action = details_menu.addAction("Linked Markers")
        self.annotations_action.triggered.connect(self.show_annotations)
        self.edit_annotation_action = details_menu.addAction("Edit Linked Marker...")
        self.edit_annotation_action.triggered.connect(self.edit_annotation)
        self.remove_annotation_action = details_menu.addAction("Remove Linked Marker...")
        self.remove_annotation_action.triggered.connect(self.remove_annotation)
        self.clear_annotations_action = details_menu.addAction("Clear Linked Markers")
        self.clear_annotations_action.triggered.connect(
            lambda: self.send("clear_annotations"))
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
        self.object_focus_menu = self.object_menu.addMenu("Object Focus")
        self.show_all_objects_action = self.object_focus_menu.addAction("Show All Points")
        self.fade_other_objects_action = self.object_focus_menu.addAction("Fade Other Points")
        self.isolate_object_action = self.object_focus_menu.addAction("Isolate Selected Object")
        self.object_focus_actions = {
            "SHOW_ALL": self.show_all_objects_action,
            "FADE_OTHERS": self.fade_other_objects_action,
            "ISOLATE": self.isolate_object_action,
        }
        for mode, action in self.object_focus_actions.items():
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, value=mode: self.set_object_focus(value))
        self.show_all_objects_action.setToolTip(
            "Restore normal visibility in every linked view. This changes display only.")
        self.fade_other_objects_action.setToolTip(
            "Keep the exact selected object bright and fade other points in every linked view. No edit is staged.")
        self.isolate_object_action.setToolTip(
            "Show the exact selected object overlay while hiding other points in every linked view. No edit is staged.")
        self.object_menu.addSeparator()
        self.object_operations_menu = self.object_menu.addMenu("Object Operations")
        self.create_object_action = self.object_operations_menu.addAction("Create New Object from Selection")
        self.create_object_action.setToolTip(
            "Assign the current authoritative source selection to the next unused object ID. "
            "The operation is journal-backed and does not rewrite the source.")
        self.create_object_action.triggered.connect(self.create_object_from_selection)
        self.assign_object_action = self.object_operations_menu.addAction("Assign Selection to Object ID...")
        self.assign_object_action.setToolTip(
            "Stage the current authoritative source selection into an existing or new object ID. "
            "The source is unchanged until a new edited cloud is exported.")
        self.assign_object_action.triggered.connect(self.assign_selection_to_object)
        self.unassign_object_action = self.object_operations_menu.addAction("Unassign Selected Points")
        self.unassign_object_action.setToolTip(
            "Stage the current authoritative source selection to the confirmed unassigned value. "
            "This is undoable and never rewrites the source.")
        self.unassign_object_action.triggered.connect(self.unassign_selection_from_object)
        self.object_operations_menu.addSeparator()
        self.begin_object_split_action = self.object_operations_menu.addAction("Choose Portion to Split")
        self.begin_object_split_action.setToolTip(
            "Keep the exact active object as the split parent, then draw the portion to move into a new ID. "
            "The final portion is resolved from the original full-resolution source.")
        self.begin_object_split_action.triggered.connect(self.begin_object_split)
        self.finish_object_split_action = self.object_operations_menu.addAction("Split Selected Portion to New Object")
        self.finish_object_split_action.setToolTip(
            "Intersect the current authoritative selection with the saved parent object and stage that subset "
            "to the next collision-safe ID. At least one point must remain in the parent.")
        self.finish_object_split_action.triggered.connect(self.finish_object_split)
        self.cancel_object_split_action = self.object_operations_menu.addAction("Cancel Split")
        self.cancel_object_split_action.triggered.connect(lambda: self.send("cancel_object_split"))
        self.merge_object_action = self.object_operations_menu.addAction("Merge Active Object Into...")
        self.merge_object_action.setToolTip(
            "Stage every point in the exact active object to an existing catalog object ID. "
            "The original source remains unchanged and the merge is undoable.")
        self.merge_object_action.triggered.connect(self.merge_active_object)
        self.object_catalog_results_action = self.object_menu.addAction("Catalog Details")
        self.object_catalog_results_action.triggered.connect(self.show_object_catalog)
        self.effective_object_audit_action = self.object_menu.addAction("Audit Effective Object Counts")
        self.effective_object_audit_action.setToolTip(
            "Explicitly stream the original source and replay staged edits to calculate exact current object counts. "
            "This is read-only, cancellable, and may take time on a large cloud.")
        self.effective_object_audit_action.triggered.connect(
            lambda: self.send("effective_object_audit"))
        self.effective_object_results_action = self.object_menu.addAction("Effective Count Results")
        self.effective_object_results_action.triggered.connect(self.show_effective_object_audit)
        self.object_review_menu = self.object_menu.addMenu("Review / Notes")
        self.mark_object_reviewed_action = self.object_review_menu.addAction("Mark Reviewed")
        self.mark_object_reviewed_action.triggered.connect(
            lambda: self.set_object_reviewed(True))
        self.mark_object_unreviewed_action = self.object_review_menu.addAction("Mark Not Reviewed")
        self.mark_object_unreviewed_action.triggered.connect(
            lambda: self.set_object_reviewed(False))
        self.edit_object_note_action = self.object_review_menu.addAction("Add or Edit Note...")
        self.edit_object_note_action.setToolTip(
            "Save a session note for the exact source object. Notes are not written into LAS dimensions or exports.")
        self.edit_object_note_action.triggered.connect(self.edit_object_note)
        self.show_object_review_action = self.object_review_menu.addAction("Review Details")
        self.show_object_review_action.triggered.connect(self.show_object_review)
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
        self.prepare_product_button = self.button("Prepare Product", "SP_ArrowRight", self.prepare_product,
            "Prepare the authoritative selection as a bounded product scope in Mission Control. This does not start processing or modify the source.")
        history_row.addWidget(self.prepare_product_button)
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
        self.measurement_button.setEnabled(ready)
        self.area_measurement_action.setEnabled(ready)
        self.profile_measurement_action.setEnabled(ready and self.active_vertical_slice())
        self.tree_height_action.setEnabled(ready and self.active_vertical_slice())
        self.annotation_action.setEnabled(ready)
        self.measurements_action.setEnabled(bool(self.state.get("measurements")))
        self.clear_measurements_action.setEnabled(ready and bool(self.state.get("measurements")))
        has_annotations = bool(self.state.get("annotations"))
        self.annotations_action.setEnabled(has_annotations)
        self.edit_annotation_action.setEnabled(ready and has_annotations)
        self.remove_annotation_action.setEnabled(ready and has_annotations)
        self.clear_annotations_action.setEnabled(ready and has_annotations)
        if hasattr(self.page, "linked"):
            self.page.linked.limits.refresh()
            self.tool.setEnabled(ready and not self.page.linked.depth_error)
            self.page.linked.refresh_detached_controls()
        self.edit_controls.setVisible(bool((self.state.get("selection") or {}).get("resolved_point_count"))
                                      or self.classify_while.isChecked())
        self.edit_controls.setEnabled(ready)
        self.undo_button.setEnabled(ready and self.state.get("can_undo", False))
        self.redo_button.setEnabled(ready and self.state.get("can_redo", False))
        self.export_button.setEnabled(ready and self.state.get("edits", 0) > 0)
        self.use_button.setEnabled(bool(self.state.get("exported")) and not self.busy)
        self.prepare_product_button.setEnabled(ready and bool(
            (self.state.get("selection") or {}).get("resolved_point_count")))
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
        self.create_object_action.setEnabled(ready and selected and has_policy and
            self.state["object_id_policy"].get("next_available_object_id") is not None)
        self.assign_object_action.setEnabled(ready and selected and has_policy)
        self.unassign_object_action.setEnabled(ready and selected and has_policy)
        self.effective_object_audit_action.setEnabled(ready and bool(catalog) and has_policy)
        self.effective_object_results_action.setEnabled(
            bool(self.state.get("effective_object_audit")))
        split_source = self.state.get("object_split_source") or {}
        exact_active = bool(active_object and active_object.get("selection_id") ==
                            (self.state.get("selection") or {}).get("selection_id"))
        self.begin_object_split_action.setEnabled(ready and selected and has_policy and exact_active)
        self.finish_object_split_action.setEnabled(ready and selected and has_policy and bool(split_source)
            and self.state["object_id_policy"].get("next_available_object_id") is not None)
        self.cancel_object_split_action.setEnabled(ready and bool(split_source))
        self.merge_object_action.setEnabled(ready and selected and has_policy and exact_active)
        for action in (self.mark_object_reviewed_action,
                       self.mark_object_unreviewed_action,
                       self.edit_object_note_action,
                       self.show_object_review_action):
            action.setEnabled(ready and exact_active)
        focus_mode = (self.page.linked.object_focus_mode if hasattr(self.page, "linked") else "SHOW_ALL")
        focus_available = ready and selected and bool(active_object)
        self.show_all_objects_action.setEnabled(ready)
        self.fade_other_objects_action.setEnabled(focus_available)
        self.isolate_object_action.setEnabled(focus_available)
        for mode, action in self.object_focus_actions.items():
            action.setChecked(mode == focus_mode)
        self.refresh_classification_guidance()

    def refresh_classification_guidance(self):
        from ..core.point_cloud.las_classification import (
            classification_entry, classification_target_guidance)
        count = (self.state.get("selection") or {}).get("resolved_point_count", 0)
        target = classification_entry(self.code.value()).label
        prefix = f"Will stage {count:,} selected points as {target}. " if count else f"Target: {target}. "
        self.target_guidance.setText(
            prefix + classification_target_guidance(self.code.value()) + " Undo remains available.")

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
                            "mode": self.mode.currentData() or "REPLACE", **values})

    def start_measurement(self):
        if not self.viewer_ready or self.busy:
            self.measurement_button.setChecked(False)
            return
        if self.active_vertical_slice():
            self.start_profile_measurement()
            return
        self.tool.blockSignals(True)
        self.tool.setCurrentText("Pointer")
        self.tool.blockSignals(False)
        self.page.send({"action":"measurement_tool"})
        self.measurement_button.setChecked(True)
        self.summary.setText("Measurement: Click the first source point")

    def active_vertical_slice(self):
        try:
            value = self.page.linked.active().view_type
            return getattr(value, "value", value) == "VERTICAL_SLICE"
        except (AttributeError, KeyError):
            return False

    def start_profile_measurement(self):
        if not self.viewer_ready or self.busy:
            self.measurement_button.setChecked(False)
            return
        if not self.active_vertical_slice():
            self.summary.setText("Open a Vertical Slice before measuring a cross-section.")
            self.measurement_button.setChecked(False)
            return
        self.tool.blockSignals(True)
        self.tool.setCurrentText("Pointer")
        self.tool.blockSignals(False)
        self.page.send({"action":"measurement_tool", "kind":"PROFILE_DISTANCE"})
        self.measurement_button.setChecked(True)
        self.summary.setText("Cross-section: Click the first displayed profile point")

    def start_tree_height_measurement(self):
        if not self.viewer_ready or self.busy:
            self.measurement_button.setChecked(False)
            return
        if not self.active_vertical_slice():
            self.summary.setText("Open a Vertical Slice before measuring tree height.")
            self.measurement_button.setChecked(False)
            return
        self.tool.blockSignals(True)
        self.tool.setCurrentText("Pointer")
        self.tool.blockSignals(False)
        self.page.send({"action":"measurement_tool", "kind":"PROFILE_DISTANCE",
                        "purpose":"TREE_HEIGHT"})
        self.measurement_button.setChecked(True)
        self.summary.setText("Tree height: Click the tree base, then the top")

    def start_area_measurement(self):
        if not self.viewer_ready or self.busy:
            return
        self.tool.blockSignals(True)
        self.tool.setCurrentText("Pointer")
        self.tool.blockSignals(False)
        self.page.send({"action":"selection_tool", "tool":"Polygon",
                        "purpose":"MEASURE_AREA"})
        self.summary.setText(
            "Area: Draw a boundary | Finish with double-click, Enter, right-click, or the first point")

    def start_annotation(self):
        if not self.viewer_ready or self.busy:
            return
        title, accepted = QInputDialog.getText(self, "Add Linked Marker", "Marker name:")
        if not accepted:
            return
        title = title.strip()
        if not title:
            QMessageBox.information(self, "Add Linked Marker", "Enter a short marker name.")
            return
        note, accepted = QInputDialog.getMultiLineText(
            self, "Add Linked Marker", "Optional note:", "")
        if not accepted:
            return
        self.pending_annotation = {"title": title, "note": note}
        self.tool.blockSignals(True)
        self.tool.setCurrentText("Pointer")
        self.tool.blockSignals(False)
        self.page.send({"action":"annotation_tool"})
        self.measurement_button.setChecked(True)
        self.summary.setText("Linked marker: Click one displayed source point")

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
            elif event.get("action") == "MEASURE_AREA":
                self.measurement_button.setChecked(False)
                self.send("add_area_measurement", geometry=event.get("geometry"),
                          display_elevation=event.get("display_elevation"))
            elif event.get("geometry"):
                try:
                    constraints = self.page.linked.selection_values(event)
                    values = {key: event[key] for key in (
                        "circle_center", "circle_radius", "brush_path", "brush_radius", "brush_tolerance",
                        "profile_brush_path", "profile_brush_radius", "profile_brush_tolerance",
                        "sphere_center", "sphere_radius", "sphere_axis", "profile_line",
                        "profile_line_side") if key in event}
                    self.send("select", geometry=event["geometry"], mode=event["mode"],
                              constraints=constraints, **values)
                except ValueError as error:
                    self.summary.setText(str(error))
            elif event.get("action") == "measurement_anchor":
                self.measurement_button.setChecked(True)
                self.summary.setText("Measurement: First source point chosen | Click the second point")
            elif event.get("action") == "measure_points":
                self.measurement_button.setChecked(False)
                self.send("add_measurement", points=event.get("points"))
            elif event.get("action") == "measure_profile_points":
                self.measurement_button.setChecked(False)
                view = self.page.linked.active()
                if (getattr(view.view_type, "value", view.view_type) != "VERTICAL_SLICE"
                        or event.get("view_id") != view.view_id):
                    self.summary.setText(
                        "The active Vertical Slice changed; start the measurement again.")
                else:
                    self.send("add_profile_measurement", points=event.get("points"),
                              profile_geometry=asdict(view)["geometry"],
                              view_id=view.view_id, view_name=view.title,
                              purpose=event.get("purpose") or "CROSS_SECTION")
            elif event.get("action") == "annotation_point":
                details = self.pending_annotation
                self.pending_annotation = None
                self.measurement_button.setChecked(False)
                if details:
                    values = {}
                    if event.get("profile_display"):
                        view = self.page.linked.active()
                        if (getattr(view.view_type, "value", view.view_type)
                                == "VERTICAL_SLICE"):
                            values["profile_geometry"] = asdict(view)["geometry"]
                    self.send("add_annotation", point=event.get("point"),
                              **values, **details)
            elif event.get("action") in ("undo", "redo"):
                self.send(event["action"])
            elif event.get("action") == "pointer":
                self.pending_annotation = None
                self.measurement_button.setChecked(False)
            elif event.get("error"):
                self.pending_annotation = None
                self.summary.setText(event["error"])
            self.tool.blockSignals(True)
            self.tool.setCurrentText("Pointer")
            self.tool.blockSignals(False)
        self.measurement_button.setChecked(
            telemetry.get("editor", {}).get("tool") in ("MeasureDistance", "AddAnnotation"))
        signature = (self.state.get("overlay"), self.state.get("revision"))
        if self.viewer_ready and signature[0] and signature != self.sent_overlay:
            color = self.palette().color(qt_enum(QPalette, "Highlight", "ColorRole")).name()
            self.page.send({"action": "editor_overlay", "path": signature[0], "selection_color": color})
            self.sent_overlay = signature
        self.refresh_controls()

    def stage(self, attribute, value, *, confirm=True):
        selected = self.state.get("selection") or {}
        count = selected.get("resolved_point_count", 0)
        if attribute == "Classification" and confirm and count:
            from ..core.point_cloud.las_classification import classification_entry
            target = classification_entry(value).label
            answer = QMessageBox.question(
                self, "Stage Classification",
                f"Stage {count:,} selected original-source points as {target}?\n\n"
                "This is undoable and will appear only in a new exported derivative. "
                "The original point cloud will not be changed.")
            if answer != qt_enum(QMessageBox, "Yes", "StandardButton"):
                return
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

    def show_measurements(self):
        measurements = self.state.get("measurements") or []
        if not measurements:
            QMessageBox.information(self, "Measurements", "No saved measurements in this editing session.")
            return
        from ..core.point_cloud.measurement import measurement_summary
        lines = []
        for index, item in enumerate(reversed(measurements[-20:]), 1):
            lines.append(f"{index}. {measurement_summary(item)}")
            if item.get("unit_warning"):
                lines.append("   " + item["unit_warning"])
        lines.extend(("", "Anchors were resolved against original source points. "
                      "Measurements are session metadata and do not edit the cloud."))
        QMessageBox.information(self, "Point-to-Point Measurements", "\n".join(lines))

    def _choose_annotation(self, title):
        annotations = self.state.get("annotations") or []
        if not annotations:
            return None
        labels = [f"{index}. {item['title']}" for index, item in enumerate(annotations, 1)]
        selected, accepted = QInputDialog.getItem(self, title, "Linked marker:", labels, 0, False)
        if not accepted:
            return None
        try:
            return annotations[labels.index(selected)]
        except ValueError:
            return None

    def show_annotations(self):
        annotations = self.state.get("annotations") or []
        if not annotations:
            QMessageBox.information(self, "Linked Markers",
                                    "No linked markers in this editing session.")
            return
        from ..core.point_cloud.annotation import annotation_summary
        lines = []
        for index, item in enumerate(annotations, 1):
            lines.append(f"{index}. {annotation_summary(item)}")
            if item.get("note"):
                lines.append("   " + item["note"].replace("\n", "\n   "))
        lines.extend(("", "Markers are resolved original-source points and are shared across linked views."))
        QMessageBox.information(self, "Linked Markers", "\n".join(lines))

    def edit_annotation(self):
        item = self._choose_annotation("Edit Linked Marker")
        if not item:
            return
        title, accepted = QInputDialog.getText(
            self, "Edit Linked Marker", "Marker name:", text=item["title"])
        if not accepted:
            return
        note, accepted = QInputDialog.getMultiLineText(
            self, "Edit Linked Marker", "Optional note:", item.get("note", ""))
        if accepted:
            self.send("update_annotation", annotation_id=item["annotation_id"],
                      title=title, note=note)

    def remove_annotation(self):
        item = self._choose_annotation("Remove Linked Marker")
        if not item:
            return
        answer = QMessageBox.question(self, "Remove Linked Marker",
            f"Remove '{item['title']}' from this editing session?",
            qt_enum(QMessageBox, "Yes", "StandardButton") |
            qt_enum(QMessageBox, "No", "StandardButton"),
            qt_enum(QMessageBox, "No", "StandardButton"))
        if answer == qt_enum(QMessageBox, "Yes", "StandardButton"):
            self.send("remove_annotation", annotation_id=item["annotation_id"])

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

    def set_object_focus(self, mode):
        if not hasattr(self.page, "linked"):
            return
        try:
            self.page.linked.set_object_focus(mode)
        except ValueError as error:
            self.summary.setText(str(error))

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

    def create_object_from_selection(self):
        policy = self.state.get("object_id_policy") or {}
        selection = self.state.get("selection") or {}
        value = policy.get("next_available_object_id")
        if value is None or not selection.get("resolved_point_count"):
            return
        answer = QMessageBox.question(self, "Create New Object",
            f"Create {policy['field']} object {value} from "
            f"{selection['resolved_point_count']:,} selected source points? "
            "This stages an undoable edit; the original remains unchanged.")
        if answer == qt_enum(QMessageBox, "Yes", "StandardButton"):
            self.send("stage_object_id", selection_id=selection["selection_id"],
                      value=str(value))

    def unassign_selection_from_object(self):
        policy = self.state.get("object_id_policy") or {}
        selection = self.state.get("selection") or {}
        if policy and selection.get("resolved_point_count"):
            self.send("stage_object_id", selection_id=selection["selection_id"],
                      value=str(policy["unassigned_id"]))

    def begin_object_split(self):
        selection = self.state.get("selection") or {}
        if selection.get("resolved_point_count"):
            self.send("begin_object_split", selection_id=selection["selection_id"])

    def finish_object_split(self):
        selection = self.state.get("selection") or {}
        if self.state.get("object_split_source") and selection.get("resolved_point_count"):
            self.send("split_object", selection_id=selection["selection_id"])

    def merge_active_object(self):
        catalog = self.state.get("object_catalog") or {}
        active = self.state.get("active_object") or {}
        selection = self.state.get("selection") or {}
        if not catalog or not active or not selection.get("resolved_point_count"):
            return
        default_id = catalog.get("minimum_object_id", "")
        if default_id == active.get("object_id"):
            default_id = catalog.get("maximum_object_id", "")
        default = str(default_id)
        value, accepted = QInputDialog.getText(self, "Merge Object",
            f"Existing target {catalog['field']} object ID", text=default)
        if accepted:
            self.send("merge_object", selection_id=selection["selection_id"],
                      target_object_id=value)

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
                ("No unused object ID remains in this field's storage range."
                 if policy.get("allocation_exhausted") else
                 f"Next safe object ID: {policy['next_available_object_id']}")))
        QMessageBox.information(self, "Exact Object Catalog", "\n".join(lines))

    def show_effective_object_audit(self):
        report = self.state.get("effective_object_audit")
        if not report:
            return
        lines = [
            f"Field: {report['field']}",
            f"Source objects: {report['source_object_count']:,}",
            f"Effective objects: {report['effective_object_count']:,}",
            f"Staged membership changes: {report['object_id_changed']:,} points",
            f"Effective unassigned points: {report['effective_unassigned_count']:,}",
            f"Removed on export: {report['removed_on_export']:,}",
            "",
            "Largest effective objects:",
        ]
        lines.extend(f"ID {identifier}: {count:,} points"
                     for identifier, count in report.get("largest_effective_objects", []))
        lines.extend(("", "Counts include the active journal and exclude points staged for removal. "
                      "The original catalog and source are unchanged."))
        QMessageBox.information(self, "Effective Object Counts", "\n".join(lines))

    def set_object_reviewed(self, reviewed):
        selection = self.state.get("selection") or {}
        if type(reviewed) is bool and selection.get("resolved_point_count"):
            self.send("set_object_review", selection_id=selection["selection_id"],
                      reviewed=reviewed)

    def edit_object_note(self):
        selection = self.state.get("selection") or {}
        active = self.state.get("active_object") or {}
        if not active or not selection.get("resolved_point_count"):
            return
        current = self.state.get("current_object_review") or {}
        note, accepted = QInputDialog.getMultiLineText(self, "Object Note",
            f"Note for {active['field']} object {active['object_id']}",
            current.get("note", ""))
        if accepted:
            self.send("set_object_review", selection_id=selection["selection_id"], note=note)

    def show_object_review(self):
        active = self.state.get("active_object") or {}
        record = self.state.get("current_object_review") or {}
        if not active or not record:
            return
        state = "Reviewed" if record.get("reviewed") else "Not reviewed"
        note = record.get("note") or "No note"
        QMessageBox.information(self, "Object Review",
            f"{active['field']} object {active['object_id']}\n{state}\n\n{note}\n\n"
            "Review metadata is stored in the editing session, not in source points or exports.")

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
            linked = getattr(self.page, "linked", None)
            if linked and hasattr(linked, "set_measurements"):
                linked.set_measurements(value.get("measurements", []))
            if linked and hasattr(linked, "set_annotations"):
                linked.set_annotations(value.get("annotations", []))
            if (not self.state.get("active_object") and
                    getattr(linked, "object_focus_mode", "SHOW_ALL") != "SHOW_ALL" and
                    hasattr(linked, "set_object_focus")):
                linked.set_object_focus("SHOW_ALL")
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
            if count == 0 and getattr(self.page.linked, "depth", {}):
                self.summary.setText(
                    "Selected: 0 source points | No points matched the active selection height. "
                    "Adjust it or choose All heights.")
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
                exhausted = payload.pop("allocation_exhausted", False)
                self.summary.setText("Object ID range exhausted" if exhausted else
                    object_id_policy_summary(ObjectIdPolicy(**payload), next_id))
            if completed_action in ("select_object", "neighbor_object") and value.get("active_object"):
                active = value["active_object"]
                self.summary.setText(
                    f"Selected object: {active['field']} = {active['object_id']} | "
                    f"{active['point_count']:,} authoritative source points")
            if completed_action == "begin_object_split" and value.get("object_split_source"):
                split = value["object_split_source"]
                self.summary.setText(
                    f"Split parent: {split['field']} = {split['object_id']} | "
                    "Draw the portion to move, then choose Split Selected Portion to New Object")
            if completed_action == "cancel_object_split":
                self.summary.setText("Object split cancelled | Selection and staged edits are unchanged")
            if completed_action == "split_object":
                self.summary.setText(
                    f"Object split staged | {value['edits']} total edits | Original source unchanged")
            if completed_action == "merge_object":
                self.summary.setText(
                    f"Object merge staged | {value['edits']} total edits | Original source unchanged")
            if completed_action == "effective_object_audit" and value.get("effective_object_audit"):
                from ..core.point_cloud.object_audit import effective_object_audit_summary
                self.summary.setText(effective_object_audit_summary(
                    value["effective_object_audit"]))
            if completed_action == "set_object_review" and value.get("current_object_review"):
                from ..core.point_cloud.object_review import object_review_summary
                active = value.get("active_object") or {}
                self.summary.setText(
                    f"{active.get('field')} object {active.get('object_id')} | "
                    + object_review_summary(value["current_object_review"]))
            if completed_action in ("add_measurement", "add_area_measurement",
                                     "add_profile_measurement") and value.get("measurements"):
                from ..core.point_cloud.measurement import measurement_summary
                self.summary.setText("Measurement saved | " +
                    measurement_summary(value["measurements"][-1]))
            if completed_action == "clear_measurements":
                self.summary.setText("Measurements cleared | Source and edit journal unchanged")
            if completed_action == "add_annotation" and value.get("annotations"):
                from ..core.point_cloud.annotation import annotation_summary
                self.summary.setText("Linked marker saved | " +
                    annotation_summary(value["annotations"][-1]))
            if completed_action == "update_annotation":
                self.summary.setText("Linked marker updated | Source and edit journal unchanged")
            if completed_action == "remove_annotation":
                self.summary.setText("Linked marker removed | Source and edit journal unchanged")
            if completed_action == "clear_annotations":
                self.summary.setText("Linked markers cleared | Source and edit journal unchanged")
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
            self.stage("Classification", self.code.value(), confirm=False)

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

    def prepare_product(self):
        """Send the authoritative selection to guided Processing for review."""
        selection = self.state.get("selection") or {}
        definitions = self.state.get("selection_definitions") or ()
        if not selection.get("resolved_point_count") or not definitions:
            self.summary.setText("Prepare Product: resolve a non-empty authoritative selection first.")
            return
        try:
            from ..core.point_cloud.selection_processing import selection_scope_from_definition
            definition = dict(definitions[-1])
            view = self.page.workspace.views.get(definition.get("view_id"))
            view_type = getattr(getattr(view, "view_type", None), "value", str(getattr(view, "view_type", "")))
            definition["scope_kind"] = (
                "PROFILE" if view_type == "VERTICAL_SLICE" else
                "AREA" if view_type == "AREA_DETAIL" else "COLUMN")
            scope = selection_scope_from_definition(
                definition,
                source_path=self.source,
                source_fingerprint=str(self.state.get("source_fingerprint", "")),
                point_count=int(selection.get("resolved_point_count", 0)),
                view_title=str(definition.get("view_name", "")),
            )
        except (KeyError, TypeError, ValueError, OSError) as error:
            self.summary.setText("Prepare Product unavailable: " + str(error))
            return
        self.selectionProcessingRequested.emit(scope.to_processing_context())
        self.summary.setText("Product scope prepared | " + scope.summary + " | Review it in Processing.")

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
