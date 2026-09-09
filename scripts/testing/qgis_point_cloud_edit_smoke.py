"""Isolated real-QGIS editor wiring canary; deterministic geometry is not mouse QA."""
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
    parser.add_argument("--plugin-root", type=Path)
    parser.add_argument('--stress-cycles', type=int, choices=(0, 100), default=0)
    args = parser.parse_args()
    if args.plugin_root:
        sys.path.insert(0, str(args.plugin_root.resolve()))
    args.output_dir.mkdir(parents=True, exist_ok=False)
    if args.source.stat().st_size > 100_000_000:
        raise ValueError("This bounded fixture harness is for small sources only.")
    from qgis.core import QgsApplication, Qgis
    from qgis.PyQt.QtCore import QTimer
    from pyforestscan_qgis.ui.point_cloud_page import PointCloudPage
    from pyforestscan_qgis.core.atomic_state import atomic_write_json
    app = QgsApplication([], True)
    app.initQgis()
    page = PointCloudPage()
    import inspect
    imported_page = Path(inspect.getfile(PointCloudPage)).resolve()
    if args.plugin_root:
        assert imported_page.is_relative_to(args.plugin_root.resolve()), "Did not import the extracted package."
    page.resize(760, 850)
    page.show()
    app.processEvents()
    canvas_before_filters = (page.surface.width(), page.surface.height())
    page.filter_toggle.setChecked(True)
    app.processEvents()
    canvas_with_filters = (page.surface.width(), page.surface.height())
    page.filter_toggle.setChecked(False)
    assert canvas_before_filters == canvas_with_filters, "Display filters resized the viewer canvas."
    page.source.setText(str(args.source))
    report = {"qgis": Qgis.QGIS_VERSION, "steps": [], "errors": [],
              "source_sha_before": hashlib.sha256(args.source.read_bytes()).hexdigest(),
              "human_drawing_test": "NOT_EXECUTED", "imported_page": str(imported_page),
              "canvas_before_filters": canvas_before_filters, "canvas_with_filters": canvas_with_filters}
    page.editor.exportReady.connect(lambda value: report.update(verified_handoff=value))
    started = time.monotonic()
    step = 0
    stress_phase = 0
    stress_completed = 0
    previous_selection = None
    widths = iter((420, 600, 760, 1100, 1400))
    pending_width = None
    finished = False
    session_path = args.output_dir / "session.json"
    export_path = args.output_dir / "edited.laz"
    page.start_source(str(args.source))

    def finish():
        nonlocal finished
        if finished:
            return
        finished = True
        timer.stop()
        workers = [worker for worker in (page.worker, page.editor.worker) if worker]
        events = [worker.stopped_event for worker in workers]
        page.prepare_for_unload()
        def close():
            if not all(event.is_set() for event in events):
                QTimer.singleShot(100, close)
                return
            report["source_sha_after"] = hashlib.sha256(args.source.read_bytes()).hexdigest()
            report['stress_cycles_completed'] = stress_completed
            report["passed"] = (step == 10 and stress_completed == args.stress_cycles and not report["errors"] and
                                report["source_sha_before"] == report["source_sha_after"])
            atomic_write_json(args.output_dir / "editor_ui_acceptance.json", report)
            print(json.dumps(report), flush=True)
            page.close()
            app.exit(0 if report["passed"] else 1)
        close()

    def tick():
        nonlocal step, pending_width, stress_phase, stress_completed, previous_selection
        try:
            if time.monotonic() - started > 120 + args.stress_cycles * 12:
                raise TimeoutError("Editor canary timed out: " + page.editor.summary.text())
            editor = page.editor
            if step == 8 and report.get("waiting_for_viewer_exit") and page.worker is not None:
                return
            if step == 8 and page.worker is None:
                assert editor.state["edits"] == 1 and Path(editor.state["autosave"]).is_file()
                report["waiting_for_viewer_exit"] = False
                page.start_source(str(args.source))
                return
            if editor.summary.text().startswith("Point Cloud editor:"):
                raise RuntimeError(editor.summary.text())
            if editor.busy or not editor.viewer_ready or not editor.state.get("ready"):
                return
            if step == 10:
                if stress_completed == args.stress_cycles:
                    finish()
                    return
                if stress_phase == 0:
                    previous_selection = (editor.state.get('selection') or {}).get('selection_id')
                    page.send({'action': 'selection_test', 'geometry': [[0,0],[4,0],[4,4],[0,4],[0,0]]})
                elif stress_phase == 1:
                    selected = editor.state.get('selection') or {}
                    if selected.get('selection_id') == previous_selection:
                        return
                    assert selected.get('resolved_point_count') == 814
                    attribute, value = (('Classification', 2), ('Classification', 7),
                                        ('Withheld', 1), ('DELETE_ON_EXPORT', 1))[stress_completed % 4]
                    editor.stage(attribute, value)
                elif stress_phase == 2:
                    assert editor.state['edits'] == stress_completed + 2
                    editor.send('undo')
                elif stress_phase == 3:
                    assert editor.state['edits'] == stress_completed + 1
                    editor.send('redo')
                else:
                    assert editor.state['edits'] == stress_completed + 2
                    telemetry = (page._view_state or {}).get('editor', {})
                    if telemetry.get('pending_nodes') or telemetry.get('revision') != editor.state['revision']:
                        return
                    assert telemetry['source_buffers_unchanged']
                    assert Path(editor.state['autosave']).is_file()
                    stress_completed += 1
                    if stress_completed % 10 == 0:
                        print(json.dumps({'stress_cycles': stress_completed}), flush=True)
                stress_phase = (stress_phase + 1) % 5
                return
            if step == 0:
                page._sync_classes([5])
                page.send({"action": "classes", "classes": [5]})
                page.send({"action": "selection_test",
                           "geometry": [[0,0],[4,0],[4,4],[0,4],[0,0]]})
            elif step == 1:
                count = (editor.state.get("selection") or {}).get("resolved_point_count", 0)
                if not count:
                    return
                assert 0 < count < editor.state["point_count"] * .25
                report["selected"] = count
                if pending_width is not None:
                    from qgis.PyQt.QtCore import QPoint
                    from qgis.PyQt.QtWidgets import QWidget
                    overflow = [control.objectName() or type(control).__name__ for control in editor.findChildren(QWidget)
                        if control.isVisible() and not control.isWindow() and
                        control.mapTo(page, QPoint(0, 0)).x() + control.width() > page.width()]
                    report.setdefault("widths", []).append({"width": pending_width, "overflow": overflow})
                    page.grab().save(str(args.output_dir / f"editing-{pending_width}.png"))
                    assert not overflow, str(overflow)
                pending_width = next(widths, None)
                if pending_width is not None:
                    page.setFixedWidth(pending_width)
                    return
                page.setFixedWidth(760)
                editor.stage("Classification", 2)
            elif step == 2:
                if editor.state["edits"] != 1:
                    return
                telemetry = (page._view_state or {}).get("editor", {})
                if telemetry.get("pending_nodes") or telemetry.get("revision") != editor.state["revision"]:
                    return
                report["staged_overlay"] = telemetry
                assert telemetry["source_buffers_unchanged"]
                assert page._view_state["classes"] == [5], "Staged colors changed the original-class filter."
                page.send({"action": "capture", "name": "editor-staged"})
                editor.send("undo")
            elif step == 3:
                assert editor.state["edits"] == 0 and editor.state["can_redo"]
                editor.send("redo")
            elif step == 4:
                assert editor.state["edits"] == 1
                page.save_session_to(str(session_path))
            elif step == 5:
                if not session_path.exists():
                    return
                editor.send("export", path=str(export_path))
            elif step == 6:
                if not editor.state.get("exported"):
                    return
                report["export"] = editor.state["exported"]
                assert export_path.is_file()
                assert report["export"]["status"] == "VALIDATED"
                assert report["staged_overlay"]["effective_classes"] == report["export"]["classification_counts"], "Resident staged colors differ from full-source export on the fully resident fixture."
                if not report.get("requested_handoff"):
                    report["requested_handoff"] = True
                    editor.use_export()
                    return
                if not report.get("verified_handoff"):
                    return
                assert report["verified_handoff"]["export_id"] == report["export"]["export_id"]
                report["pre_restore_viewer_pid"] = page.worker.run_record.data["viewer_pid"]
                page.load_session_from(str(session_path))
            elif step == 7:
                if (editor.state.get("edits") != 1 or page._restore_expected is not None or
                    page._restore_after_open is not None or page._pending_source or not page.worker or
                    page.worker.run_record.data.get("viewer_pid") == report["pre_restore_viewer_pid"]):
                    return
                assert editor.state["can_undo"]
                import subprocess
                from pyforestscan_qgis.core.backend.process_env import hidden_subprocess_kwargs
                pid = page.worker.run_record.data["viewer_pid"]
                result = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True, text=True, timeout=10, **hidden_subprocess_kwargs())
                assert result.returncode == 0, result.stderr
                report["owned_renderer_terminated_after_edits"] = pid
                report["waiting_for_viewer_exit"] = True
            elif step == 8:
                if page.worker is None or page._pending_source:
                    return
                telemetry = (page._view_state or {}).get("editor", {})
                if telemetry.get("pending_nodes") or telemetry.get("revision") != editor.state["revision"]:
                    return
                report["reload_overlay"] = telemetry
                assert editor.state["edits"] == 1
            elif step == 9:
                from pyforestscan_qgis.ui.pages import BatchPage
                from pyforestscan_qgis.core.adapter import PyForestScanAdapter
                process_page = BatchPage(PyForestScanAdapter(execution_mode="pbm_backend"))
                process_page.output_folder_edit.setText(str(args.output_dir / "science"))
                process_page.use_edited_cloud(report["verified_handoff"])
                assert process_page._selected_paths() == [export_path.resolve()]
                assert process_page.output_folder_edit.text() == str(args.output_dir / "science")
                assert process_page.editor_input_provenance["session_id"] == report["export"]["session_id"]
                assert process_page.batch_thread is None
                process_page.close()
            report["steps"].append(step)
            step += 1
            if step == 10 and not args.stress_cycles:
                finish()
        except Exception as error:
            report["errors"].append({"message": str(error), "traceback": traceback.format_exc()})
            finish()
    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(300)
    code = app.exec() if hasattr(app, "exec") else app.exec_()
    app.exitQgis()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
