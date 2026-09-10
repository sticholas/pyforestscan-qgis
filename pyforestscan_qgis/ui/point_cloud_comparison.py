"""Read-only, source-isolated point-cloud comparison window."""
from pathlib import Path
import time

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout,
                                QToolButton, QComboBox)

from ..compat.qt import qt_enum
from ..core.point_cloud.comparison import (
    ComparisonSourceRecord, comparison_display_command)
from .point_cloud_widgets import StableViewerStatus


class ComparisonView(QDialog):
    closed = pyqtSignal(str)

    def __init__(self, controller, comparison_id, source):
        super().__init__(controller.page, qt_enum(Qt, "Window", "WindowType"))
        from .point_cloud_page import ViewerSurface, ViewerWorker, _ACTIVE_WORKERS
        self.controller = controller
        self.comparison_id = comparison_id
        self.source = str(source)
        self.source_record = None
        self.telemetry = {}
        self.worker = None
        self.closing = False
        self.fit_sent = False
        self.fit_attempts = 0
        self.last_fit_at = 0.0
        self.setWindowTitle(f"Compare: {Path(source).name}")
        self.resize(960, 720)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        row = QHBoxLayout()
        for label, action in (("Fit", "fit"), ("Top", "top"), ("Front", "front")):
            button = QToolButton()
            button.setText(label)
            button.setToolTip(f"{label} this comparison source. Display only; no source or edit state changes.")
            button.clicked.connect(lambda _checked=False, value=action:
                                   self.send({"action": value}))
            row.addWidget(button)
        self.mode = QComboBox()
        self.mode.addItems(("Classification", "Elevation", "RGB", "Intensity"))
        self.mode.setToolTip("Display attribute for this comparison source only.")
        self.mode.currentTextChanged.connect(
            lambda value: self.send({"action":"mode", "mode":value}))
        row.addWidget(self.mode, 1)
        from .point_cloud_appearance import PointAppearance
        self.appearance = PointAppearance(self.send, self)
        row.addWidget(self.appearance)
        layout.addLayout(row)
        self.surface = ViewerSurface(self)
        layout.addWidget(self.surface, 1)
        self.status = StableViewerStatus(
            "Opening independent read-only comparison source...", self)
        layout.addWidget(self.status)
        self.details = StableViewerStatus(
            "No selection or edit journal is shared with this window.", self)
        layout.addWidget(self.details)
        self.surface.resized.connect(
            lambda width, height:self.send({"action":"resize", "width":width, "height":height}))
        self.surface.visibility.connect(
            lambda visible:self.send({"action":"visible", "visible":visible}))
        # A foreign Qt6 renderer needs a real, exposed Windows child handle.
        # Process the top-level show before capturing it; an early synthetic
        # handle can embed successfully yet never expose/load visible nodes.
        self.show()
        QApplication.processEvents()
        worker = ViewerWorker(source=self.source, parent_handle=int(self.surface.winId()))
        self.worker = worker
        worker.update.connect(self.update_view)
        worker.finished.connect(self.finished)
        _ACTIVE_WORKERS.add(worker)
        worker.finished.connect(lambda:_ACTIVE_WORKERS.discard(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def send(self, command):
        value = comparison_display_command(command)
        if self.worker and not self.closing:
            self.worker.send(value)

    def update_view(self, value):
        if self.closing:
            return
        if value.get("started"):
            self.send({"action":"resize", "width":self.surface.width(),
                       "height":self.surface.height()})
        if value.get("status"):
            self.status.setText(value["status"])
        if value.get("error"):
            self.status.setText("Comparison unavailable: " + value["error"])
        if value.get("source_info"):
            try:
                self.source_record = ComparisonSourceRecord.from_viewer_info(
                    self.source, value["source_info"], comparison_id=self.comparison_id)
                relationship = self.source_record.relationship(
                    self.controller.page.workspace.source_fingerprint)
                note = "Same immutable source reference" if relationship == "SAME_SOURCE_REFERENCE" else "Independent source"
                self.details.setText(
                    f"{note} | {self.source_record.source_type} | No shared selection or edit journal")
            except ValueError as error:
                self.status.setText(str(error))
        telemetry = value.get("telemetry") or {}
        if telemetry.get("ready"):
            self.telemetry = telemetry
            self.appearance.sync(telemetry)
            displayed = telemetry.get("render_diagnostics", {}).get(
                "rendered_points", telemetry.get("displayed", 0))
            now = time.monotonic()
            if (displayed <= 0 and self.fit_attempts < 3
                    and now - self.last_fit_at >= 1.0):
                self.fit_sent = True
                self.fit_attempts += 1
                self.last_fit_at = now
                self.send({"action":"fit"})
            if not value.get("status"):
                self.status.setText("Comparison ready | Read-only independent source")
            identity = self.source_record.source_type if self.source_record else "Verifying source"
            self.details.setText(
                f"{identity} | Displayed: {displayed:,} | No shared selection or edit journal")
            self.controller.coordinate_resources()

    def finished(self):
        self.worker = None
        if not self.closing:
            self.status.setText("Comparison viewer closed.")

    def shutdown(self):
        if self.closing:
            return
        self.closing = True
        worker, self.worker = self.worker, None
        if worker:
            try:
                worker.update.disconnect(self.update_view)
                worker.finished.disconnect(self.finished)
            except (RuntimeError, TypeError):
                pass
            worker.stop("comparison_window_close")
        self.closed.emit(self.comparison_id)

    def closeEvent(self, event):
        self.shutdown()
        event.accept()
