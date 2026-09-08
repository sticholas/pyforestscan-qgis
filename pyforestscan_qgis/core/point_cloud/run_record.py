"""Durable, attempt-scoped viewer diagnostics without Qt or scientific imports."""
from __future__ import annotations
from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import threading
import time
import traceback
from uuid import uuid4
from ..atomic_state import atomic_write_json

STAGES = (
    "VIEWER_PROCESS_CREATED", "QT_INITIALIZED", "WEBENGINE_INITIALIZED",
    "VIEWER_ASSETS_LOADED", "JS_READY", "SOURCE_REQUESTED", "SOURCE_OPENED",
    "FIRST_NODE_LOADED", "FIRST_FRAME_RENDERED", "CAMERA_READY",
    "INTERACTION_READY", "SESSION_READY", "SHUTDOWN_REQUESTED", "SHUTDOWN_COMPLETE",
)


def now():
    return datetime.now(timezone.utc).isoformat()


class ViewerRunRecord:
    """One writer lock, distinct output files, explicit unknowns after hard kills."""

    def __init__(self, root: Path, source: str, versions=None):
        self.folder = Path(root) / uuid4().hex
        self.folder.mkdir(parents=True, exist_ok=False)
        self.path = self.folder / "viewer_run.json"
        self.started = time.monotonic()
        self.lock = threading.RLock()
        self.data = dict.fromkeys((
            "finished_at", "duration", "viewer_pid", "exit_code", "exit_signal",
            "source_fingerprint", "last_successful_stage", "exception_type",
            "exception_message", "traceback", "OpenGL_information", "WebGL_information",
        ))
        self.data.update({
            "run_id": self.folder.name, "started_at": now(), "parent_pid": os.getpid(),
            "QGIS_version": None, "Qt_version": None, "Python_version": platform.python_version(),
            "platform": platform.platform(), "viewer_backend": "isolated QtQuick/WebEngine + Potree",
            "source": source, "source_format": "COPC" if source.lower().endswith(".copc.laz") else
                "EPT" if source.lower().endswith("ept.json") else Path(source).suffix[1:].upper(),
            "viewer_stage": "PREPARING", "stdout_path": str(self.folder / "stdout.log"),
            "stderr_path": str(self.folder / "stderr.log"), "JS_console_messages": [],
            "QML_errors": [], "WebEngine_errors": [], "source_load_status": "NOT_STARTED",
            "first_frame_status": "NOT_OBSERVED", "camera_initialized": False,
            "shutdown_requested": False, "shutdown_origin": None, "stage_history": [],
        })
        self.data.update(versions or {})
        # Launch may fail before Popen; every attempt still has inspectable logs.
        for name in ("stdout.log", "stderr.log", "prepare_stdout.log", "prepare_stderr.log"):
            (self.folder / name).touch(exist_ok=False)
        self.update()

    def update(self, **values):
        with self.lock:
            self.data.update(values)
            self.data["duration"] = round(time.monotonic() - self.started, 3)
            atomic_write_json(self.path, self.data)

    def stage(self, stage, **values):
        with self.lock:
            if stage not in STAGES:
                raise ValueError("Unknown viewer lifecycle stage.")
            self.data["stage_history"] = (self.data["stage_history"] + [{"stage": stage, "at": now()}])[-64:]
            self.update(viewer_stage=stage, last_successful_stage=stage, **values)

    def observe(self, value):
        if value.get("stage") in STAGES:
            self.stage(value["stage"])
        fields = {key: value[key] for key in ("viewer_Qt_version", "OpenGL_information", "WebGL_information",
                  "source_load_status", "first_frame_status", "camera_initialized", "screenshot") if key in value}
        for field in ("JS_console_messages", "QML_errors", "WebEngine_errors"):
            if field in value:
                with self.lock:
                    fields[field] = (self.data[field] + [value[field]])[-100:]
        if value.get("telemetry"):
            fields["render_stats"] = value["telemetry"]
            if value["telemetry"].get("webgl_information"):
                fields["WebGL_information"] = value["telemetry"]["webgl_information"]
        if fields:
            self.update(**fields)

    def shutdown(self, origin):
        self.stage("SHUTDOWN_REQUESTED", shutdown_requested=True, shutdown_origin=origin)

    def finish(self, exit_code, error=None):
        values = {"exit_code": exit_code, "exit_signal": -exit_code if exit_code is not None and exit_code < 0 and os.name != "nt" else None,
                  "finished_at": now()}
        if error:
            values.update(exception_type=type(error).__name__, exception_message=str(error),
                          traceback="".join(traceback.format_exception(type(error), error, error.__traceback__)))
        if exit_code == 0 and self.data["shutdown_requested"] and error is None:
            self.stage("SHUTDOWN_COMPLETE", **values)
        else:
            self.update(**values)
