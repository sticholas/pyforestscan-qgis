"""Deliberate owned-child failure, reload and compact-width checks in QGIS Qt."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
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
    from pyforestscan_qgis.ui.mission_control import MissionControlDock
    from pyforestscan_qgis.core.backend.service import BackendService
    from pyforestscan_qgis.core.backend.process_env import hidden_subprocess_kwargs
    from pyforestscan_qgis.core.atomic_state import atomic_write_json

    app = QgsApplication([v.encode() for v in sys.argv], True)
    app.initQgis()
    dock = MissionControlDock(None)
    dock.resize(1000, 900)
    dock.show()
    dock._navigate_to("Point Cloud")
    page = dock.point_cloud_page
    page.source.setText(str(args.source))
    page.start_source(str(args.source))
    before = BackendService().processing_engine_state(quick=True)
    report = {"passed": False, "engine_before": before.status.value, "widths": [], "events": []}
    started = time.monotonic()
    phase = 0
    phase_at = started
    killed_record = None
    widths = iter((420, 600, 760, 1100, 1400))

    def finish(error=None):
        timer.stop()
        worker = page.worker
        stopped = worker.stopped_event if worker else None
        record = worker.run_record if worker else None
        dock.prepare_for_unload()
        deadline = time.monotonic() + 15

        def complete():
            if stopped and not stopped.is_set():
                if time.monotonic() > deadline:
                    raise RuntimeError("Owned viewer did not stop within the shutdown deadline.")
                QTimer.singleShot(100, complete)
                return
            report["error"] = error
            report["final_viewer_exit_code"] = record.data["exit_code"] if record else None
            report["passed"] = error is None and report["final_viewer_exit_code"] == 0
            report["duration"] = round(time.monotonic() - started, 3)
            atomic_write_json(args.output_dir / "failure_isolation.json", report)
            print(json.dumps(report), flush=True)
            dock.close()
            app.exit(0 if report["passed"] else 1)
        complete()

    def tick():
        nonlocal phase, phase_at, killed_record
        now = time.monotonic()
        if now - started > 90:
            finish(f"Timed out in phase {phase}: {page.status.text()}")
            return
        if phase == 0 and page._view_state and page._view_state.get("displayed"):
            if now - phase_at < 2:
                return
            width = next(widths, None)
            if width is not None:
                page.setFixedWidth(width)
                page.filter_toggle.setChecked(True)
                phase_at = now
                QTimer.singleShot(250, lambda w=width: capture_width(w))
                return
            page.filter_toggle.setChecked(False)
            killed_record = page.worker.run_record
            # Kill only this harness-owned renderer and its child processes.
            command = ["taskkill", "/PID", str(killed_record.data["viewer_pid"]), "/T", "/F"]
            result = subprocess.run(command, capture_output=True, text=True, timeout=10, **hidden_subprocess_kwargs())
            if result.returncode:
                finish("Could not terminate the owned test viewer: " + result.stderr)
                return
            report["events"].append("OWNED_VIEWER_TREE_TERMINATED")
            phase = 1
        elif phase == 1 and page.worker is None:
            report["failure_message"] = page.status.text()
            report["failed_run"] = str(killed_record.folder)
            report["failed_exit_code"] = killed_record.data["exit_code"]
            if page.save_session_button.isEnabled() or any(b.isEnabled() for b in page.view_buttons):
                finish("Viewer controls remained enabled after forced termination.")
                return
            report["process_navigation"] = dock._navigate_to("Process")
            dock.results_page.refresh_results()
            report["tools_navigation"] = dock._navigate_to("Tools & Setup")
            after = BackendService().processing_engine_state(quick=True)
            report["engine_after"] = after.status.value
            if after.status != before.status or not report["process_navigation"] or not report["tools_navigation"]:
                finish("Viewer failure changed protected Process availability.")
                return
            dock._navigate_to("Point Cloud")
            page.setFixedWidth(760)
            page.start_source(str(args.source))
            report["events"].append("RELOAD_REQUESTED")
            phase, phase_at = 2, now
        elif phase == 2 and page._view_state and page._view_state.get("displayed") and now - phase_at > 3:
            report["events"].append("RELOAD_RENDERED")
            if not all(item["controls_fit"] for item in report["widths"]):
                finish("Visible controls overflowed a tested page width.")
            else:
                finish()

    def capture_width(width):
        controls = [page.open_button, page.mode, page.navigation_mode, page.class_list,
                    page.solo_class_button, page.show_classes_button, page.height_min, page.height_max,
                    page.save_session_button, page.load_session_button, page.diagnostics_button]
        from qgis.PyQt.QtCore import QPoint
        fits = all(c.mapTo(page, QPoint(0, 0)).x() >= 0 and
                   c.mapTo(page, QPoint(c.width(), 0)).x() <= page.width() for c in controls)
        report["widths"].append({"requested": width, "actual": page.width(), "controls_fit": fits,
                                 "viewer_height": page.surface.height(), "viewer_width": page.surface.width()})
        page.grab().save(str(args.output_dir / f"page-{width}.png"))

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
