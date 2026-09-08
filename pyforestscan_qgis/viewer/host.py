"""Managed QtQuick renderer process, embedded into a host-owned native surface."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from pathlib import Path
import sys
import struct
import threading

# Executed by the isolated viewer Python with -I; only this plugin is added.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pyforestscan_qgis.core.point_cloud.asset_server import ViewerAssetServer
from pyforestscan_qgis.core.point_cloud.view_policy import next_view_budget


def assets():
    root = Path(__file__).parent / "assets"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    result = {}
    for name, record in manifest["files"].items():
        path = (root / name).resolve(strict=True)
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Invalid packaged viewer asset.")
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Viewer asset needs repair: {name}")
        route = "assets/" + name
        if name.startswith("resources/"):
            route = "assets/build/potree/" + name
        result[route] = path
    result["viewer.html"] = Path(__file__).with_name("viewer.html")
    result["viewer.js"] = Path(__file__).with_name("viewer.js")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", required=True, type=int)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args()
    from PySide6.QtCore import QObject, Signal, Slot, QUrl, QTimer
    from PySide6.QtGui import QGuiApplication, QWindow
    from PySide6.QtQuick import QQuickView
    from PySide6.QtWebEngineQuick import QtWebEngineQuick, QQuickWebEngineProfile
    from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor

    def emit(value):
        print(json.dumps(value, allow_nan=False), flush=True)

    QtWebEngineQuick.initialize()
    emit({"stage": "WEBENGINE_INITIALIZED"})
    app = QGuiApplication(sys.argv)
    from PySide6.QtCore import qVersion
    emit({"stage": "QT_INITIALIZED", "viewer_Qt_version": qVersion()})
    if app.platformName() != "windows":
        raise RuntimeError("Embedded viewer platform adapter is not yet qualified on this platform.")
    server = ViewerAssetServer(assets=assets(), source=args.source)
    emit({"stage": "VIEWER_ASSETS_LOADED"})
    viewer_url = server.base_url + "viewer.html?source=" + server.source_route
    observed = set()

    def stage_once(stage, **values):
        if stage not in observed:
            observed.add(stage)
            emit({"stage": stage, **values})

    def capture(name):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name):
            raise ValueError("Invalid screenshot name.")
        bridge.command.emit(json.dumps({"action": "capture", "name": name}))

    def accept_capture(name, encoded):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name):
            raise ValueError("Invalid screenshot name.")
        prefix = "data:image/png;base64,"
        if not encoded.startswith(prefix) or len(encoded) > 16 * 1024 * 1024:
            raise ValueError("Invalid or oversized canvas capture.")
        raw = base64.b64decode(encoded[len(prefix):], validate=True)
        if len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Invalid PNG capture.")
        width, height = struct.unpack_from(">II", raw, 16)
        if width * height > 8_000_000:
            raise ValueError("Canvas capture exceeds the pixel budget.")
        from PySide6.QtGui import QImage
        frame = QImage.fromData(raw, "PNG")
        colors = set()
        if not frame.isNull():
            for y in range(0, frame.height(), max(1, frame.height() // 48)):
                for x in range(0, frame.width(), max(1, frame.width() // 48)):
                    colors.add(frame.pixelColor(x, y).rgb())
        path = args.run_dir / (name + ".png")
        saved = not frame.isNull() and frame.save(str(path))
        result = {"name": name, "path": str(path), "saved": bool(saved), "sampled_colors": len(colors),
                  "width": frame.width(), "height": frame.height()}
        emit({"screenshot": result})
        if name == "first_frame":
            observed.discard("CAPTURE_PENDING")
            if saved and len(colors) > 1:
                stage_once("FIRST_FRAME_RENDERED", first_frame_status="NONBLANK_WEBGL_CAPTURE")
        return result

    class Bridge(QObject):
        command = Signal(str)
        received = Signal(str)

        @Slot(str, str)
        def captured(self, name, encoded):
            try:
                accept_capture(name, encoded)
            except (ValueError, TypeError) as error:
                observed.discard("CAPTURE_PENDING")
                emit({"error": str(error)})

        @Slot(str)
        def diagnostic(self, payload):
            try:
                emit(json.loads(payload))
            except (ValueError, TypeError):
                pass

        @Slot(str)
        def telemetry(self, payload):
            try:
                value = json.loads(payload)
                if not isinstance(value, dict):
                    return
                value["transport"] = server.stats()
                if value.get("js_ready"):
                    stage_once("JS_READY")
                if value.get("source_requested"):
                    stage_once("SOURCE_REQUESTED", source_load_status="REQUESTED")
                if value.get("ready"):
                    stage_once("SOURCE_OPENED", source_load_status="OPEN")
                    if value.get("displayed", 0) > 0:
                        stage_once("FIRST_NODE_LOADED")
                        if "FIRST_FRAME_RENDERED" not in observed and "CAPTURE_PENDING" not in observed and view.isExposed():
                            observed.add("CAPTURE_PENDING")
                            capture("first_frame")
                    if value.get("camera"):
                        stage_once("CAMERA_READY", camera_initialized=True)
                    stage_once("INTERACTION_READY")
                    policy = next_view_budget(
                        int(value.get("budget", 0)), viewport_pixels=max(1, view.width() * view.height()),
                        moving=bool(value.get("moving")), frame_ms=value.get("frame_ms"))
                    self.command.emit(json.dumps({"action": "budget", "points": policy.points,
                                                  "screen_error": policy.screen_error}))
                emit({"telemetry": value})
            except (ValueError, TypeError, OverflowError):
                emit({"error": "Invalid renderer telemetry."})

    class LocalOnly(QWebEngineUrlRequestInterceptor):
        def interceptRequest(self, info):
            url = info.requestUrl()
            if url.scheme() not in ("data", "blob", "about") and not url.toString().startswith(server.base_url):
                info.block(True)

    bridge = Bridge()
    interceptor = LocalOnly(app)
    profile = QQuickWebEngineProfile.defaultProfile()
    profile.setUrlRequestInterceptor(interceptor)
    profile.downloadRequested.connect(lambda download: download.cancel())
    view = QQuickView()
    view.setTitle("PyForestScan point cloud renderer")
    view.rootContext().setContextProperty("viewerUrl", QUrl(viewer_url))
    view.rootContext().setContextProperty("bridge", bridge)
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.resize(640, 480)
    view.winId()
    parent = QWindow.fromWinId(args.parent)
    if parent is None:
        server.close()
        raise RuntimeError("Embedded viewer surface is unavailable.")
    view.setParent(parent)
    view.setPosition(0, 0)

    def receive(line):
        try:
            command = json.loads(line)
            if not isinstance(command, dict):
                return
            action = command.get("action")
            if action == "close":
                view.hide()
                view.setParent(None)
                app.quit()
            elif action == "resize":
                view.resize(max(1, min(16384, int(command["width"]))),
                            max(1, min(16384, int(command["height"]))))
            elif action == "visible":
                view.setVisible(bool(command["visible"]))
            elif action == "capture":
                capture(command["name"])
            elif action == "session_ready":
                stage_once("SESSION_READY")
            elif action in ("fit", "top", "front", "mode", "classes", "height", "clear_height", "clear_filters", "camera", "navigation", "orbit", "pan", "zoom", "snapshot"):
                bridge.command.emit(json.dumps(command, allow_nan=False))
        except (ValueError, KeyError, TypeError, OverflowError):
            emit({"error": "Invalid viewer command."})

    bridge.received.connect(receive)

    def listen():
        while True:
            line = sys.stdin.readline(65537)
            if not line or len(line) > 65536:
                bridge.received.emit('{"action":"close"}')
                return
            bridge.received.emit(line)

    threading.Thread(target=listen, daemon=True).start()
    view.setSource(QUrl.fromLocalFile(str(Path(__file__).with_name("host.qml"))))
    view.statusChanged.connect(lambda status: emit({"QML_errors": [e.toString() for e in view.errors()]}) if view.errors() else None)
    if view.rootObject() is None:
        server.close()
        raise RuntimeError("Viewer QML failed: " + "; ".join(e.toString() for e in view.errors()))
    view.show()
    emit({"started": True})
    try:
        return app.exec()
    finally:
        server.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({"error": str(error)}), flush=True)
        sys.exit(1)
