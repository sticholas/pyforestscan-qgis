"""Optional isolated viewer page; scientific imports remain in managed workers."""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import queue
from collections import deque
import subprocess
import threading
import time

from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal, QEvent
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices, QColor, QImage, QIcon, QPixmap
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QInputDialog,
    QComboBox, QFileDialog, QMessageBox, QSizePolicy,
    QToolButton, QCheckBox, QDoubleSpinBox, QFormLayout,
    QStyle, QListWidget, QListWidgetItem, QDialog, QTabWidget, QTabBar, QMenu,
)
from ..compat.qt import qt_enum
from ..core.backend.process_env import hidden_subprocess_kwargs
from ..core.point_cloud.runtime import ViewerRuntimeService, viewer_environment
from ..core.point_cloud.run_record import ViewerRunRecord
from ..core.point_cloud.display_stability import DisplayTelemetryStabilizer
from .point_cloud_display_range import DisplayRangeControls
from ..core.point_cloud.scientific_overlay import ScientificOverlayPayload, overlay_value_range

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
        # Display controls can generate bursts while the renderer is loading.
        # Keep enough room for normal interaction, and coalesce palette changes
        # rather than silently dropping the user's final choice.
        self.commands = queue.Queue(maxsize=128)
        self.stop_event = threading.Event()
        self.stopped_event = threading.Event()
        self.shutdown_origin = "user_request"
        self.run_record = None

    def send(self, command):
        try:
            self.commands.put_nowait(command)
        except queue.Full:
            if command.get("action") != "palette":
                return
            with self.commands.mutex:
                retained = deque(
                    item for item in self.commands.queue
                    if item.get("action") != "palette"
                )
                removed = len(self.commands.queue) - len(retained)
                self.commands.queue = retained
                self.commands.unfinished_tasks = max(
                    0, self.commands.unfinished_tasks - removed
                )
                try:
                    self.commands.queue.append(command)
                    self.commands.unfinished_tasks += 1
                    self.commands.not_empty.notify()
                except (AttributeError, RuntimeError):
                    return

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
            self.run_record.stage("VIEWER_RUNTIME_RESOLVED")
            source = Path(self.source).resolve(strict=True)
            viewer_root = Path(__file__).resolve().parents[1] / "viewer"
            if source.suffix.lower() in (".las", ".laz") and not source.name.lower().endswith(".copc.laz"):
                self.run_record.stage("SOURCE_PREPARATION_STARTED")
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
                self.run_record.stage("SOURCE_PREPARATION_COMPLETE")
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


