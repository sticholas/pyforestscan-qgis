"""Live read-only EPT linked-view qualification; never enables an editor."""
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
    parser.add_argument("--center", nargs=2, type=float, required=True)
    args = parser.parse_args()
    if args.source.name.lower() != "ept.json":
        parser.error("This qualification requires EPT metadata.")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    before = hashlib.sha256(args.source.read_bytes()).hexdigest()
    from qgis.core import QgsApplication, Qgis
    from qgis.PyQt.QtCore import QTimer
    from pyforestscan_qgis.ui.point_cloud_page import PointCloudPage
    from pyforestscan_qgis.core.point_cloud.workspace import ViewType
    app = QgsApplication([], True)
    app.initQgis()
    page = PointCloudPage()
    page.resize(1000, 900)
    page.show()
    page.source.setText(str(args.source))
    page.start_source(str(args.source))
    start = time.monotonic()
    report = {"qgis": Qgis.QGIS_VERSION, "source": str(args.source),
              "metadata_sha256": before, "identity_scope": "EPT_METADATA_ONLY",
              "human_acceptance": "NOT_EXECUTED", "steps": [], "errors": []}
    stage = 0
    ending = False
    area = profile = overview = retained = None
    captures = {}

    def finish():
        nonlocal ending
        if ending:
            return
        ending = True
        timer.stop()
        workers = [w for w in (page.worker, page.editor.worker, page.linked.query_worker,
                   *(e["worker"] for e in page.linked.residents.parked.values()),
                   *(v.worker for v in page.linked.detached.values())) if w]
        stopped = [w.stopped_event for w in workers]
        page.prepare_for_unload()
        def drain():
            if not all(e.is_set() for e in stopped):
                QTimer.singleShot(100, drain)
                return
            report["metadata_unchanged"] = hashlib.sha256(args.source.read_bytes()).hexdigest() == before
            report["passed"] = stage == 7 and not report["errors"] and report["metadata_unchanged"]
            report["elapsed_seconds"] = time.monotonic() - start
            (args.output_dir / "ept-linked.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report), flush=True)
            page.close()
            app.exit(0 if report["passed"] else 1)
        drain()

    def activate(key):
        page.view_tabs.setCurrentIndex(next(i for i in range(page.view_tabs.count())
                                           if page.view_tabs.tabData(i) == key))

    def tick():
        nonlocal stage, area, profile, overview, retained
        try:
            if time.monotonic() - start > 180:
                raise TimeoutError(page.status.text())
            assert page.editor.worker is None, "EPT started an authoritative editor"
            assert not page.editor.export_button.isEnabled()
            assert not page.editor.tool.isEnabled()
            state = page._view_state or {}
            if not state.get("ready") or page.linked.waiting or page.linked.rendered_id != page.workspace.active_view_id:
                return
            if not state.get("render_diagnostics", {}).get("rendered_points"):
                return
            x, y = args.center
            if stage == 0:
                overview = page.worker
                crs = page.linked.source_crs()
                assert crs
                area = page.linked.add(ViewType.AREA_DETAIL, {"shape": "RECTANGLE",
                    "center": [x, y], "width": 30, "height": 30, "crs": crs})
            elif stage == 1:
                assert page.linked.rendered_id == area
                captures["area"] = str(page.worker.run_record.folder / "ept-area.png")
                page.send({"action": "capture", "name": "ept-area"})
                report["area_points"] = state["render_diagnostics"]["rendered_points"]
                profile = page.linked.add(ViewType.VERTICAL_SLICE, {"a": [x-15, y],
                    "b": [x+15, y], "thickness": 5, "crs": page.linked.source_crs()})
            elif stage == 2:
                assert page.linked.rendered_id == profile
                retained = page.worker
                report["slice_points"] = state["render_diagnostics"]["rendered_points"]
                captures["slice"] = str(page.worker.run_record.folder / "ept-slice.png")
                page.send({"action": "capture", "name": "ept-slice"})
                activate("overview")
            elif stage == 3:
                assert page.worker is overview
                activate(profile)
            elif stage == 4:
                assert page.worker is retained
                page.linked.detach_button.click()
            elif stage == 5:
                window = page.linked.detached[profile]
                assert not window.tool.isEnabled()
                assert not window.classify_button.isEnabled()
                assert not window.action_buttons["undo"].isEnabled()
                assert not window.action_buttons["redo"].isEnabled()
                if getattr(retained, "_surface_transfer", None):
                    return
                assert window.worker is retained
                page.linked.dock(profile)
            elif stage == 6:
                if getattr(retained, "_surface_transfer", None):
                    return
                assert page.worker is retained
                if not all(Path(path).is_file() for path in captures.values()):
                    return
                report["captures"] = captures
            report["steps"].append({"stage": stage, "elapsed": time.monotonic()-start})
            stage += 1
            if stage == 7:
                finish()
        except Exception:
            report["errors"].append(traceback.format_exc())
            finish()

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(250)
    return app.exec() if hasattr(app, "exec") else app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
