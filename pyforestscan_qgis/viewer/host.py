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
import time
import platform

# Executed by the isolated viewer Python with -I; only this plugin is added.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pyforestscan_qgis.core.point_cloud.asset_server import ViewerAssetServer
from pyforestscan_qgis.core.point_cloud.view_policy import next_view_budget, system_memory_pressure


def assets(root=None):
    root = (Path(root) if root is not None else Path(__file__).parent / "assets").resolve(strict=True)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    result = {}
    for name, record in manifest["files"].items():
        path = (root / name).resolve(strict=True)
        if not path.is_relative_to(root):
            raise ValueError("Invalid packaged viewer asset.")
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Viewer asset needs repair: {name}")
        route = "assets/" + name
        if name.startswith("resources/"):
            route = "assets/build/potree/" + name
        result[route] = path
    result["viewer.html"] = Path(__file__).with_name("viewer.html")
    result["viewer.js"] = Path(__file__).with_name("viewer.js")
    result["editor.js"] = Path(__file__).with_name("editor.js")
    result["drawing.js"] = Path(__file__).with_name("drawing.js")
    result["rgb.js"] = Path(__file__).with_name("rgb.js")
    result["assets/build/potree/workers/rgb.js"] = Path(__file__).with_name("rgb.js")
    result["render_policy.js"] = Path(__file__).with_name("render_policy.js")
    worker_route = "assets/build/potree/workers/EptLaszipDecoderWorker.js"
    result[worker_route.replace(".js", ".vendor.js")] = result[worker_route]
    result[worker_route] = Path(__file__).with_name("full_file_decoder.js")
    return result


def main():
    host_started = time.monotonic()
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
    asset_started = time.monotonic()
    packaged_assets = assets()
    assets_verified = time.monotonic()
    server = ViewerAssetServer(assets=packaged_assets, source=args.source)
    emit({"stage": "VIEWER_ASSETS_LOADED", "host_startup_seconds": {
        "qt_initialization": round(asset_started - host_started, 6),
        "asset_verification": round(assets_verified - asset_started, 6),
        "source_server": round(time.monotonic() - assets_verified, 6),
    }})
    viewer_url = server.base_url + "viewer.html?source=" + server.source_route
    observed = set()
    memory_sample = {"at": 0, "value": None}
    profile_state = {"path": None, "seed": None, "saved_at": 0}
    coordinated_limit = {"points": None}

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
                now = time.monotonic()
                if now - memory_sample['at'] > 1:
                    memory_sample.update(at=now, value=system_memory_pressure())
                value['system_memory'] = memory_sample['value']
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
                    from pyforestscan_qgis.core.point_cloud.runtime import ViewerRuntimeService, runtime_spec
                    from pyforestscan_qgis.core.atomic_state import atomic_write_json
                    if profile_state['path'] is None:
                        key = hashlib.sha256(json.dumps([platform.platform(), runtime_spec()[1],
                            value.get('webgl_information'), 'motion-policy-v1'], sort_keys=True).encode()).hexdigest()
                        profile_state['path'] = ViewerRuntimeService().root / 'performance-profiles' / (key + '.json')
                        try:
                            saved = json.loads(profile_state['path'].read_text(encoding='utf-8'))
                            if time.time() - saved['timestamp'] < 30 * 86400:
                                profile_state['seed'] = max(0, min(2000000, int(saved['comfortable_points'])))
                        except (OSError, ValueError, KeyError, TypeError):
                            pass
                    previous = max(int(value.get('budget', 0)), profile_state['seed'] or 0)
                    profile_state['seed'] = None
                    memory = memory_sample['value'] or {}
                    pressure = max(value.get('memory_pressure', 0), memory.get('pressure', 0))
                    value['performance_profile'] = profile_state['path'].name
                    policy = next_view_budget(
                        previous, viewport_pixels=max(1, view.width() * view.height()),
                        moving=bool(value.get("moving")), frame_ms=value.get("frame_ms"),
                        source_points=value.get("source_points"),
                        root_points=max(0, int(value.get("render_diagnostics", {}).get("root_points") or 0)),
                        velocity=value.get("camera_velocity", 0.0),
                        memory_pressure=pressure,
                        available_bytes=memory.get('available_bytes'),
                        quality=value.get("quality", "Automatic"))
                    if (not value.get('moving') and value.get('displayed', 0) > 0 and
                            value.get('frame_ms', 100) < 30 and now - profile_state['saved_at'] > 30):
                        try:
                            atomic_write_json(profile_state['path'], {'timestamp': time.time(),
                                'comfortable_points': value['displayed'], 'frame_ms': value['frame_ms'],
                                'advisory_only': True})
                            profile_state['saved_at'] = now
                        except OSError:
                            pass
                    limit = coordinated_limit["points"]
                    ceiling = policy.ceiling if limit is None else min(policy.ceiling,limit)
                    self.command.emit(json.dumps({"action": "budget", "points": min(policy.points,ceiling),
                                                  "screen_error": policy.screen_error,
                                                  "ceiling": ceiling, "floor": min(policy.floor,ceiling),
                                                  "pressure": pressure,
                                                  "source_class": policy.source_class}))
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
        nonlocal parent
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
            elif action == "reparent":
                handle = command["parent"]
                if type(handle) is not int or not 0 < handle < 2**64:
                    raise ValueError("Invalid viewer parent handle.")
                if int(parent.winId()) != handle:
                    replacement = QWindow.fromWinId(handle)
                    if replacement is None:
                        raise ValueError("Viewer parent surface is unavailable.")
                    previous = parent
                    view.hide()
                    view.setParent(replacement)
                    parent = replacement
                    view.setPosition(0, 0)
                    previous.deleteLater()
                view.show()
                emit({"surface_attached": command["request_id"]})
            elif action == "resource_limit":
                limit = command["points"]
                if type(limit) is not int or not 0 <= limit <= 2000000:
                    raise ValueError("Invalid coordinated point allocation.")
                coordinated_limit["points"] = limit
                view.setVisible(limit > 0)
            elif action == "capture":
                capture(command["name"])
            elif action == "session_ready":
                stage_once("SESSION_READY")
            elif action == "editor_overlay":
                from pyforestscan_qgis.core.point_cloud.runtime import ViewerRuntimeService
                path = Path(command["path"]).resolve(strict=True)
                root = (ViewerRuntimeService().root / "editor-runs").resolve()
                if path.name != "overlay.json" or not path.is_relative_to(root) or path.stat().st_size > 16 * 1024 * 1024:
                    raise ValueError("Invalid editor overlay path.")
                server.assets["editor-overlay.json"] = path
                bridge.command.emit(json.dumps({"action": "editor_overlay", "selection_color": command.get("selection_color")}))
            elif action in ("fit", "top", "front", "mode", "classes", "height", "clear_height", "clear_filters", "camera", "navigation", "orbit", "pan", "zoom", "snapshot", "selection_tool", "selection_test", "selection_resolution", "linked_view", "quality", "point_display"):
                bridge.command.emit(json.dumps(command, allow_nan=False))
        except (ValueError, KeyError, TypeError, OverflowError, OSError):
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