class ThinSourceWorker(QThread):
    """Run an explicit non-destructive thinning request in managed PBM Python."""
    update = pyqtSignal(object)

    def __init__(self, request, parent=None):
        super().__init__(parent)
        self.request = request
        self.cancelled = threading.Event()
        self.run_folder = None

    def run(self):
        process = None
        try:
            from ..core.backend.service import BackendService
            from ..core.atomic_state import atomic_write_json
            service = BackendService()
            engine = service.processing_engine_service()
            token = engine.runtime_token_for(("dataset_inspection",))
            engine.validate_runtime_token_for_launch(token, ("dataset_inspection",))
            root = service.paths.backend_root / "viewer" / "thinning-runs"
            root.mkdir(parents=True, exist_ok=True)
            self.run_folder = root / __import__("uuid").uuid4().hex
            self.run_folder.mkdir()
            request_path = self.run_folder / "request.json"
            result_path = self.run_folder / "result.json"
            progress_path = self.run_folder / "progress.json"
            cancel_path = self.run_folder / "cancel"
            atomic_write_json(request_path, self.request)
            script = Path(__file__).resolve().parents[1] / "viewer" / "thin_source.py"
            with (self.run_folder / "stdout.log").open("w+", encoding="utf-8") as stdout, \
                 (self.run_folder / "stderr.log").open("w+", encoding="utf-8") as stderr:
                process = subprocess.Popen(
                    [token.executable, "-I", str(script), "--request", str(request_path),
                     "--result", str(result_path), "--progress-file", str(progress_path),
                     "--cancel-file", str(cancel_path)],
                    stdout=stdout, stderr=stderr, env=engine.environment(),
                    **hidden_subprocess_kwargs())
                while process.poll() is None:
                    if self.cancelled.wait(.15):
                        cancel_path.touch()
                        process.wait(timeout=20)
                        raise InterruptedError("Thinning cancelled.")
                    try:
                        progress = json.loads(progress_path.read_text(encoding="utf-8"))
                        self.update.emit({"progress": progress})
                    except (OSError, ValueError):
                        pass
                if process.returncode:
                    stderr.seek(0)
                    raise RuntimeError(stderr.read(4000).strip() or "Could not create thinned copy.")
            result = json.loads(result_path.read_text(encoding="utf-8"))
            self.update.emit({"complete": result, "run_folder": str(self.run_folder)})
        except Exception as error:
            self.update.emit({"error": str(error), "run_folder": str(self.run_folder or "")})

    def stop(self):
        self.cancelled.set()


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
        self._display_stabilizer = DisplayTelemetryStabilizer()
        self._source_info = {}
        self._scientific_overlay = None
        self._thin_worker = None
        self._thinning_dialog = None
        self._closing = False
        self.last_run_folder = None
        self.setObjectName("pointCloudPage")
        self.setStyleSheet("""
            QWidget#pointCloudPage {
                background: #f6f8fa;
                color: #20313a;
            }
            QWidget#pointCloudPage QLineEdit,
            QWidget#pointCloudPage QComboBox,
            QWidget#pointCloudPage QDoubleSpinBox {
                min-height: 28px;
                border: 1px solid #cbd7dc;
                border-radius: 4px;
                padding: 2px 6px;
                background: #ffffff;
            }
            QWidget#pointCloudPage QLineEdit:focus,
            QWidget#pointCloudPage QComboBox:focus,
            QWidget#pointCloudPage QDoubleSpinBox:focus {
                border: 2px solid #347d8f;
                background: #fbfeff;
            }
            QWidget#pointCloudPage QPushButton[pointCloudRole="primary"] {
                background: #176b7a;
                color: #ffffff;
                border: 1px solid #115963;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: 600;
            }
            QWidget#pointCloudPage QPushButton[pointCloudRole="primary"]:hover {
                background: #105f6d;
            }
            QWidget#pointCloudPage QPushButton[pointCloudRole="secondary"] {
                background: #ffffff;
                color: #1f4f5b;
                border: 1px solid #b9cbd1;
                border-radius: 4px;
                padding: 4px 10px;
            }
            QWidget#pointCloudPage QToolButton[pointCloudControl="true"] {
                min-height: 26px;
                border: 1px solid #cbd7dc;
                border-radius: 4px;
                padding: 3px 6px;
                background: #ffffff;
                color: #244651;
            }
            QWidget#pointCloudPage QToolButton[pointCloudControl="true"]:hover,
            QWidget#pointCloudPage QToolButton[pointCloudControl="true"]:checked {
                background: #e7f2f4;
                border-color: #77a6b1;
            }
            QWidget#pointCloudPage QLabel[pointCloudHint="true"] {
                color: #52656d;
                padding: 2px 5px;
                background: #edf2f4;
                border-radius: 3px;
            }
            QWidget#pointCloudPage QTabBar::tab {
                min-height: 26px;
                padding: 4px 10px;
                margin-right: 2px;
                border: 1px solid #ccd8dc;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                background: #edf1f3;
            }
            QWidget#pointCloudPage QTabBar::tab:selected {
                background: #ffffff;
                color: #145a68;
                font-weight: 600;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)
        source_row = QHBoxLayout()
        self.source = QLineEdit()
        self.source.setReadOnly(True)
        self.source.setPlaceholderText("Point cloud source")
        self.open_button = QPushButton("Open")
        self.open_button.setProperty("pointCloudRole", "primary")
        self.open_button.setIcon(self.style().standardIcon(qt_enum(QStyle, "SP_DialogOpenButton", "StandardPixmap")))
        self.open_button.setAccessibleName("Open point cloud")
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
            button.setProperty("pointCloudControl", True)
            button.setFixedWidth(44)
            button.setToolTip({"fit": "Fit the selected source in view.", "top": "Look down along source Z.", "front": "Look along source Y."}[action])
            button.clicked.connect(lambda _checked=False, value=action: self.send({"action": value}))
            toolbar.addWidget(button)
            self.view_buttons.append(button)
        self.mode = QComboBox()
        self.mode.addItems(("Classification", "Elevation", "RGB", "Intensity"))
        self.mode.setAccessibleName("Color By")
        self.mode.setToolTip("RGB uses stored Red, Green and Blue attributes. Missing, zero or constant colors are diagnosed separately from rendering failures. Display modes never alter source attributes.")
        self.mode.currentTextChanged.connect(lambda value: self.send({"action": "mode", "mode": value}))
        self.palette = QComboBox()
        palette_stops = {
            "Viridis": ((68, 1, 84), (33, 145, 140), (253, 231, 37)),
            "Turbo": ((48, 18, 59), (70, 129, 237), (164, 252, 60), (249, 132, 10), (122, 4, 3)),
            "Terrain": ((31, 77, 41), (107, 158, 61), (212, 194, 107), (245, 237, 199)),
            "Grayscale": ((10, 10, 10), (245, 245, 245)),
            "Heat": ((10, 0, 26), (143, 0, 92), (245, 46, 13), (255, 230, 51)),
            "CoolWarm": ((20, 51, 179), (191, 219, 240), (245, 240, 194), (184, 31, 26)),
            "Forest": ((5, 26, 20), (15, 97, 51), (107, 179, 61), (235, 224, 97)),
        }
        for name, stops in palette_stops.items():
            image = QImage(120, 14, QImage.Format_ARGB32)
            for x in range(image.width()):
                position = x / max(1, image.width() - 1) * (len(stops) - 1)
                index = min(len(stops) - 2, int(position))
                fraction = position - index
                left, right = stops[index], stops[min(index + 1, len(stops) - 1)]
                color = QColor(*[round(left[i] + (right[i] - left[i]) * fraction) for i in range(3)])
                for y in range(image.height()):
                    image.setPixelColor(x, y, color)
            self.palette.addItem(QIcon(QPixmap.fromImage(image)), name)
        self.palette.setIconSize(QPixmap(120, 14).size())
        self.palette.setAccessibleName("Color palette")
        self.palette.setToolTip("Choose a scientific ramp. The swatch shows the low-to-high color direction; the live legend shows the current numeric range. Classification colors remain categorical.")
        self.palette.currentTextChanged.connect(lambda value: self.send({"action": "palette", "palette": value}))
        layout.addLayout(toolbar)
        self.navigation_hint = QLabel("Mouse: drag to orbit | wheel zoom to cursor | middle drag pans")
        self.navigation_hint.setProperty("pointCloudHint", True)
        self.navigation_hint.setToolTip("Navigation stays available without switching tools: left drag orbits, the wheel zooms toward its cursor point, and holding the middle button pans.")
        toolbar.addWidget(self.navigation_hint, 1)
        display_row = QHBoxLayout()
        color_label = QLabel("Color By")
        color_label.setBuddy(self.mode)
        display_row.addWidget(color_label)
        display_row.addWidget(self.mode, 1)
        palette_label = QLabel("Palette")
        palette_label.setBuddy(self.palette)
        display_row.addWidget(palette_label)
        display_row.addWidget(self.palette)
        from .point_cloud_appearance import PointAppearance
        self.appearance = PointAppearance(self._send_point_display, self)
        display_row.addWidget(self.appearance)
        self.display_range = DisplayRangeControls(self.send, self)
        self.overlay_button = QToolButton()
        self.overlay_button.setText("Overlays")
        self.overlay_button.setProperty("pointCloudControl", True)
        self.overlay_button.setAccessibleName("Scientific overlays")
        self.overlay_button.setToolTip("Choose an existing verified product GeoTIFF and display a bounded spatial overlay in the viewer. This never calculates a product or treats it as a point attribute.")
        self.overlay_button.setToolTip("Open cached scientific product overlay actions. Products remain spatial surfaces and are never treated as point attributes.")
        self.overlay_menu = QMenu(self.overlay_button)
        self.load_overlay_action = self.overlay_menu.addAction("Load cached product GeoTIFF...")
        self.load_overlay_action.triggered.connect(self.choose_scientific_overlay)
        self.clear_overlay_action = self.overlay_menu.addAction("Clear current overlay")
        self.clear_overlay_action.triggered.connect(self.clear_scientific_overlay)
        self.clear_overlay_action.setEnabled(False)
        self.overlay_button.setMenu(self.overlay_menu)
        self.overlay_button.setPopupMode(qt_enum(QToolButton, "InstantPopup", "ToolButtonPopupMode"))
        self.prepare_button = QToolButton()
        self.prepare_button.setText("Prepare")
        self.prepare_button.setProperty("pointCloudControl", True)
        self.prepare_button.setAccessibleName("Prepare point-cloud copy")
        self.prepare_button.setToolTip("Create a non-destructive thinned LAS/LAZ copy in the managed Processing Engine. The open source and Process workflow remain unchanged.")
        self.prepare_menu = QMenu(self.prepare_button)
        self.thin_source_action = self.prepare_menu.addAction("Create Thinned Copy...")
        self.thin_source_action.triggered.connect(self.open_thinning_dialog)
        self.prepare_button.setMenu(self.prepare_menu)
        self.prepare_button.setPopupMode(qt_enum(QToolButton, "InstantPopup", "ToolButtonPopupMode"))
        display_row.addWidget(self.display_range)
        display_row.addWidget(self.overlay_button)
        display_row.addWidget(self.prepare_button)
        layout.addLayout(display_row)
        self.filter_toggle = QToolButton()
        self.filter_toggle.setText("Display filters")
        self.filter_toggle.setProperty("pointCloudControl", True)
        self.filter_toggle.setAccessibleName("Display filters")
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
        self.class_list.setToolTip("Source and staged classes observed in resident view points. Approximate counts refine with the view. Check a class to show it; this never edits the source.")
        self.class_list.itemChanged.connect(self.apply_class_visibility)
        form.addRow("Observed classes", self.class_list)
        class_actions = QHBoxLayout()
        self.solo_class_button = QPushButton("Isolate Class")
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
        self.reload_button.setProperty("pointCloudRole", "secondary")
        self.reload_button.setIcon(self.style().standardIcon(qt_enum(QStyle, "SP_BrowserReload", "StandardPixmap")))
        self.reload_button.clicked.connect(lambda: self.start_source(self.source.text()))
        self.reload_button.setToolTip("Restart the isolated viewer for the current source. Scientific processing is unaffected.")
        self.setup_button = QPushButton("Set Up Viewer")
        self.setup_button.setProperty("pointCloudRole", "secondary")
        self.setup_button.setIcon(self.style().standardIcon(qt_enum(QStyle, "SP_DriveHDIcon", "StandardPixmap")))
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
        self.save_session_button.setProperty("pointCloudControl", True)
        self.save_session_button.setIcon(self.style().standardIcon(qt_enum(QStyle, "SP_DialogSaveButton", "StandardPixmap")))
        self.save_session_button.setAccessibleName("Save Session")
        self.save_session_button.setToolTip("Save camera and display filters with a verified source fingerprint. The original source and existing edit journal are preserved.")
        self.save_session_button.clicked.connect(self.save_session)
        self.load_session_button = QToolButton()
        self.load_session_button.setProperty("pointCloudControl", True)
        self.load_session_button.setIcon(self.style().standardIcon(qt_enum(QStyle, "SP_DialogOpenButton", "StandardPixmap")))
        self.load_session_button.setAccessibleName("Open Session")
        self.load_session_button.setToolTip("Verify the saved source before restoring camera, colors and display filters. Changed sources are not replayed automatically.")
        self.load_session_button.clicked.connect(self.open_session)
        self.diagnostics_button = QToolButton()
        self.diagnostics_button.setProperty("pointCloudControl", True)
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
        for control in tuple(self.view_buttons) + (
                self.overlay_button, self.prepare_button, self.filter_toggle, self.save_session_button,
                self.load_session_button, self.diagnostics_button):
            control.setProperty("pointCloudControl", True)
        self._controls(False)

    def eventFilter(self, watched, event):
        if event.type() in (qt_enum(QEvent, "Enter", "Type"), qt_enum(QEvent, "FocusIn", "Type")):
            if self.filters_panel.isAncestorOf(watched):
                banner = self.filter_help
            elif getattr(self, "_thinning_dialog", None) and self._thinning_dialog.isAncestorOf(watched):
                banner = getattr(self, "_thinning_help", self.context_help)
            else:
                banner = self.context_help
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

    def _thinning_unit_assessment(self):
        """Resolve only documented CRS unit evidence; never infer units from magnitude."""
        from ..core.source_coordinate_units import assess_source_coordinate_units
        metadata = self._source_info.get("metadata") or {}
        srs = metadata.get("srs") or {}
        crs = srs.get("wkt", srs.get("compoundwkt", "")) if isinstance(srs, dict) else str(srs)
        return assess_source_coordinate_units(crs)

    def open_thinning_dialog(self):
        """Offer a compact, explicit derived-copy workflow; never changes the open source."""
        if self._thin_worker is not None:
            return
        source = Path(self.source.text())
        fingerprint = str(self._source_info.get("sha256") or "")
        if not source.is_file() or not fingerprint:
            self.status.setText("Open and verify a local LAS or LAZ source before creating a thinned copy.")
            return
        if source.name.lower().endswith(".copc.laz"):
            self.status.setText("Create a thinned copy from a LAS or LAZ source, not the optimized viewer cache.")
            return
        units = self._thinning_unit_assessment()
        metres_per_unit = units.meters_per_source_unit
        unit_label = {
            "METERS": "metres",
            "INTERNATIONAL_FEET": "international feet",
            "US_SURVEY_FEET": "US survey feet",
        }.get(units.units.value, "unverified source units")
        dialog = QDialog(self)
        dialog.setWindowTitle("Create Thinned Copy")
        dialog.setModal(False)
        dialog.setMinimumWidth(620)
        dialog.setStyleSheet("""
            QDialog { background: #f6f8fa; color: #20313a; }
            QDialog QLabel[thinTitle="true"] { color: #174f60; font-size: 16px; font-weight: 600; }
            QDialog QComboBox, QDialog QLineEdit, QDialog QDoubleSpinBox {
                min-height: 28px; border: 1px solid #cbd7dc; border-radius: 4px;
                padding: 2px 6px; background: #ffffff;
            }
            QDialog QPushButton[thinPrimary="true"] {
                background: #176b7a; color: #ffffff; border: 1px solid #115963;
                border-radius: 4px; padding: 5px 12px; font-weight: 600;
            }
            QDialog QPushButton { border: 1px solid #b9cbd1; border-radius: 4px; padding: 4px 10px; background: #ffffff; }
        """)
        form = QFormLayout(dialog)
        form.setContentsMargins(16, 14, 16, 14)
        form.setSpacing(9)
        title = QLabel("Create a Thinned Point-Cloud Copy")
        title.setProperty("thinTitle", True)
        form.addRow(title)
        notice = QLabel(
            "Thinning creates a lighter working copy while the original remains authoritative. "
            "For canopy, trunk, and future individual-tree work, begin with Canopy and trunk detail "
            "(0.25 m) or Fine vegetation detail (0.10 m). It creates a separate LAS/LAZ with a "
            "validation record; the open source, viewer session, and Process workflow are unchanged.")
        notice.setWordWrap(True)
        form.addRow(notice)
        unit_note = QLabel(
            f"Coordinates: {unit_label} ({units.evidence}). "
            + ("The presets are expressed in metres and converted for this file."
               if metres_per_unit else
               "The file does not provide trusted linear units. The default is 1 source unit; confirm "
               "the file units in Tools & Setup before using a distance-sensitive setting."))
        unit_note.setWordWrap(True)
        unit_note.setProperty("thinUnitNote", True)
        form.addRow(unit_note)
        method = QComboBox()
        method.addItem("Voxel grid (recommended)", "voxel_first")
        method.addItem("Poisson disk", "poisson")
        method.setToolTip(
            "Voxel grid keeps one original point from each spacing cell. It is fast, predictable, "
            "and normally best for an interactive copy. Poisson disk produces a more evenly distributed "
            "subset at the chosen minimum spacing; it can take longer on dense clouds.")
        preset = QComboBox()
        preset.addItem("Fine vegetation detail: 0.10 m", .10)
        preset.addItem("Canopy and trunk detail: 0.25 m (recommended)", .25)
        preset.addItem("General working copy: 0.50 m", .50)
        preset.addItem("Overview: 1 m", 1.0)
        preset.addItem("Custom spacing", None)
        preset.setCurrentIndex(1)
        preset.setToolTip(
            "Canopy and trunk detail is the recommended starting point for vegetation work. Fine vegetation "
            "detail keeps more branch and trunk structure but makes a larger copy. General and Overview "
            "reduce density more aggressively. Choose Custom spacing to enter a file-specific value.")
        spacing = QDoubleSpinBox()
        spacing.setRange(0.001, 1000000)
        spacing.setDecimals(3)
        spacing.setValue(1.0 / metres_per_unit if metres_per_unit else 1.0)
        spacing.setSuffix(f" {unit_label}")
        spacing.setToolTip(
            "The separation used by thinning in this file's coordinate system. Larger spacing keeps fewer points; "
            "smaller spacing preserves more detail and creates a larger copy.")
        def apply_preset(_index=0):
            canonical = preset.currentData()
            if canonical is None:
                spacing.setEnabled(True)
                return
            spacing.setValue(float(canonical) / metres_per_unit if metres_per_unit else float(canonical))
            spacing.setEnabled(False)
        preset.currentIndexChanged.connect(apply_preset)
        apply_preset()
        default_output = source.with_name(source.stem + "_thinned.laz")
        output = QLineEdit(str(default_output))
        browse = QPushButton("Browse")
        output_row = QHBoxLayout()
        output_row.addWidget(output, 1)
        output_row.addWidget(browse)
        status = QLabel("")
        status.setWordWrap(True)
        create = QPushButton("Create Thinned Copy")
        create.setProperty("thinPrimary", True)
        open_copy = QPushButton("Open Thinned Copy")
        open_copy.setVisible(False)
        from .point_cloud_widgets import StableViewerHelp
        help_banner = StableViewerHelp(dialog)
        def browse_output():
            path, _ = QFileDialog.getSaveFileName(
                dialog, "Save thinned point cloud", output.text(), "LAZ (*.laz);;LAS (*.las)")
            if path:
                if Path(path).suffix.lower() not in (".las", ".laz"):
                    path += ".laz"
                output.setText(path)
        browse.clicked.connect(browse_output)
        def create_copy():
            try:
                from ..core.point_cloud.preparation import PreparationOptions, PreparationRequest
                from ..core.point_cloud.session import SourceIdentity
                chosen = Path(output.text()).expanduser()
                identity = SourceIdentity(str(source.resolve()), fingerprint, source.stat().st_size,
                                          "LAZ" if source.suffix.lower() == ".laz" else "LAS")
                request = PreparationRequest(identity, str(chosen.resolve()),
                    PreparationOptions(thinning=method.currentData(), spacing=float(spacing.value())))
            except Exception as error:
                status.setText(f"Choose a new output path: {error}")
                return
            create.setEnabled(False)
            method.setEnabled(False)
            preset.setEnabled(False)
            spacing.setEnabled(False)
            output.setEnabled(False)
            browse.setEnabled(False)
            status.setText("Starting managed thinning...")
            self._thin_worker = ThinSourceWorker(request, self)
            self._thin_worker.update.connect(
                lambda value: self._update_thinning(value, dialog, status, create, open_copy))
            self._thin_worker.finished.connect(self._finished_thinning)
            _ACTIVE_WORKERS.add(self._thin_worker)
            self._thin_worker.finished.connect(lambda: _ACTIVE_WORKERS.discard(self._thin_worker))
            self._thin_worker.finished.connect(self._thin_worker.deleteLater)
            self._controls(bool(self._view_state))
            self._thin_worker.start()
        def open_output():
            output_path = open_copy.property("thin_output")
            if output_path:
                dialog.close()
                self.source.setText(output_path)
                self.start_source(output_path)
        create.clicked.connect(create_copy)
        open_copy.clicked.connect(open_output)
        form.addRow("Method", method)
        form.addRow("Recommended density", preset)
        form.addRow("Spacing", spacing)
        form.addRow("Output", output_row)
        form.addRow(status)
        actions = QHBoxLayout()
        actions.addWidget(create)
        actions.addWidget(open_copy)
        form.addRow(actions)
        form.addRow(help_banner)
        for control in (method, preset, spacing, output, browse, create, open_copy):
            control.installEventFilter(self)
        dialog.finished.connect(lambda _result: setattr(self, "_thinning_dialog", None))
        self._thinning_dialog = dialog
        self._thinning_help = help_banner
        dialog.show()

    def _update_thinning(self, value, dialog, status, create, open_copy):
        if value.get("progress"):
            progress = value["progress"]
            status.setText(str(progress.get("stage", "Creating thinned copy")))
        if value.get("error"):
            status.setText("Thinned copy failed: " + str(value["error"]))
            create.setEnabled(True)
        if value.get("complete"):
            result = value["complete"]
            status.setText(
                f"Thinned copy ready: {int(result['input_points']):,} to "
                f"{int(result['output_points']):,} points. Original source unchanged.")
            open_copy.setProperty("thin_output", result["output_path"])
            open_copy.setVisible(True)
            self.status.setText("Thinned copy ready. The original source remains open.")

    def _finished_thinning(self):
        self._thin_worker = None
        self._controls(bool(self._view_state))

    def choose_scientific_overlay(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose cached scientific raster", "", "GeoTIFF (*.tif *.tiff)")
        if path:
            self.load_scientific_overlay_path(path, choose_band=True)

    def load_scientific_overlay_path(self, path: str | Path, *, choose_band: bool = False) -> bool:
        """Load a verified scientific GeoTIFF as a linked viewer overlay."""
        try:
            from qgis.core import QgsCoordinateReferenceSystem, QgsRasterLayer
            from ..core.point_cloud.scientific_visualization import product_visualization_spec
            output_path = Path(path)
            layer = QgsRasterLayer(str(output_path), output_path.stem)
            if not layer.isValid():
                raise ValueError("The selected raster could not be opened by QGIS.")
            stem = output_path.stem.upper().replace("-", "_").replace(" ", "_")
            product_id = next((key for key in (
                "CANOPY_COVER", "POINT_DENSITY", "VOXEL_STATISTIC", "CHM", "DTM",
                "PAD", "PAI", "FHD", "RUMPLE",
            ) if key in stem), None)
            if not product_id:
                raise ValueError("The output name does not identify a registered scientific product.")
            spec = product_visualization_spec(product_id)
            source_metadata = self._source_info.get("metadata") or {}
            raw_source_crs = (self._source_info.get("crs") or source_metadata.get("crs")
                              or source_metadata.get("srs") or "")
            source_crs = QgsCoordinateReferenceSystem(str(raw_source_crs)) if raw_source_crs else None
            overlay_crs = layer.crs()
            if (source_crs and source_crs.isValid() and overlay_crs.isValid()
                    and source_crs.authid() and overlay_crs.authid()
                    and source_crs.authid().upper() != overlay_crs.authid().upper()):
                raise ValueError(
                    f"Raster CRS {overlay_crs.authid()} does not match source CRS {source_crs.authid()}.")
            band_index = 1
            if product_id in {"PAD", "VOXEL_STATISTIC"} and layer.bandCount() > 1 and choose_band:
                band_index, accepted = QInputDialog.getInt(
                    self, f"Choose {spec.label} band", "Vertical/support band:",
                    1, 1, layer.bandCount())
                if not accepted:
                    return False
            extent = layer.extent()
            columns = min(96, max(2, int(max(layer.width(), layer.height()) ** .5 * 4)))
            rows = min(96, max(2, round(
                columns * max(extent.height(), .001) / max(extent.width(), .001))))
            block = layer.dataProvider().block(band_index, extent, columns, rows)
            values = []
            for row in range(rows):
                for col in range(columns):
                    if block.isNoData(row, col):
                        values.append(None)
                    else:
                        value = float(block.value(row, col))
                        values.append(value if value == value else None)
            source_fingerprint = str(
                self._source_info.get("sha256")
                or (self._source_info.get("source_identity") or {}).get("sha256")
                or "")
            if not source_fingerprint:
                raise ValueError(
                    "Open the point cloud before loading a scientific overlay so source provenance can be checked.")
            output_stat = output_path.stat()
            payload = ScientificOverlayPayload(
                product_id, spec.label, spec.kind.value, spec.units, layer.crs().authid(),
                (extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()),
                rows, columns, tuple(values), overlay_value_range(values), None, spec.palette,
                {
                    "source_fingerprint": source_fingerprint,
                    "output_path": str(output_path.resolve()),
                    "output_identity": f"{output_stat.st_size}:{output_stat.st_mtime_ns}",
                    "crs_alignment": ("verified" if source_crs and source_crs.isValid()
                                      and overlay_crs.isValid() else "unknown"),
                },
                vertical_semantics=spec.vertical_semantics,
                surface_mode="values" if product_id == "DTM" else "flat",
                band_index=band_index,
            )
            self._scientific_overlay = payload
            self.clear_overlay_action.setEnabled(True)
            self.linked.broadcast_viewer_command(payload.as_command())
            band_text = f" | band {band_index}" if layer.bandCount() > 1 else ""
            self.status.setText(
                f"{spec.label} overlay loaded{band_text} | cached spatial product | "
                f"{payload.valid_value_count:,} sampled cells")
            return True
        except Exception as error:
            self.status.setText(f"Scientific overlay unavailable: {error}")
            return False

    def clear_scientific_overlay(self):
        self._scientific_overlay = None
        self.clear_overlay_action.setEnabled(False)
        self.linked.broadcast_viewer_command({"action": "clear_scientific_overlay"})
        self.status.setText("Scientific overlay cleared | cached product remains unchanged")

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

    def _observe_classes(self, codes, visible, resident_counts=None):
        from ..core.point_cloud.view_filters import class_visibility_rows
        from .point_cloud_class_visibility import class_swatch_icon
        rows = class_visibility_rows(codes, visible, resident_counts)
        known = {self.class_list.item(i).data(qt_enum(Qt, "UserRole", "ItemDataRole")):
                 self.class_list.item(i) for i in range(self.class_list.count())}
        self.class_list.blockSignals(True)
        row_codes = {row.code for row in rows}
        for index in reversed(range(self.class_list.count())):
            if self.class_list.item(index).data(qt_enum(Qt, "UserRole", "ItemDataRole")) not in row_codes:
                self.class_list.takeItem(index)
        for row in rows:
            item = known.get(row.code)
            if item is None:
                item = QListWidgetItem()
                item.setData(qt_enum(Qt, "UserRole", "ItemDataRole"), row.code)
                item.setFlags(item.flags() | qt_enum(Qt, "ItemIsUserCheckable", "ItemFlag"))
                self.class_list.addItem(item)
            item.setText(row.text)
            item.setIcon(class_swatch_icon(row.color))
            item.setToolTip("Approximate count covers resident points in this view after staged edits; authoritative selected counts are shown in Selection Details.")
            item.setCheckState(qt_enum(Qt, "Checked" if row.visible else "Unchecked", "CheckState"))
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
            from ..core.point_cloud.view_filters import isolated_class
            self.send({"action": "classes", "classes": isolated_class(classes[0])})

    def show_all_classes(self):
        self._sync_classes(None)
        self.send({"action": "classes", "classes": list(range(256))})

    def _controls(self, ready):
        for button in self.view_buttons:
            button.setEnabled(ready)
        self.mode.setEnabled(ready)
        self.palette.setEnabled(ready)
        self.appearance.setEnabled(ready)
        self.overlay_button.setEnabled(ready)
        self.prepare_button.setEnabled(ready and self._thin_worker is None)
        self.clear_overlay_action.setEnabled(ready and self._scientific_overlay is not None)
        self.apply_filters_button.setEnabled(ready)
        self.clear_filters_button.setEnabled(ready)
        self.class_list.setEnabled(ready)
        self.solo_class_button.setEnabled(ready)
        self.show_classes_button.setEnabled(ready)
        self.save_session_button.setEnabled(ready and self._session_worker is None and self._pending_save is None)
        if hasattr(self,"linked") and self.linked.active().view_type == "VERTICAL_SLICE":
            for button in self.view_buttons[1:]:
                button.setEnabled(False)

    def send(self, command):
        if self.worker:
            self.worker.send(command)

    def _send_point_display(self, command):
        self.send(command)
        linked = getattr(self, "linked", None)
        if linked is not None:
            linked.set_point_display(
                self.workspace.active_view_id,
                command.get("style", "Circular"),
                command.get("size", 0),
            )

    def _start(self, worker):
        if self.worker is not None:
            self.status.setText("Close the current viewer before starting another operation.")
            return
        self.worker = worker
        self.status.setBusy(True)
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
            self.status.setBusy(False)
            self.status.setText("Select a LAS, LAZ, COPC or local EPT source.")
            return
        self.status.setBusy(True)
        self.status.setText("Opening linked point cloud" if render_only else "Verifying original source")
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
        self._display_stabilizer.reset()
        self._pending_save = None
        self._source_info = {}
        self._scientific_overlay = None
        self.class_list.clear()
        self._edit_session = self._session_to_open
        self._restore_expected = None
        for combo, value in ((self.mode, "Classification"), (self.palette, "Viridis"), (self.quality, "Automatic")):
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

    def _sync_available_modes(self, modes):
        modes = tuple(modes or ())
        if not modes:
            return
        current = self.mode.currentText()
        existing = tuple(self.mode.itemText(index) for index in range(self.mode.count()))
        self.mode.blockSignals(True)
        if existing != modes:
            self.mode.clear()
            self.mode.addItems(modes)
        self.mode.setCurrentText(current if current in modes else modes[0])
        self.mode.blockSignals(False)

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
        if value.get("viewer_command") == "palette":
            self.status.setText("Palette applied in renderer: " + str(value.get("palette", "unknown")))
        if value.get("error"):
            self.status.setBusy(False)
            self.status.setText(value["error"])
            self._controls(False)
        telemetry = value.get("telemetry", {})
        if telemetry.get("ready"):
            self.status.setBusy(False)
            self._view_state = telemetry
            display_state = dict(telemetry)
            active_view = self.workspace.views.get(self.workspace.active_view_id)
            if active_view:
                display_state.update(point_style=active_view.lod.get("point_style", "Circular"),
                                     point_size=active_view.lod.get("point_size", 0))
            self.appearance.sync(display_state)
            self._sync_available_modes(telemetry.get("available_modes"))
            self.palette.setEnabled(telemetry.get("mode") != "Classification")
            self.palette.blockSignals(True)
            # Keep the user-selected palette; stale telemetry must not reset it.
            self.palette.blockSignals(False)
            self.display_range.sync(telemetry)
            self.linked.observe(telemetry)
            self.editor.observe(telemetry)
            self.linked.coordinate_resources()
            self._observe_classes(telemetry.get("observed_classes", []), telemetry.get("classes"),
                                  (telemetry.get("editor") or {}).get("effective_classes", {}))
            self._controls(True)
            if self._session_worker is None and self._scientific_overlay is None:
                if self.status.text() != "Source open | Original unchanged":
                    self.status.setText("Source open | Original unchanged")
                if telemetry.get("mode") == "RGB" and telemetry.get("rgb_diagnostic", {}).get("message"):
                    self.status.setText(telemetry["rgb_diagnostic"]["message"])
            display_summary = self._display_stabilizer.observe(telemetry)
            displayed = display_summary["displayed"]
            budget = display_summary["budget"]
            active_view = self.workspace.views.get(self.workspace.active_view_id)
            view_label = active_view.title if active_view else "Active view"
            budget_text = f" | Display budget: {budget:,}" if isinstance(budget, int) else ""
            self.details.setText(
                f"{view_label} | Display sample: {displayed:,}{budget_text} | "
                f"{display_summary['quality']} | {display_summary['detail']}")
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
                self.palette.setCurrentText(restored.get("palette", "Viridis"))
                self.send({"action": "palette", "palette": restored.get("palette", "Viridis")})
                self.appearance.sync(restored)
                self.send({"action": "point_display",
                           "style": restored.get("point_style", "Circular"),
                           "size": restored.get("point_size", 0)})
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
        self.status.setBusy(False)
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
