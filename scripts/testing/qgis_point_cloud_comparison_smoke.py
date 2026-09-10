"""Real QGIS canary for a source-isolated read-only comparison window."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=180)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    from qgis.core import QgsApplication, Qgis
    from qgis.PyQt.QtCore import QTimer, qVersion
    from pyforestscan_qgis.core.atomic_state import atomic_write_json
    from pyforestscan_qgis.ui.point_cloud_page import PointCloudPage
    from pyforestscan_qgis.ui.point_cloud_comparison import ComparisonView

    app = QgsApplication([], True)
    app.initQgis()
    source_hash = lambda: hashlib.sha256(args.source.read_bytes()).hexdigest()
    report = {"source":str(args.source), "qgis":Qgis.QGIS_VERSION,
              "qt":qVersion(), "sha256_before":source_hash(), "errors":[],
              "passed":False}
    page = PointCloudPage()
    page.resize(700, 600)
    page.show()
    comparison = ComparisonView(page.linked, "c" * 32, args.source)
    worker = comparison.worker
    started = time.monotonic()
    ready_samples = 0
    mode_sent = False
    ending = False

    def save():
        atomic_write_json(args.output, report)

    def finish(error=None):
        nonlocal ending
        if ending:
            return
        ending = True
        deadline.stop()
        if error:
            report["errors"].append(str(error))
        report["sha256_after"] = source_hash()
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        stopped = worker.stopped_event
        comparison.close()
        page.prepare_for_unload()
        closing = time.monotonic()
        def drain():
            if not stopped.is_set() and time.monotonic() - closing < 20:
                QTimer.singleShot(100, drain)
                return
            record = worker.run_record.data if worker.run_record else {}
            report["viewer_exit_code"] = record.get("exit_code")
            report["passed"] = bool(
                report.get("first_frame_seconds") is not None
                and report.get("source_record", {}).get("authority") == "READ_ONLY_INDEPENDENT_SOURCE"
                and report.get("editor_command_rejected")
                and report.get("display_mode") == "Elevation"
                and report["sha256_before"] == report["sha256_after"]
                and stopped.is_set() and record.get("exit_code") == 0
                and not report["errors"])
            save()
            print(json.dumps({"passed":report["passed"], "evidence":str(args.output),
                              "errors":report["errors"]}), flush=True)
            page.close()
            app.exit(0 if report["passed"] else 1)
        drain()

    def observe(value):
        nonlocal ready_samples, mode_sent
        try:
            if value.get("error"):
                finish(value["error"])
                return
            telemetry = value.get("telemetry") or {}
            if not telemetry.get("ready") or telemetry.get("displayed", 0) <= 0:
                return
            if comparison.source_record and "source_record" not in report:
                report["source_record"] = {
                    "fingerprint":comparison.source_record.source_fingerprint,
                    "source_type":comparison.source_record.source_type,
                    "point_count":comparison.source_record.point_count,
                    "authority":comparison.source_record.authority,
                }
            if "first_frame_seconds" not in report:
                report["first_frame_seconds"] = round(time.monotonic() - started, 3)
                try:
                    comparison.send({"action":"editor_overlay", "path":"primary-editor.json"})
                except ValueError:
                    report["editor_command_rejected"] = True
            if not mode_sent:
                comparison.mode.setCurrentText("Elevation")
                comparison.send({"action":"fit"})
                mode_sent = True
                return
            if telemetry.get("mode") != "Elevation":
                return
            ready_samples += 1
            if ready_samples >= 3 and report.get("source_record"):
                report["display_mode"] = telemetry["mode"]
                report["displayed_points"] = telemetry.get("render_diagnostics", {}).get(
                    "rendered_points", telemetry.get("displayed"))
                report["source_buffers_unchanged"] = telemetry.get(
                    "editor", {}).get("source_buffers_unchanged")
                finish()
        except Exception as error:
            report["errors"].append("".join(traceback.format_exception_only(type(error), error)).strip())
            finish()

    worker.update.connect(observe)
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(lambda:finish("Comparison smoke timed out."))
    deadline.start(args.seconds * 1000)
    code = app.exec() if hasattr(app, "exec") else app.exec_()
    app.exitQgis()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
