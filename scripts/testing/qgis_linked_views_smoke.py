"""Real isolated QGIS linked-view canary; does not substitute for human gestures."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--center", nargs=2, type=float, default=(2,2))
    parser.add_argument("--width", type=float, default=8)
    parser.add_argument("--hag", action="store_true")
    parser.add_argument("--detach", action="store_true")
    parser.add_argument("--transfer-cycles", type=int, default=0)
    parser.add_argument("--selection-hag", nargs=2, type=float)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
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
    started = time.monotonic()
    report = {"qgis":Qgis.QGIS_VERSION,"steps":[],"errors":[],"human_acceptance":"NOT_EXECUTED"}
    step = 0
    detail = profile = None
    original_worker = None
    previous = None
    renderers = {}
    switch_started = None
    transferred_worker = None
    transfer_started = None
    cycle_stage = "detach"
    cycles = 0
    x,y = args.center
    d = args.width/4
    ending = False

    def finish():
        nonlocal ending
        if ending:
            return
        ending = True
        timer.stop()
        workers = [w for w in (page.worker,page.editor.worker,page.linked.query_worker,
                   *(entry["worker"] for entry in page.linked.residents.parked.values()),
                   *(window.worker for window in page.linked.detached.values())) if w]
        events = [w.stopped_event for w in workers]
        page.prepare_for_unload()
        def drain():
            if not all(event.is_set() for event in events):
                QTimer.singleShot(100,drain)
                return
            report["passed"] = step == (22 if args.detach else 15) and not report["errors"]
            report["elapsed_seconds"] = time.monotonic()-started
            (args.output_dir/"linked.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
            print(json.dumps(report),flush=True)
            page.close()
            app.exit(0 if report["passed"] else 1)
        drain()

    def switch(key):
        nonlocal switch_started
        switch_started = time.monotonic()
        page.view_tabs.setCurrentIndex(next(i for i in range(page.view_tabs.count()) if page.view_tabs.tabData(i)==key))
        page.send({"action":"snapshot", "request_id":"warm-"+key})

    def apply_limits():
        if args.selection_hag:
            limits = page.linked.limits
            limits.mode.setCurrentIndex(limits.mode.findData("hag_filter"))
            limits.minimum.setValue(args.selection_hag[0])
            limits.maximum.setValue(args.selection_hag[1])
            assert page.linked.depth == {"hag_filter": args.selection_hag}

    def tick():
        nonlocal step,detail,profile,original_worker,previous,transferred_worker,transfer_started,cycle_stage,cycles
        try:
            if time.monotonic()-started > 480:
                raise TimeoutError(page.status.text()+" | "+page.editor.summary.text())
            if "needs attention" in page.status.text() or "unavailable:" in page.status.text():
                report["viewer_log"] = page.last_run_folder
                raise RuntimeError(page.status.text())
            editor = page.editor
            if not editor.viewer_ready or editor.busy or not editor.state.get("ready") or page.linked.waiting:
                return
            if page.linked.rendered_id != page.workspace.active_view_id:
                return
            if original_worker:
                assert editor.worker is original_worker, "Linked view replaced authoritative editor"
            if step == 0:
                page.linked.set_depth({"z_filter": [20, 10]})
                assert not editor.tool.isEnabled()
                page.linked.set_depth({})
                apply_limits()
                report["requested_hag_limits"] = args.selection_hag
                with patch.object(page.linked, "draw") as draw:
                    page.linked.area_button.click()
                    draw.assert_called_with("Rectangle", "CREATE_AREA")
                    page.linked.slice_button.click()
                    draw.assert_called_with("Line", "CREATE_SLICE")
                assert not page.linked.area_button.icon().isNull()
                assert not page.linked.slice_button.icon().isNull()
                original_worker = editor.worker
                renderers["overview"] = page.worker
                detail = page.linked.add(ViewType.AREA_DETAIL,
                    {"shape":"RECTANGLE","center":[x,y],"width":args.width,"height":args.width,"crs":editor.state["source_crs"]})
            elif step == 1:
                if page.linked.rendered_id != detail:
                    return
                page.grab().save(str(args.output_dir/"area.png"))
                report["area_telemetry"] = page._view_state
                previous = (editor.state.get("selection") or {}).get("selection_id")
                editor.tool.buttons["Rectangle"].click()
                page.send({"action":"selection_test","geometry":[[x-d,y-d],[x+d,y-d],[x+d,y+d],[x-d,y+d],[x-d,y-d]]})
            elif step == 2:
                result = editor.state.get("selection") or {}
                if result.get("selection_id") == previous:
                    return
                assert result["resolved_point_count"] > 0
                report["area_selection"] = result
                if args.selection_hag:
                    assert result["hag_min"] >= args.selection_hag[0]
                    assert result["hag_max"] <= args.selection_hag[1]
                editor.stage("Classification",2)
            elif step == 3:
                assert editor.state["edits"] == 1
                profile = page.linked.add(ViewType.VERTICAL_SLICE,
                    {"a":[x-args.width/2,y],"b":[x+args.width/2,y],"thickness":4,"crs":editor.state["source_crs"],
                     "vertical_axis":"HeightAboveGround" if args.hag else "Z"})
            elif step == 4:
                if page.linked.rendered_id != profile:
                    return
                page.grab().save(str(args.output_dir/"slice.png"))
                report["slice_telemetry"] = page._view_state
                renderers[profile] = page.worker
                previous = (editor.state.get("selection") or {}).get("selection_id")
                low,high = page._view_state["z_range"]
                editor.tool.buttons["Polygon"].click()
                page.send({"action":"selection_test","geometry":[[d,low],[3*d,low],[3*d,high],[d,high],[d,low]]})
            elif step == 5:
                result = editor.state.get("selection") or {}
                if result.get("selection_id") == previous:
                    return
                assert result["resolved_point_count"] > 0
                report["slice_selection"] = result
                if args.selection_hag:
                    assert result["hag_min"] >= args.selection_hag[0]
                    assert result["hag_max"] <= args.selection_hag[1]
                editor.stage("Classification",7)
            elif step == 6:
                assert editor.state["edits"] == 2
                switch("overview")
            elif step == 7:
                if page.linked.rendered_id != "overview":
                    return
                assert page.worker is renderers["overview"], "Overview renderer was restarted"
                if page._view_state.get("request_id") != "warm-overview":
                    return
                assert page._view_state["render_diagnostics"]["rendered_points"] > 0
                report["warm_overview_log"] = str(page.worker.run_record.folder)
                page.send({"action":"capture", "name":"warm-overview"})
                report["warm_overview_seconds"] = time.monotonic()-switch_started
                editor.send("undo")
            elif step == 8:
                assert editor.state["edits"] == 1
                editor.send("redo")
            elif step == 9:
                assert editor.state["edits"] == 2
                switch(profile)
            elif step == 10:
                if page.linked.rendered_id != profile:
                    return
                assert page.worker is renderers[profile], "Slice renderer was restarted"
                if page._view_state.get("request_id") != "warm-"+profile:
                    return
                assert page._view_state["render_diagnostics"]["rendered_points"] > 0
                report["warm_slice_log"] = str(page.worker.run_record.folder)
                page.send({"action":"capture", "name":"warm-slice"})
                report["warm_slice_seconds"] = time.monotonic()-switch_started
                editor.save_to(str(args.output_dir/"session.json"))
            elif step == 11:
                if not (args.output_dir/"session.json").is_file():
                    return
                original_worker = None
                editor.load(str(args.output_dir/"session.json"))
            elif step == 12:
                if page.linked.rendered_id != profile:
                    return
                assert editor.state["edits"] == 2
                assert page.view_tabs.count() == 3
                original_worker = editor.worker
                report["restored_selection"] = editor.state["selection"]
                if args.selection_hag:
                    assert page.linked.depth == {"hag_filter": args.selection_hag}, "Saved limits were not restored"
                editor.send("export",path=str(args.output_dir/"edited.laz"))
            elif step == 13:
                if not editor.state.get("exported"):
                    return
                report["export"] = editor.state["exported"]
                editor.exportReady.connect(lambda value: report.update(handoff=value))
                editor.use_export()
            elif step == 14:
                if "handoff" not in report:
                    return
                if cycles < args.transfer_cycles:
                    if cycle_stage == "detach":
                        transferred_worker = page.worker
                        page.linked.detach_button.click()
                        cycle_stage = "dock"
                    elif cycle_stage == "dock":
                        window = page.linked.detached[profile]
                        assert window.worker is transferred_worker
                        if getattr(window.worker, "_surface_transfer", None):
                            return
                        report.setdefault("transfer_cycles", []).append({"detach": window.worker.surface_transfer_seconds})
                        page.linked.dock(profile)
                        cycle_stage = "finish"
                    else:
                        assert page.worker is transferred_worker
                        if getattr(page.worker, "_surface_transfer", None):
                            return
                        report["transfer_cycles"][-1]["dock"] = page.worker.surface_transfer_seconds
                        cycles += 1
                        cycle_stage = "detach"
                    return
            elif step == 15:
                if args.detach:
                    transferred_worker = page.worker
                    transfer_started = time.monotonic()
                    assert page.linked.detach_button.accessibleName() == "Detach View"
                    assert not page.linked.detach_button.icon().isNull()
                    page.linked.detach_button.click()
                else:
                    finish()
                    return
            elif step == 16:
                window = page.linked.detached[profile]
                if args.selection_hag:
                    assert window.limits.minimum.value() == args.selection_hag[0]
                    assert window.limits.maximum.value() == args.selection_hag[1]
                assert window.worker is transferred_worker, "Detaching restarted the renderer"
                if getattr(window.worker, "_surface_transfer", None):
                    return
                if window.telemetry.get("editor",{}).get("view_id") != profile:
                    return
                report["detach_seconds"] = time.monotonic()-transfer_started
                report["detach_ack_seconds"] = window.worker.surface_transfer_seconds
                report["detached_view_log"] = str(window.worker.run_record.folder)
                previous = editor.state["selection"]["selection_id"]
                low,high = window.telemetry["z_range"]
                window.send({"action":"capture","name":"detached-profile"})
                window.tool.buttons["Polygon"].click()
                window.send({"action":"selection_test","geometry":[[d,low],[3*d,low],[3*d,high],[d,high],[d,low]]})
            elif step == 17:
                if editor.state["selection"]["selection_id"] == previous:
                    return
                assert editor.state["selection"]["resolved_point_count"] == report["slice_selection"]["resolved_point_count"]
                editor.stage("Classification",9)
            elif step == 18:
                assert editor.state["edits"] == 3
                transfer_started = time.monotonic()
                page.linked.dock(profile)
            elif step == 19:
                if page.linked.rendered_id != profile:
                    return
                assert page.worker is transferred_worker, "Docking restarted the renderer"
                if getattr(page.worker, "_surface_transfer", None):
                    return
                report["dock_seconds"] = time.monotonic()-transfer_started
                report["dock_ack_seconds"] = page.worker.surface_transfer_seconds
                page.send({"action":"capture","name":"redocked-profile"})
                assert page.view_tabs.count() == 3
                assert not page.linked.detached
                editor.send("export",path=str(args.output_dir/"detached-edited.laz"))
            elif step == 20:
                if editor.state.get("exported",{}).get("staged_operations") != 3:
                    return
                report["detached_export"] = editor.state["exported"]
                editor.send("undo")
            elif step == 21:
                assert editor.state["edits"] == 2
            elif step == 22:
                finish()
                return
            report["steps"].append({"step":step,"elapsed":time.monotonic()-started})
            (args.output_dir/"progress.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
            print(json.dumps({"step":step,"elapsed":time.monotonic()-started}),flush=True)
            step += 1
        except Exception:
            report["errors"].append(traceback.format_exc())
            finish()
    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(250)
    return app.exec() if hasattr(app,"exec") else app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
