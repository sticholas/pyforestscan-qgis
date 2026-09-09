"""Deterministic real-QGIS viewer smoke. Does not alter a QGIS profile.

Run with the selected QGIS Python. Evidence is written only to --output-dir.
Camera commands exercise Potree's existing controls; human mouse QA is separate.
"""
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
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=65)
    parser.add_argument("--no-captures", action="store_true")
    parser.add_argument("--point-sizes", nargs="+", type=int, choices=range(17))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    from qgis.core import QgsApplication, Qgis
    from qgis.PyQt.QtCore import QTimer, qVersion
    from pyforestscan_qgis.ui.point_cloud_page import PointCloudPage
    from pyforestscan_qgis.core.atomic_state import atomic_write_json

    app = QgsApplication([str(value).encode() for value in sys.argv], True)
    app.initQgis()
    started = time.monotonic()
    report = {"source": str(args.source), "QGIS_version": Qgis.QGIS_VERSION, "Qt_version": qVersion(),
              "steps": [], "errors": [], "first_frame_seconds": None, "passed": False}
    report["memory_samples"] = []
    # Fingerprints on large sources are explicitly outside first-frame timing.
    hash_source = args.source.is_file() and args.source.stat().st_size <= 100 * 1024 * 1024
    def fingerprint():
        if not hash_source:
            return None
        return hashlib.sha256(args.source.read_bytes()).hexdigest()
    report["sha256_before"] = fingerprint()
    page = PointCloudPage()
    page.setWindowTitle("PyForestScan deterministic viewer QA")
    page.resize(760, 680)
    page.show()
    page.source.setText(str(args.source))
    stopped = None
    finished = False
    worker = None
    action_index = 0
    sample = 0
    previous = None
    pending = None
    captures = set()
    commands = [
        ("initial", {"action": "fit"}),
        ("orbit", {"action": "orbit"}),
        ("pan", {"action": "pan"}),
        ("zoom", {"action": "zoom"}),
        ("top", {"action": "top"}),
        ("front", {"action": "front"}),
        ("classification", {"action": "mode", "mode": "Classification"}),
        ("elevation", {"action": "mode", "mode": "Elevation"}),
        ("filtered", {"action": "height", "minimum": 2, "maximum": 6}),
        ("clear_filter", {"action": "clear_filters"}),
    ]
    if args.point_sizes:
        commands.append(("rgb", {"action": "mode", "mode": "RGB"}))
        commands.extend((f"points-{size}", {"action": "point_display", "style": "Circular", "size": size})
                        for size in args.point_sizes)

    def save():
        atomic_write_json(args.output_dir / "harness_run.json", report)

    def exception(kind, error, tb):
        report["errors"].append({"type": kind.__name__, "message": str(error),
                                 "traceback": "".join(traceback.format_exception(kind, error, tb))})
        save()
        finish()

    sys.excepthook = exception

    def observe(value):
        nonlocal action_index, sample, previous, pending
        if value.get("diagnostics_path"):
            report["viewer_run_dir"] = value["diagnostics_path"]
        if value.get("error"):
            report["errors"].append(value["error"])
        if value.get("screenshot"):
            shot = value["screenshot"]
            captures.add(shot["name"])
            report.setdefault("screenshots", []).append(shot)
        telemetry = value.get("telemetry", {})
        if worker and worker.run_record and telemetry:
            from windows_viewer_memory import tree_memory
            memory = tree_memory(worker.run_record.data.get("viewer_pid"))
            if memory:
                report["memory_samples"].append({"seconds": round(time.monotonic() - started, 3), **memory})
                report["peak_sampled_private_bytes"] = max(report.get("peak_sampled_private_bytes", 0), memory["private_bytes"])
                report["peak_sampled_working_set_bytes"] = max(report.get("peak_sampled_working_set_bytes", 0), memory["working_set_bytes"])
        if telemetry.get("errors"):
            report["errors"].extend(telemetry["errors"])
        if not telemetry.get("ready") or telemetry.get("displayed", 0) <= 0:
            return
        if report["first_frame_seconds"] is None:
            report["first_frame_seconds"] = round(time.monotonic() - started, 3)
        sample += 1
        if pending is not None and sample >= 3:
            name, command = pending
            camera = telemetry["camera"]
            passed = True
            if name == "orbit":
                passed = abs(camera["yaw"] - previous["camera"]["yaw"]) > .01
            elif name == "pan":
                passed = any(abs(a - b) > .01 for a, b in zip(camera["position"], previous["camera"]["position"]))
            elif name == "zoom":
                passed = camera["radius"] < previous["camera"]["radius"] * .95
            elif name in ("classification", "elevation", "rgb"):
                passed = telemetry["mode"] == command["mode"]
            elif name.startswith("points-"):
                material = telemetry.get("render_diagnostics", {})
                passed = (telemetry.get("point_size") == command["size"] and
                          material.get("point_shape") == 1 and
                          material.get("point_size_type") == (2 if command["size"] == 0 else 0) and
                          (command["size"] == 0 or material.get("point_size") == command["size"]))
            report["steps"].append({"name": name, "passed": passed, "before": previous, "after": telemetry})
            if not args.no_captures:
                page.send({"action": "capture", "name": name})
            pending = None
            action_index += 1
            save()
        if pending is None and action_index < len(commands):
            previous = telemetry
            pending = commands[action_index]
            sample = 0
            page.send(pending[1])
        if action_index == len(commands) and (args.no_captures or all(name in captures for name, _ in commands)):
            finish()

    def finish():
        nonlocal finished, stopped
        if finished:
            return
        finished = True
        deadline.stop()
        report["sha256_after"] = fingerprint()
        report["duration"] = round(time.monotonic() - started, 3)
        report["status"] = page.status.text()
        owned = [w for w in (page.worker, page.editor.worker, page.linked.query_worker,
                 *(entry["worker"] for entry in page.linked.residents.parked.values()),
                 *(view.worker for view in page.linked.detached.values())) if w]
        stopped = [w.stopped_event for w in owned]
        page.prepare_for_unload()
        save()
        closing_started = time.monotonic()
        def complete():
            if not all(event.is_set() for event in stopped):
                if time.monotonic() - closing_started > 15:
                    report["errors"].append("Worker shutdown exceeded 15 seconds.")
                    save()
                QTimer.singleShot(100, complete)
                return
            record = worker.run_record.data if worker and worker.run_record else {}
            report["viewer_exit_code"] = record.get("exit_code")
            report["passed"] = (len(report["steps"]) == len(commands) and all(s["passed"] for s in report["steps"])
                                and not report["errors"] and report["sha256_before"] == report["sha256_after"]
                                and record.get("exit_code") == 0)
            save()
            print(json.dumps({"passed": report["passed"], "steps": len(report["steps"]),
                              "errors": report["errors"], "viewer_exit_code": record.get("exit_code"),
                              "evidence": str(args.output_dir / "harness_run.json")}), flush=True)
            page.close()
            app.exit(0 if report["passed"] else 1)
        complete()

    page.start_source(str(args.source))
    worker = page.worker
    # Keep only Python-owned state after Qt deletes the worker wrapper.
    worker.update.connect(observe)
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(finish)
    deadline.start(args.seconds * 1000)
    code = app.exec() if hasattr(app, "exec") else app.exec_()
    app.exitQgis()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
