"""Optional isolated viewer page; scientific imports remain in managed workers."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time

from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal, QEvent
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QComboBox, QFileDialog, QMessageBox, QSizePolicy,
    QToolButton, QCheckBox, QDoubleSpinBox, QFormLayout,
    QStyle, QListWidget, QListWidgetItem, QDialog, QTabWidget, QTabBar,
)
from ..compat.qt import qt_enum
from ..core.backend.process_env import hidden_subprocess_kwargs
from ..core.point_cloud.runtime import ViewerRuntimeService, viewer_environment
from ..core.point_cloud.run_record import ViewerRunRecord

# Workers are not children of disposable widgets. Keep them alive through unload;
# each exits after its owned subprocess is reaped, then releases this reference.
_ACTIVE_WORKERS = set()


class ViewerWorker(QThread):
    update = pyqtSignal(object)

    def __init__(self, *, source="", parent_handle=0, setup=False):
        super().__init__()
        self.source = source
        self.parent_handle = parent_handle
        self.setup = setup
        self.commands = queue.Queue(maxsize=32)
        self.stop_event = threading.Event()
        self.stopped_event = threading.Event()
        self.shutdown_origin = "user_request"
        self.run_record = None

    def send(self, command):
        try:
            self.commands.put_nowait(command)
        except queue.Full:
            pass

    def stop(self, origin="user_request"):
        self.shutdown_origin = origin
        self.stop_event.set()

    def run(self):
        process = None
        cache_lease = None
        failure = None
        service = ViewerRuntimeService()
        try:
            from qgis.core import Qgis
            from qgis.PyQt.QtCore import qVersion
            self.run_record = ViewerRunRecord(service.root / "runs", self.source,
                                             {"QGIS_version": Qgis.QGIS_VERSION, "Qt_version": qVersion()})
            self.update.emit({"diagnostics_path": str(self.run_record.folder)})
            if self.setup:
                executable = service.setup(confirmed=True, progress=lambda message: self.update.emit({"status": message}),
                                           cancelled=self.stop_event.is_set)
                from ..core.point_cloud.indexer import ViewerIndexerService
                ViewerIndexerService(service.paths).setup(confirmed=True,
                    progress=lambda message: self.update.emit({"status": message}),
                    cancelled=self.stop_event.is_set)
                self.update.emit({"status": "Viewer component ready", "setup_ready": True})
                return
            if os.name != "nt":
                raise RuntimeError("Embedded viewer is experimental on Windows; other platform adapters are not yet qualified.")
            executable = service.executable()
            source = Path(self.source).resolve(strict=True)
            viewer_root = Path(__file__).resolve().parents[1] / "viewer"
            if source.suffix.lower() in (".las", ".laz") and not source.name.lower().endswith(".copc.laz"):
                from ..core.backend.service import BackendService
                engine = BackendService().processing_engine_service()
                token = engine.runtime_token_for(("dataset_inspection",))
                engine.validate_runtime_token_for_launch(token, ("dataset_inspection",))
                self.update.emit({"status": "Opening point cloud"})
                progress_path = self.run_record.folder / "prepare_progress.json"
                cancel_path = self.run_record.folder / "prepare_cancel"
                with (self.run_record.folder / "prepare_stdout.log").open("w+", encoding="utf-8") as output, \
                     (self.run_record.folder / "prepare_stderr.log").open("w+", encoding="utf-8") as errors:
                    process = subprocess.Popen(
                        [token.executable, "-I", str(viewer_root / "prepare_source.py"), "--source", str(source),
                         "--cache", str(service.root / "source-cache"),
                         "--progress-file", str(progress_path), "--cancel-file", str(cancel_path)],
                        stdout=output, stderr=errors, env=engine.environment(), **hidden_subprocess_kwargs())
                    self.run_record.update(preparation_pid=process.pid,
                        preparation_stdout_path=str(self.run_record.folder / "prepare_stdout.log"),
                        preparation_stderr_path=str(self.run_record.folder / "prepare_stderr.log"))
                    started = time.monotonic()
                    last_progress = 0
                    while process.poll() is None:
                        if self.stop_event.wait(.1) or time.monotonic() - started > 86400:
                            cancel_path.touch()
                            try:
                                process.wait(timeout=15)
                            except subprocess.TimeoutExpired:
                                from ..core.owned_workers import terminate_process_tree
                                terminate_process_tree(process)
                                process.wait()
                            raise RuntimeError("Viewer source preparation cancelled or timed out.")
                        if time.monotonic() - last_progress >= 1:
                            last_progress = time.monotonic()
                            try:
                                with progress_path.open(encoding="utf-8") as progress_stream:
                                    progress = json.loads(progress_stream.read(16000))
                                elapsed = int(progress.get("elapsed_seconds", 0))
                                self.update.emit({"status": f"{progress['stage']} ({elapsed}s)",
                                                  "preparation_progress": progress})
                            except (OSError, ValueError, KeyError):
                                pass
                    output.seek(0)
                    lines = output.read(16000).splitlines()
                    if process.returncode:
                        errors.seek(0)
                        detail = errors.read(4000).strip()
                        raise RuntimeError("Could not prepare an interactive view. " +
                                           (detail or "See preparation logs in Viewer Diagnostics."))
                    prepared = json.loads(lines[-1])
                    if prepared.get("cache_fingerprint"):
                        from ..core.point_cloud.view_cache import ViewCache
                        lease = ViewCache(service.root / "source-cache").lease(prepared["cache_fingerprint"])
                        lease.__enter__()
                        cache_lease = lease
                    self.run_record.update(source_fingerprint=prepared["sha256"],
                        view_strategy=prepared.get("strategy"),
                        cache_fingerprint=prepared.get("cache_fingerprint"),
                        preparation_seconds=prepared.get("preparation_seconds"))
                    source = Path(prepared["render_source"])
                    self.update.emit({"source_info": prepared})
            if self.stop_event.is_set():
                return
            if source.name.lower() == "ept.json":
                with source.open(encoding="utf-8", newline="") as stream:
                    raw = stream.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise RuntimeError("EPT metadata exceeds the viewer limit.")
                metadata = json.loads(raw)
                if metadata.get("dataType") not in ("laszip", "binary"):
                    raise RuntimeError("Viewer currently supports LASzip/binary EPT; this EPT encoding is not yet packaged.")
                import hashlib
                self.update.emit({"source_info": {"point_count": metadata.get("points"), "metadata": metadata,
                    "source_identity":{"path":str(source),"sha256":hashlib.sha256(raw.encode("utf-8")).hexdigest(),"source_type":"EPT"}}})
            service.root.mkdir(parents=True, exist_ok=True)
            with (self.run_record.folder / "stderr.log").open("a", encoding="utf-8") as log:
                process = subprocess.Popen(
                    [str(executable), "-I", str(viewer_root / "host.py"), "--parent", str(self.parent_handle),
                     "--source", str(source), "--run-dir", str(self.run_record.folder)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                    text=True, encoding="utf-8", env=viewer_environment(executable), **hidden_subprocess_kwargs())
                self.run_record.stage("VIEWER_PROCESS_CREATED", viewer_pid=process.pid)
                received = queue.Queue(maxsize=4)

                def read():
                    with (self.run_record.folder / "stdout.log").open("a", encoding="utf-8") as stdout:
                        for line in iter(lambda: process.stdout.readline(65537), ""):
                            stdout.write(line)
                            stdout.flush()
                            if len(line) > 65536:
                                return
                            try:
                                value = json.loads(line)
                                self.run_record.observe(value)
                                received.put_nowait(value)
                            except (queue.Full, ValueError):
                                pass

                reader = threading.Thread(target=read, daemon=True)
                reader.start()
                launched_at = time.monotonic()
                stopping_at = None
                self.update.emit({"status": "Opening point cloud"})
                while process.poll() is None:
                    if (time.monotonic() - launched_at > 120 and
                            self.run_record.data.get("first_frame_status") != "NONBLANK_WEBGL_CAPTURE" and
                            not self.run_record.data.get("render_stats", {}).get("displayed")):
                        raise TimeoutError("Could not open source within two minutes. Reload Viewer or inspect diagnostics.")
                    if self.stop_event.is_set() and stopping_at is None:
                        self.run_record.shutdown(self.shutdown_origin)
                        process.stdin.write('{"action":"close"}\n')
                        process.stdin.flush()
                        stopping_at = time.monotonic()
                    if stopping_at is not None and time.monotonic() - stopping_at > 5:
                        process.kill()
                        break
                    try:
                        command = self.commands.get(timeout=.05)
                        process.stdin.write(json.dumps(command, allow_nan=False) + "\n")
                        process.stdin.flush()
                    except queue.Empty:
                        pass
                    try:
                        self.update.emit(received.get_nowait())
                    except queue.Empty:
                        pass
                process.wait()
                reader.join(timeout=1)
                if not self.stop_event.is_set():
                    self.update.emit({"error": "Viewer disconnected. Reload Viewer."})
        except Exception as error:
            failure = error
            if not self.stop_event.is_set():
                self.update.emit({"error": str(error)})
        finally:
            try:
                if process is not None:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
                    for stream in (process.stdin, process.stdout):
                        if stream:
                            stream.close()
            except Exception as error:
                failure = failure or error
            finally:
                try:
                    if self.run_record is not None:
                        if self.stop_event.is_set() and not self.run_record.data["shutdown_requested"]:
                            self.run_record.shutdown(self.shutdown_origin)
                        self.run_record.finish(process.returncode if process is not None else (1 if failure else 0), failure)
                finally:
                    try:
                        if cache_lease is not None:
                            cache_lease.__exit__(None, None, None)
                    finally:
                        self.stopped_event.set()


class ViewerSessionWorker(QThread):
    completed = pyqtSignal(object)

    def __init__(self, operation, path, *, source="", state=None, existing=None, source_crs="", cache_identity=None):
        super().__init__()
        self.operation, self.path = operation, path
        self.source, self.state, self.existing = source, state, existing
        self.source_crs, self.cache_identity = source_crs, cache_identity
        self.cancelled = threading.Event()
        self.stopped_event = threading.Event()

    def run(self):
        from ..core.point_cloud.view_session import load_view_session, save_view_session, ViewerSourceChanged
        try:
            if self.operation == "load":
                session = load_view_session(self.path, cancelled=self.cancelled.is_set)
            else:
                session = save_view_session(self.path, self.source, self.state, existing=self.existing,
                                            source_crs=self.source_crs, cache_identity=self.cache_identity,
                                            cancelled=self.cancelled.is_set)
            if not self.cancelled.is_set():
                self.completed.emit({"session": session, "operation": self.operation, "path": self.path})
        except ViewerSourceChanged as error:
            self.completed.emit({"error": str(error), "source_changed": error.source, "operation": self.operation})
        except Exception as error:
            if not self.cancelled.is_set():
                self.completed.emit({"error": str(error), "operation": self.operation})
        finally:
            self.stopped_event.set()


class ViewerSurface(QWidget):
    resized = pyqtSignal(int, int)
    visibility = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(qt_enum(Qt, "WA_NativeWindow", "WidgetAttribute"))
        self.setMinimumSize(180, 180)
        self.setSizePolicy(qt_enum(QSizePolicy, "Expanding", "Policy"), qt_enum(QSizePolicy, "Expanding", "Policy"))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit(self.width(), self.height())

    def showEvent(self, event):
        super().showEvent(event)
        self.visibility.emit(True)

    def hideEvent(self, event):
        self.visibility.emit(False)
        super().hideEvent(event)


class PointCloudPage(QWidget):
    """Compact experimental surface; missing viewer never disables Process."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self._pending_source = None
        self._pending_render_only = False
        self._render_only = False
        self._filter_bounds_initialized = False
        self._session_worker = None
        self._edit_session = None
        self._session_to_open = None
        self._restore_after_open = None
        self._restore_expected = None
        self._pending_save = None
        self._view_state = None
        self._source_info = {}
        self._closing = False
        self.last_run_folder = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)
        source_row = QHBoxLayout()
        self.source = QLineEdit()
        self.source.setReadOnly(True)
        self.source.setPlaceholderText("Point cloud source")
        self.open_button = QPushButton("Open")
        self.open_button.clicked.connect(self.open_source)
        self.open_button.setToolTip("Open a local LAS, LAZ, COPC or EPT source without modifying its points.")
        self.source.setToolTip("Original point cloud path. Small sources open directly; larger raw sources use a managed, read-only viewing cache.")
        source_row.addWidget(self.source, 1)
        source_row.addWidget(self.open_button)
        layout.addLayout(source_row)
        toolbar = QHBoxLayout()
        self.view_buttons = []
        for label, action in (("Fit", "fit"), ("Top", "top"), ("Front", "front")):
            button = QToolButton()
            button.setText(label)
            button.setFixedWidth(42)
            button.setToolTip({"fit": "Fit the selected source in view.", "top": "Look down along source Z.", "front": "Look along source Y."}[action])
            button.clicked.connect(lambda _checked=False, value=action: self.send({"action": value}))
            toolbar.addWidget(button)
            self.view_buttons.append(button)
        self.mode = QComboBox()
        self.mode.addItems(("Classification", "Elevation", "RGB", "Intensity"))
        self.mode.setToolTip("RGB uses stored Red, Green and Blue attributes. Missing, zero or constant colors are diagnosed separately from rendering failures. Display modes never alter source attributes.")
        self.mode.currentTextChanged.connect(lambda value: self.send({"action": "mode", "mode": value}))
        layout.addLayout(toolbar)
        self.navigation_mode = QComboBox()
        self.navigation_mode.addItems(("Orbit", "Pan"))
        self.navigation_mode.setToolTip("Orbit turns around the cloud. Pan moves over a picked source surface without rotating it.")
        self.navigation_mode.currentTextChanged.connect(lambda value: self.send({"action": "navigation", "mode": value}))
        toolbar.addWidget(self.navigation_mode, 1)
        display_row = QHBoxLayout()
        display_row.addWidget(self.mode, 1)
        from .point_cloud_appearance import PointAppearance
        self.appearance = PointAppearance(self.send, self)
        display_row.addWidget(self.appearance)
        layout.addLayout(display_row)
        self.filter_toggle = QToolButton()
        self.filter_toggle.setText("Display filters")
        self.filter_toggle.setCheckable(True)
        self.filter_toggle.setToolButtonStyle(qt_enum(Qt, "ToolButtonTextBesideIcon", "ToolButtonStyle"))
        self.filter_toggle.setArrowType(qt_enum(Qt, "RightArrow", "ArrowType"))
        self.filter_toggle.setToolTip("Display-only class and source-Z filters; no source attributes or journal entries change.")
        layout.addWidget(self.filter_toggle)
        self.filters_panel = QDialog(self, qt_enum(Qt, "Tool", "WindowType"))
        self.filters_panel.setWindowTitle("Point Cloud display filters")
        self.filters_panel.setModal(False)
        self.filters_panel.finished.connect(lambda _result: self.filter_toggle.setChecked(False))
        form = QFormLayout(self.filters_panel)
        form.setContentsMargins(10, 10, 10, 10)
        self.quality = QComboBox()
        self.quality.addItems(("Automatic", "Performance", "Balanced", "High Detail"))
        self.quality.setToolTip("Automatic adapts display detail to measured frame time without dropping below the structural point floor. Presets affect viewing only.")
        self.quality.currentTextChanged.connect(lambda value: self.send({"action": "quality", "quality": value}))
        form.addRow("Quality", self.quality)
        self.class_list = QListWidget()
        self.class_list.setMaximumHeight(100)
        self.class_list.setToolTip("Classes observed in streamed points. More may appear as the view refines. Check a class to show it; this never edits the source.")
        self.class_list.itemChanged.connect(self.apply_class_visibility)
        form.addRow("Observed classes", self.class_list)
        class_actions = QHBoxLayout()
        self.solo_class_button = QPushButton("Solo Class")
        self.solo_class_button.setToolTip("Display only the selected observed class. This does not change classification values.")
        self.solo_class_button.clicked.connect(self.solo_class)
        self.show_classes_button = QPushButton("Show All Classes")
        self.show_classes_button.setToolTip("Show all classification values, including classes not yet encountered in streamed nodes.")
        self.show_classes_button.clicked.connect(self.show_all_classes)
        class_actions.addWidget(self.solo_class_button)
        class_actions.addWidget(self.show_classes_button)
        form.addRow(class_actions)
        self.height_enabled = QCheckBox("Source Z range")
        self.height_enabled.setToolTip("Clip the displayed cloud in source Z units. This is not Height Above Ground normalization.")
        form.addRow(self.height_enabled)
        self.height_min = QDoubleSpinBox()
        self.height_max = QDoubleSpinBox()
        for spin in (self.height_min, self.height_max):
            spin.setRange(-1e9, 1e9)
            spin.setDecimals(3)
        self.height_max.setValue(10000)
        self.height_min.setToolTip("Lowest visible source Z coordinate. Display-only; not a normalization or edit.")
        self.height_max.setToolTip("Highest visible source Z coordinate. Display-only; not a normalization or edit.")
        form.addRow("Minimum", self.height_min)
        form.addRow("Maximum", self.height_max)
        self.apply_filters_button = QPushButton("Apply Filters")
        self.apply_filters_button.setToolTip("Apply the display-only Z interval without changing source points or the edit journal.")
        self.apply_filters_button.clicked.connect(self.apply_filters)
        self.clear_filters_button = QPushButton("Clear Filters")
        self.clear_filters_button.setToolTip("Show all source Z values and classifications again. No source file is modified.")
        self.clear_filters_button.clicked.connect(self.clear_filters)
        filter_actions = QHBoxLayout()
        filter_actions.addWidget(self.apply_filters_button)
        filter_actions.addWidget(self.clear_filters_button)
        form.addRow(filter_actions)
        self.filters_panel.setVisible(False)
        self.filter_toggle.toggled.connect(self._toggle_filters)
        self.surface = ViewerSurface(self)
        from ..core.point_cloud.workspace import PointCloudWorkspaceModel
        self.workspace = PointCloudWorkspaceModel()
        self.overview_id = self.workspace.register(view_id="overview")
        from .point_cloud_detached import LinkedTabBar
        self.view_tabs = LinkedTabBar(self)
        self.view_tabs.setExpanding(False)
        self.view_tabs.setMovable(True)
        self.view_tabs.setTabsClosable(True)
        layout.addWidget(self.view_tabs)
        layout.addWidget(self.surface, 1)
        from .point_cloud_widgets import StableViewerStatus
        self.status = StableViewerStatus("Open a source. Viewer setup is separate from scientific processing.")
        layout.addWidget(self.status)
        self.details = StableViewerStatus("Quality: Automatic | Selection: None")
        layout.addWidget(self.details)
        actions = QHBoxLayout()
        self.reload_button = QPushButton("Reload Viewer")
        self.reload_button.clicked.connect(lambda: self.start_source(self.source.text()))
        self.reload_button.setToolTip("Restart the isolated viewer for the current source. Scientific processing is unaffected.")
        self.setup_button = QPushButton("Set Up Viewer")
        self.setup_button.clicked.connect(self.setup_viewer)
        self.setup_button.setToolTip("Install or repair the optional, user-local graphics runtime. QGIS Python and scientific packages stay separate.")
        actions.addWidget(self.reload_button)
        actions.addWidget(self.setup_button)
        layout.addLayout(actions)
        session_actions = QHBoxLayout()
        self.session_status = QLabel("Session: Not saved")
        self.session_status.setWordWrap(True)
        session_actions.addWidget(self.session_status, 1)
        self.save_session_button = QToolButton()
        self.save_session_button.setIcon(self.style().standardIcon(qt_enum(QStyle, "SP_DialogSaveButton", "StandardPixmap")))
        self.save_session_button.setAccessibleName("Save Session")
        self.save_session_button.setToolTip("Save camera and display filters with a verified source fingerprint. The original source and existing edit journal are preserved.")
        self.save_session_button.clicked.connect(self.save_session)
        self.load_session_button = QToolButton()
        self.load_session_button.setIcon(self.style().standardIcon(qt_enum(QStyle, "SP_DialogOpenButton", "StandardPixmap")))
        self.load_session_button.setAccessibleName("Open Session")
        self.load_session_button.setToolTip("Verify the saved source before restoring camera, colors and display filters. Changed sources are not replayed automatically.")
        self.load_session_button.clicked.connect(self.open_session)
        self.diagnostics_button = QToolButton()
        self.diagnostics_button.setIcon(self.style().standardIcon(qt_enum(QStyle, "SP_FileDialogDetailedView", "StandardPixmap")))
        self.diagnostics_button.setAccessibleName("Viewer Diagnostics")
        self.diagnostics_button.setToolTip("Open this viewer attempt's lifecycle record, retained output and screenshot evidence.")
        self.diagnostics_button.clicked.connect(self.open_diagnostics)
        session_actions.addWidget(self.save_session_button)
        session_actions.addWidget(self.load_session_button)
        session_actions.addWidget(self.diagnostics_button)
        layout.addLayout(session_actions)
        from .point_cloud_editor import EditorPanel
        self.editor = EditorPanel(self)
        self.workspace.bind_editor(self.editor.send)
        from .point_cloud_linked_views import LinkedViews
        self.linked = LinkedViews(self, toolbar)
        layout.addWidget(self.editor)
        from .point_cloud_widgets import StableViewerHelp
        self.filter_help = StableViewerHelp(self.filters_panel)
        form.addRow(self.filter_help)
        for control, name in ((self.quality, "Viewing quality"),
                              (self.class_list, "Visible classifications"),
                              (self.height_min, "Minimum source Z"),
                              (self.height_max, "Maximum source Z")):
            control.setAccessibleName(name)
        self.context_help = StableViewerHelp(self)
        layout.addWidget(self.context_help)
        for control in self.findChildren(QWidget):
            if control.toolTip():
                control.installEventFilter(self)
        self._controls(False)

    def eventFilter(self, watched, event):
        if event.type() in (qt_enum(QEvent, "Enter", "Type"), qt_enum(QEvent, "FocusIn", "Type")):
            banner = self.filter_help if self.filters_panel.isAncestorOf(watched) else self.context_help
            banner.set_help(watched.toolTip())
        return super().eventFilter(watched, event)

    def _toggle_filters(self, opened):
        self.filters_panel.setVisible(opened)
        if opened:
            self.filters_panel.adjustSize()
            self.filters_panel.raise_()
            self.quality.setFocus()
        elif not self._closing:
            self.filter_toggle.setFocus()
        self.filter_toggle.setArrowType(qt_enum(Qt, "DownArrow" if opened else "RightArrow", "ArrowType"))

    def open_diagnostics(self):
        if self.last_run_folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_run_folder))

    def save_session(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save point cloud session", "", "Point cloud session (*.json)")
        if path:
            self.save_session_to(path)

    def save_session_to(self, path):
        if self.editor.worker:
            self.editor.save_to(path)
            return
        if not self.worker or not self._view_state or self._session_worker:
            return
        if self.source.text().lower().endswith("ept.json"):
            self.status.setText("EPT tree fingerprinting is not yet available for portable sessions.")
            return
        from uuid import uuid4
        request = uuid4().hex
        self._pending_save = (request, path)
        self.session_status.setText("Session: Saving")
        self.save_session_button.setEnabled(False)
        self.send({"action": "snapshot", "request_id": request})

    def open_session(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open point cloud session", "", "Point cloud session (*.json)")
        if path:
            self.load_session_from(path)

    def load_session_from(self, path):
        self.editor.load(path)
        return

    def _load_view_only_session_from(self, path):
        if self._session_worker is None:
            self._start_session_worker(ViewerSessionWorker("load", path))

    def _start_session_worker(self, worker):
        self._session_worker = worker
        self.status.setText("Verifying source and session")
        for button in (self.save_session_button, self.load_session_button, self.open_button, self.reload_button):
            button.setEnabled(False)
        worker.completed.connect(self._session_completed)
        worker.finished.connect(self._session_finished)
        _ACTIVE_WORKERS.add(worker)
        worker.finished.connect(lambda: _ACTIVE_WORKERS.discard(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _session_completed(self, result):
        if self._closing:
            return
        if result.get("source_changed"):
            self.session_status.setText("Session: Source changed")
            self.status.setText(result["error"])
            dialog = QMessageBox(self)
            dialog.setWindowTitle("Source changed")
            dialog.setText(result["error"])
            reopen = dialog.addButton("Reopen Without Edits", qt_enum(QMessageBox, "AcceptRole", "ButtonRole"))
            choose = dialog.addButton("Choose Source", qt_enum(QMessageBox, "ActionRole", "ButtonRole"))
            dialog.addButton("Discard Session", qt_enum(QMessageBox, "RejectRole", "ButtonRole"))
            dialog.exec() if hasattr(dialog, "exec") else dialog.exec_()
            if dialog.clickedButton() is reopen:
                self.source.setText(result["source_changed"])
                self.start_source(result["source_changed"])
            elif dialog.clickedButton() is choose:
                self.open_source()
            return
        if result.get("error"):
            self.session_status.setText("Session: Needs attention")
            self.status.setText(result["error"])
            return
        self._edit_session = result["session"]
        if result["operation"] == "load":
            self.session_status.setText("Session: Restoring")
            self._session_to_open = result["session"]
            self.source.setText(self._session_to_open.source.path)
            self.start_source(self._session_to_open.source.path)
        else:
            self.session_status.setText("Session: Saved")
            self.status.setText("Session saved | Original unchanged")

    def _session_finished(self):
        self._session_worker = None
        if not self._closing:
            self.load_session_button.setEnabled(True)
            self.save_session_button.setEnabled(self._view_state is not None)
            self.open_button.setEnabled(True)
            self.reload_button.setEnabled(True)

    def apply_filters(self):
        if self.height_enabled.isChecked() and self.height_min.value() >= self.height_max.value():
            self.status.setText("Height minimum must be below maximum.")
            return
        self.send({"action": "clear_height"})
        if self.height_enabled.isChecked():
            self.send({"action": "height", "minimum": self.height_min.value(), "maximum": self.height_max.value()})

    def clear_filters(self):
        self._sync_classes(None)
        self.height_enabled.setChecked(False)
        self.send({"action": "clear_filters"})

    def _sync_classes(self, visible):
        self.class_list.blockSignals(True)
        for index in range(self.class_list.count()):
            item = self.class_list.item(index)
            code = item.data(qt_enum(Qt, "UserRole", "ItemDataRole"))
            item.setCheckState(qt_enum(Qt, "Checked" if visible is None or code in visible else "Unchecked", "CheckState"))
        self.class_list.blockSignals(False)

    def _observe_classes(self, codes, visible):
        known = {self.class_list.item(i).data(qt_enum(Qt, "UserRole", "ItemDataRole")) for i in range(self.class_list.count())}
        self.class_list.blockSignals(True)
        for code in sorted(set(codes) - known):
            if type(code) is not int or not 0 <= code <= 255:
                continue
            item = QListWidgetItem(f"Class {code}")
            item.setData(qt_enum(Qt, "UserRole", "ItemDataRole"), code)
            item.setFlags(item.flags() | qt_enum(Qt, "ItemIsUserCheckable", "ItemFlag"))
            item.setCheckState(qt_enum(Qt, "Checked" if visible is None or code in visible else "Unchecked", "CheckState"))
            self.class_list.addItem(item)
        self.class_list.blockSignals(False)

    def apply_class_visibility(self):
        from ..core.point_cloud.view_filters import visible_classes_after_changes
        changes = {}
        for index in range(self.class_list.count()):
            item = self.class_list.item(index)
            code = item.data(qt_enum(Qt, "UserRole", "ItemDataRole"))
            changes[code] = item.checkState() == qt_enum(Qt, "Checked", "CheckState")
        visible = visible_classes_after_changes((self._view_state or {}).get("classes"), changes)
        self.send({"action": "classes", "classes": visible})

    def solo_class(self):
        item = self.class_list.currentItem()
        if item is not None:
            classes = [item.data(qt_enum(Qt, "UserRole", "ItemDataRole"))]
            self._sync_classes(classes)
            self.send({"action": "classes", "classes": classes})

    def show_all_classes(self):
        self._sync_classes(None)
        self.send({"action": "classes", "classes": list(range(256))})

    def _controls(self, ready):
        for button in self.view_buttons:
            button.setEnabled(ready)
        self.mode.setEnabled(ready)
        self.appearance.setEnabled(ready)
        self.navigation_mode.setEnabled(ready)
        self.apply_filters_button.setEnabled(ready)
        self.clear_filters_button.setEnabled(ready)
        self.class_list.setEnabled(ready)
        self.solo_class_button.setEnabled(ready)
        self.show_classes_button.setEnabled(ready)
        self.save_session_button.setEnabled(ready and self._session_worker is None and self._pending_save is None)
        if hasattr(self,"linked") and self.linked.active().view_type == "VERTICAL_SLICE":
            self.navigation_mode.setEnabled(False)
            for button in self.view_buttons[1:]:
                button.setEnabled(False)

    def send(self, command):
        if self.worker:
            self.worker.send(command)

    def _start(self, worker):
        if self.worker is not None:
            self.status.setText("Close the current viewer before starting another operation.")
            return
        self.worker = worker
        self.linked.residents.started()
        from .point_cloud_resident_views import bind_surface
        bind_surface(worker, self.surface)
        self.open_button.setEnabled(False)
        self.reload_button.setEnabled(False)
        self.setup_button.setEnabled(False)
        worker.update.connect(self._update)
        worker.finished.connect(self._finished)
        _ACTIVE_WORKERS.add(worker)
        worker.finished.connect(lambda: _ACTIVE_WORKERS.discard(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def open_source(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open point cloud", "", "Point clouds (*.las *.laz ept.json)")
        if path:
            self.source.setText(path)
            self.start_source(path)

    def start_source(self, path, *, render_only=False):
        if not path.strip():
            self.status.setText("Select a LAS, LAZ, COPC or local EPT source.")
            return
        if not render_only:
            self.linked.set_depth({}, persist=False)
            self.linked.residents.clear()
        if self.worker is not None:
            self._pending_source = path
            self._pending_render_only = render_only
            self.editor.observe({})
            self._controls(False)
            self.worker.stop()
            self.status.setText("Closing previous viewer")
            return
        self._controls(False)
        self._render_only = render_only
        self.linked.context_sent = False
        if not render_only:
            self.linked.request_id = None
            self.linked.waiting = False
            self.linked.rendered_id = self.overview_id
            self.workspace.activate(self.overview_id)
            self.linked.sync_tabs()
        self._filter_bounds_initialized = False
        self._view_state = None
        self._pending_save = None
        self._source_info = {}
        self.class_list.clear()
        self._edit_session = self._session_to_open
        self._restore_expected = None
        for combo, value in ((self.mode, "Classification"), (self.navigation_mode, "Orbit"), (self.quality, "Automatic")):
            combo.blockSignals(True)
            combo.setCurrentText(value)
            combo.blockSignals(False)
        self._session_to_open = None
        if self._edit_session:
            from ..core.point_cloud.view_session import session_view_state
            self._restore_after_open = session_view_state(self._edit_session)
        else:
            self._restore_after_open = None
            self.session_status.setText("Session: Not saved")
        self.clear_filters()
        self._start(ViewerWorker(source=path, parent_handle=int(self.surface.winId())))
        if not render_only:
            self.editor.attach(path)
        if self.editor.restored_view:
            self._restore_after_open = self.editor.restored_view
            self.editor.restored_view = None

    def setup_viewer(self):
        answer = QMessageBox.question(self, "Set up optional viewer",
            "Download the isolated viewer runtime into your user-local PyForestScan folder? "
            "QGIS Python and the scientific Processing Engine will not be modified.")
        if answer == qt_enum(QMessageBox, "Yes", "StandardButton"):
            self._start(ViewerWorker(setup=True))

    def _update(self, value):
        if self._closing or self._pending_source:
            return
        if value.get("diagnostics_path"):
            self.last_run_folder = value["diagnostics_path"]
        if value.get("source_info"):
            self._source_info = value["source_info"]
            if not self._render_only:
                self.linked.original_info = value["source_info"]
        if value.get("started"):
            self.open_button.setEnabled(True)
            self.reload_button.setEnabled(True)
            self.send({"action": "resize", "width": self.surface.width(), "height": self.surface.height()})
        if value.get("status"):
            self.status.setText(value["status"])
        if value.get("error"):
            self.status.setText(value["error"])
            self._controls(False)
        telemetry = value.get("telemetry", {})
        if telemetry.get("ready"):
            self._view_state = telemetry
            self.appearance.sync(telemetry)
            self.linked.observe(telemetry)
            self.editor.observe(telemetry)
            self.linked.coordinate_resources()
            self._observe_classes(telemetry.get("observed_classes", []), telemetry.get("classes"))
            self._controls(True)
            if self._session_worker is None:
                self.status.setText("Source open | Original unchanged")
                if telemetry.get("mode") == "RGB" and telemetry.get("rgb_diagnostic", {}).get("message"):
                    self.status.setText(telemetry["rgb_diagnostic"]["message"])
            displayed = telemetry.get('render_diagnostics', {}).get('rendered_points', telemetry.get('displayed', 0))
            self.details.setText(f"View points (before filters): {displayed:,} | {telemetry.get('quality', 'Automatic')} | {telemetry.get('detail', 'Refining')}")
            if telemetry.get('context_lost'):
                self.status.setText("Viewer graphics context was reset. Restoring view...")
            if not self._filter_bounds_initialized and telemetry.get("z_range"):
                self.height_min.setValue(telemetry["z_range"][0])
                self.height_max.setValue(telemetry["z_range"][1])
                self._filter_bounds_initialized = True
            if self._restore_after_open:
                restored, self._restore_after_open = self._restore_after_open, None
                if not restored.get("camera"):
                    restored = dict(restored, camera=telemetry["camera"])
                self._restore_expected = restored
                self.send({"action": "camera", "camera": restored["camera"]})
                self.quality.setCurrentText(restored.get("quality", "Automatic"))
                self.send({"action": "quality", "quality": restored.get("quality", "Automatic")})
                self.mode.setCurrentText(restored["mode"])
                self.send({"action": "mode", "mode": restored["mode"]})
                self.send({"action": "clear_filters"})
                self._sync_classes(restored["classes"])
                if restored["classes"] is not None:
                    self.send({"action": "classes", "classes": restored["classes"]})
                if restored["height_filter"] is not None:
                    low, high = restored["height_filter"]
                    self.height_enabled.setChecked(True)
                    self.height_min.setValue(low)
                    self.height_max.setValue(high)
                    self.send({"action": "height", "minimum": low, "maximum": high})
            if self._restore_expected is not None:
                from ..core.point_cloud.view_session import view_state_matches
                if view_state_matches(telemetry, self._restore_expected):
                    self._restore_expected = None
                    self.session_status.setText("Session: Restored")
                    self.send({"action": "session_ready"})
            if self._pending_save and telemetry.get("request_id") == self._pending_save[0]:
                _, path = self._pending_save
                self._pending_save = None
                self._start_session_worker(ViewerSessionWorker("save", path, source=self.source.text(),
                    state=telemetry, existing=self._edit_session,
                    cache_identity={key: self._source_info[key] for key in ("render_source", "sha256", "strategy", "cache_fingerprint") if key in self._source_info}))
        if telemetry.get("errors"):
            self.status.setText("Point Cloud viewer needs attention. Reload Viewer; details are in diagnostics.")
            self._view_state = None
            self._controls(False)

    def _finished(self):
        self.worker = None
        self.editor.observe({})
        self._view_state = None
        self._pending_save = None
        self._controls(False)
        if not self._closing:
            self.open_button.setEnabled(True)
            self.reload_button.setEnabled(True)
            self.setup_button.setEnabled(True)
            if self._pending_source:
                path, self._pending_source = self._pending_source, None
                self.start_source(path, render_only=self._pending_render_only)

    def prepare_for_unload(self):
        self._closing = True
        self.linked.close()
        self.filters_panel.close()
        self.editor.close_editor()
        if self._session_worker:
            self._session_worker.cancelled.set()
            try:
                self._session_worker.completed.disconnect(self._session_completed)
                self._session_worker.finished.disconnect(self._session_finished)
            except (TypeError, RuntimeError):
                pass
            self._session_worker = None
        if self.worker:
            try:
                self.worker.update.disconnect(self._update)
                self.worker.finished.disconnect(self._finished)
            except (TypeError, RuntimeError):
                pass
            self.worker.stop("plugin_unload")
            self.worker = None
