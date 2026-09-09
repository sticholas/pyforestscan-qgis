"""Qt-only editor controls. Scientific work belongs to the managed child."""
from __future__ import annotations
import json
from pathlib import Path
import queue
import subprocess
import threading
import time
from uuid import uuid4

from qgis.PyQt.QtCore import QThread, QUrl, pyqtSignal
from qgis.PyQt.QtGui import QDesktopServices, QPalette
from qgis.PyQt.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel,
    QToolButton, QSpinBox, QMenu, QStyle, QFileDialog, QMessageBox, QListWidget)
from ..compat.qt import qt_enum
from ..core.backend.process_env import hidden_subprocess_kwargs
from ..core.point_cloud.runtime import ViewerRuntimeService

_WORKERS = set()


class EditorWorker(QThread):
    update = pyqtSignal(object)

    def __init__(self, initial):
        super().__init__()
        self.initial = initial
        self.commands = queue.Queue(maxsize=32)
        self.stopping = threading.Event()
        self.stopped_event = threading.Event()
        self.folder = None

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
            self.folder = ViewerRuntimeService().root / "editor-runs" / uuid4().hex
            self.folder.mkdir(parents=True, exist_ok=False)
            self.update.emit({"folder": str(self.folder)})
            script = Path(__file__).resolve().parents[1] / "viewer" / "editor_worker.py"
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
        self.folder = None
        self.restored_view = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        row = QHBoxLayout()
        self.tool = QComboBox()
        self.tool.addItems(("Pointer", "Polygon", "Rectangle"))
        self.tool.setToolTip("Polygon: click vertices, then double-click, Enter, right-click or click the first vertex to finish. Escape cancels. Rectangle: drag. Selection temporarily uses top view through source Z; your prior camera returns when finished or cancelled.")
        self.mode = QComboBox()
        self.mode.addItems(("Replace", "Add", "Subtract"))
        self.mode.setToolTip("Replace, add or subtract a filtered source region. Hold Shift for Add or Alt for Subtract when starting a shape in the viewer. Esc returns to navigation. Rendered point count is not edit membership.")
        self.tool.currentTextChanged.connect(self.change_tool)
        self.mode.currentTextChanged.connect(lambda _: self.change_tool(self.tool.currentText()))
        row.addWidget(self.tool, 1)
        row.addWidget(self.mode, 1)
        self.clear = self.button("Clear Selection", "SP_DialogResetButton", lambda: self.send("clear"),
                                 "Clear only the current selection. Staged edits and history remain.")
        row.addWidget(self.clear)
        layout.addLayout(row)
        from .point_cloud_widgets import StableViewerStatus
        self.summary = StableViewerStatus("Editor: Open a local source")
        layout.addWidget(self.summary)
        self.edit_controls = QWidget()
        actions = QHBoxLayout(self.edit_controls)
        actions.setContentsMargins(0, 0, 0, 0)
        self.classes = QComboBox()
        for code, name in ((0,"Created"),(1,"Unclassified"),(2,"Ground"),(3,"Low vegetation"),
                           (4,"Medium vegetation"),(5,"High vegetation"),(6,"Building"),
                           (7,"Low noise"),(9,"Water"),(17,"Bridge deck"),(18,"High noise")):
            self.classes.addItem(f"{name} ({code})", code)
        self.classes.setCurrentIndex(5)
        self.classes.setToolTip("Choose a common original LAS classification target. Ground changes can affect terrain and height normalization.")
        self.code = QSpinBox()
        self.code.setRange(0, 255)
        self.code.setValue(5)
        self.code.setToolTip("LAS classification code 0-255. Legacy point formats remain restricted to 0-31 at export.")
        self.classes.currentIndexChanged.connect(lambda _: self.code.setValue(self.classes.currentData()))
        actions.addWidget(self.classes, 1)
        actions.addWidget(self.code)
        actions.addWidget(self.button("Apply Classification", "SP_DialogApplyButton",
            lambda: self.stage("Classification", self.code.value()),
            "Stage classification for all resolved source points. The original is never rewritten; export creates a new file."))
        flags = QToolButton()
        flags.setText("Flags / Noise")
        flags.setToolTip("Noise changes Classification; Withheld retains flagged points; Removal omits them only from a new export.")
        menu = QMenu(flags)
        for label, attribute, value in (("Low Noise (7)", "Classification", 7), ("High Noise (18)", "Classification", 18),
                                        ("Mark Withheld", "Withheld", 1), ("Remove on Export", "DELETE_ON_EXPORT", 1)):
            action = menu.addAction(label)
            action.triggered.connect(lambda _=False, a=attribute, v=value: self.stage(a, v))
        flags.setMenu(menu)
        flags.setPopupMode(qt_enum(QToolButton, "InstantPopup", "ToolButtonPopupMode"))
        actions.addWidget(flags)
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
        ready = bool(self.state.get("ready")) and not self.busy and self.viewer_ready
        for control in (self.tool, self.mode, self.clear):
            control.setEnabled(ready)
        self.edit_controls.setVisible(bool((self.state.get("selection") or {}).get("resolved_point_count")))
        self.edit_controls.setEnabled(ready)
        self.undo_button.setEnabled(ready and self.state.get("can_undo", False))
        self.redo_button.setEnabled(ready and self.state.get("can_redo", False))
        self.export_button.setEnabled(ready and self.state.get("edits", 0) > 0)
        self.use_button.setEnabled(bool(self.state.get("exported")) and not self.busy)
        self.cancel.setVisible(self.busy)
        self.recover_action.setEnabled(not self.busy)
        self.logs_action.setEnabled(bool(self.folder))

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
        command = {"action": action, **values}
        if self.page._view_state:
            command["view"] = self.page._view_state
        if self.page._source_info:
            command["view_cache"] = {key: self.page._source_info.get(key)
                                    for key in ("sha256", "strategy", "cache_fingerprint")}
        if self.worker.send(command) and action != "cancel":
            self.pending_action = action
            self.busy = True
            self.refresh_controls()

    def change_tool(self, tool):
        if self.viewer_ready:
            self.page.send({"action": "selection_tool", "tool": tool, "mode": self.mode.currentText().upper()})

    def observe(self, telemetry):
        if self.viewer_worker is not self.page.worker:
            self.viewer_worker = self.page.worker
            self.sent_overlay = None
            self.event_id = None
        self.viewer_ready = bool(telemetry.get("ready") and telemetry.get("editor", {}).get("ready"))
        event = telemetry.get("editor", {}).get("event")
        if event and event["id"] != self.event_id:
            self.event_id = event["id"]
            if event.get("geometry"):
                self.send("select", geometry=event["geometry"], mode=event["mode"])
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
        lines.extend(f"Class {code}: {count:,}" for code, count in selection.get("classification_counts", []))
        for key in ("z_min", "z_max", "hag_min", "hag_max", "bounds", "source_partitions"):
            if selection.get(key) is not None:
                lines.append(f"{key.replace('_', ' ').title()}: {selection[key]}")
        lines.append("Counts describe the frozen original-source selection, not rendered LOD or staged attributes.")
        QMessageBox.information(self, "Authoritative Selection Details", "\n".join(lines))

    def update_state(self, value):
        if value.get("folder"):
            self.folder = value["folder"]
        if value.get("progress"):
            self.summary.setText(f"{value['progress']} | {value.get('count', 0):,}")
        if value.get("ready"):
            self.page.send({"action": "selection_resolution"})
            old_export = self.state.get("exported")
            self.state = value
            self.state["exported"] = value.get("exported") or old_export
            self.page.workspace.accept_editor_snapshot(self.state)
            self.busy = False
            self.source = value["source"]
            selection = value.get("selection") or {}
            count = selection.get("resolved_point_count", 0)
            codes = ", ".join(str(code) for code, _count in selection.get("classification_counts", [])[:8])
            suffix = f" | Classes: {codes}" if codes else ""
            self.summary.setText(f"Selected: {count:,} source points | {value['edits']} staged edits" + suffix)
            self.page.session_status.setText(f"Session: Autosaved | {value['edits']} staged edits, not a source rewrite")
            self.history.clear()
            self.history.addItems(value.get("history", []))
            if value.get("restored"):
                self.restored_view = value["restored"]
                self.page.source.setText(value["source"])
                self.page.start_source(value["source"])
            if value.get("exported"):
                report = value["exported"]
                changed = report.get("attribute_changes", {}).get("classification_changed", 0)
                self.summary.setText(f"Export validated | {changed:,} reclassified | {report['removed_point_count']:,} removed | Original unchanged")
            if value.get("last_attribute") == "Classification" or value.get("last_action") in ("undo", "redo"):
                self.page.mode.setCurrentText("Classification")
        if value.get("saved"):
            self.page.session_status.setText("Session: Saved | Edited cloud requires explicit export")
            self.busy = False
        if value.get("error"):
            self.page.send({"action": "selection_resolution", "error": str(value["error"])})
            suffix = " Previous authoritative selection retained." if self.pending_action == "select" else ""
            self.summary.setText(value["error"] + suffix)
            self.sent_overlay = None
            self.busy = False
        if value.get("handoff_ready"):
            self.busy = False
            self.exportReady.emit(value["handoff_ready"])
        if value.get("source_changed"):
            self.source_changed(value)
        if value.get("confirm"):
            self.busy = False
            answer = QMessageBox.question(self, "Large edit",
                f"This stages an edit for {value['count']:,} source points ({value['fraction']:.1%}). "
                "Large classification changes may affect terrain and canopy products. Continue?")
            if answer == qt_enum(QMessageBox, "Yes", "StandardButton"):
                command = dict(value["command"])
                command.pop("action", None)
                command.pop("view", None)
                self.send("stage", **command, confirmed=True)
        self.refresh_controls()

    def save_to(self, path):
        self.send("save", path=path)

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
        self.state["ready"] = False
        self.refresh_controls()
        if self.pending_initial:
            initial, self.pending_initial = self.pending_initial, None
            self.start(initial)

    def close_editor(self):
        self.page.workspace.detach_editor()
        self.pending_initial = None
        if self.worker:
            try:
                self.worker.update.disconnect()
                self.worker.finished.disconnect(self.finished)
            except (TypeError, RuntimeError):
                pass
            self.worker.stop()
            self.worker = None
