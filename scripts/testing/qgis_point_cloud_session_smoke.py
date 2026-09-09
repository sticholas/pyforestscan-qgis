"""Real-QGIS page recreation and fingerprint-safe viewer-session round trip."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    from qgis.core import QgsApplication
    from qgis.PyQt.QtCore import QTimer
    from pyforestscan_qgis.ui.point_cloud_page import PointCloudPage
    from pyforestscan_qgis.core.point_cloud.view_session import session_view_state
    from pyforestscan_qgis.core.point_cloud.session import PointCloudEditSession
    from pyforestscan_qgis.core.atomic_state import atomic_write_json

    app = QgsApplication([str(value).encode() for value in sys.argv], True)
    app.initQgis()
    source = args.source
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    page = PointCloudPage()
    page.resize(760, 680)
    page.show()
    page.source.setText(str(source))
    page.start_source(str(source))
    started = time.monotonic()
    phase, phase_at = 0, started
    session_path = args.output_dir / "session.json"
    expected = None
    retired = None
    report = {"passed": False, "sha256_before": before, "events": []}

    def finish(error=None):
        timer.stop()
        report["sha256_after"] = hashlib.sha256(source.read_bytes()).hexdigest()
        report["error"] = error
        worker = page.worker
        session_worker = page._session_worker
        completion = [w.stopped_event for w in (worker, session_worker, page.editor.worker) if w is not None]
        page.prepare_for_unload()
        def complete():
            if any(not event.is_set() for event in completion):
                QTimer.singleShot(100, complete)
                return
            report["passed"] = error is None and report["sha256_before"] == report["sha256_after"]
            report["duration"] = round(time.monotonic() - started, 3)
            atomic_write_json(args.output_dir / "session_roundtrip.json", report)
            print(json.dumps(report), flush=True)
            page.close()
            app.exit(0 if report["passed"] else 1)
        complete()

    def tick():
        nonlocal page, phase, phase_at, expected, retired
        now = time.monotonic()
        if now - started > 90:
            finish(f"Timed out in phase {phase}: {page.status.text()}")
            return
        state = page._view_state
        if phase == 0 and state and state.get("ready"):
            page.send({"action": "orbit"})
            page.send({"action": "mode", "mode": "Elevation"})
            page.send({"action": "classes", "classes": [5]})
            page.send({"action": "height", "minimum": 2, "maximum": 6})
            phase, phase_at = 1, now
        elif phase == 1 and now - phase_at > 3:
            page.save_session_to(str(session_path))
            phase = 2
        elif phase == 2 and session_path.is_file() and not page.editor.busy:
            expected = session_view_state(PointCloudEditSession.load(session_path))
            report["saved_state"] = expected
            report["events"].append("SAVED")
            retired = [worker.stopped_event for worker in (page.worker, page.editor.worker) if worker]
            page.prepare_for_unload()
            phase = 3
        elif phase == 3 and all(event.is_set() for event in retired):
            page.close()
            page.deleteLater()
            page = PointCloudPage()
            page.resize(760, 680)
            page.show()
            page.load_session_from(str(session_path))
            phase, phase_at = 4, now
        elif phase == 4 and state and page._restore_after_open is None and now - phase_at > 8:
            actual = {"camera": state["camera"], "mode": state["mode"], "classes": state.get("classes"),
                      "height_filter": state.get("height_filter")}
            camera_match = all(abs(a - b) < 1e-5 for a, b in zip(actual["camera"]["position"], expected["camera"]["position"]))
            camera_match &= all(abs(actual["camera"][key] - expected["camera"][key]) < 1e-5 for key in ("yaw", "pitch", "radius"))
            if camera_match and all(actual[key] == expected[key] for key in ("mode", "classes", "height_filter")):
                report["restored_state"] = actual
                report["events"].append("RESTORED_AFTER_PAGE_RECREATION")
                report["viewer_run_dir"] = page.last_run_folder
                finish()

    def unhandled(kind, error, tb):
        import traceback
        report["traceback"] = "".join(traceback.format_exception(kind, error, tb))
        finish(str(error))

    sys.excepthook = unhandled
    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(200)
    code = app.exec() if hasattr(app, "exec") else app.exec_()
    app.exitQgis()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
