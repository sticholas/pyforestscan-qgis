"""Same-page source cycling with owned renderer teardown and state assertions."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import traceback
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', action='append', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--cycles', type=int, default=50)
    args = parser.parse_args()
    if not 1 <= args.cycles <= 100:
        parser.error('Use 1-100 source cycles.')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    from qgis.core import QgsApplication, Qgis
    from qgis.PyQt.QtCore import QTimer
    from pyforestscan_qgis.ui.point_cloud_page import PointCloudPage, _ACTIVE_WORKERS
    from pyforestscan_qgis.ui.point_cloud_editor import _WORKERS
    from pyforestscan_qgis.core.atomic_state import atomic_write_json
    from windows_viewer_memory import tree_memory, process_identity
    app = QgsApplication([], True)
    app.initQgis()
    page = PointCloudPage()
    page.setWindowTitle('Automated source-switch lifecycle QA')
    page.resize(760, 850)
    page.show()
    report = {'qgis': Qgis.QGIS_VERSION, 'cycles': [], 'errors': []}
    index = 0
    started = time.monotonic()
    opened = started
    ready_at = None
    previous = {}
    closing = False

    def open_next():
        nonlocal opened, ready_at
        source = args.source[index % len(args.source)]
        page.source.setText(str(source))
        page.start_source(str(source))
        opened, ready_at = time.monotonic(), None

    def finish():
        nonlocal closing
        if closing:
            return
        closing = True
        timer.stop()
        memory = tree_memory(page.worker.run_record.data.get('viewer_pid')) if page.worker and page.worker.run_record else {}
        previous.update({pid: process_identity(pid) for pid in (memory or {}).get('pids', [])})
        events = [w.stopped_event for w in (page.worker, page.editor.worker) if w]
        page.prepare_for_unload()
        def complete():
            if not all(e.is_set() for e in events):
                QTimer.singleShot(100, complete)
                return
            report['orphan_renderer_pids'] = [pid for pid, birth in previous.items()
                                             if birth is not None and process_identity(pid) == birth]
            report['passed'] = not report['errors'] and not report['orphan_renderer_pids'] and len(report['cycles']) == args.cycles
            report['seconds'] = time.monotonic() - started
            atomic_write_json(args.output_dir / 'source_switch.json', report)
            print(json.dumps({k: v for k, v in report.items() if k != 'cycles'}), flush=True)
            page.close()
            app.exit(0 if report['passed'] else 1)
        complete()

    def tick():
        nonlocal index, ready_at
        try:
            if time.monotonic() - opened > 600:
                raise TimeoutError('Source switch timed out: ' + page.status.text())
            state = page._view_state or {}
            if page._pending_source or not state.get('ready') or not state.get('render_diagnostics', {}).get('rendered_points'):
                return
            source = args.source[index % len(args.source)]
            ept = source.name.lower() == 'ept.json'
            if not ept and (not page.editor.state.get('ready') or page.editor.busy):
                return
            if ready_at is None:
                ready_at = time.monotonic()
            if time.monotonic() - ready_at < 2:
                return
            assert not state.get('errors'), state.get('errors')
            assert state.get('classes') is None and state.get('height_filter') is None
            assert state.get('mode') == 'Classification'
            assert not page.editor.state.get('selection') and not page.editor.state.get('edits')
            assert len(_ACTIVE_WORKERS) == 1 and len(_WORKERS) <= 1
            orphans = [pid for pid, birth in previous.items()
                       if birth is not None and process_identity(pid) == birth]
            assert not orphans, f'Previous renderer processes survived: {orphans}'
            memory = tree_memory(page.worker.run_record.data.get('viewer_pid')) or {}
            previous.clear()
            previous.update({pid: process_identity(pid) for pid in memory.get('pids', [])})
            assert all(birth is not None for birth in previous.values()), 'Could not establish owned process identity'
            report['cycles'].append({'index': index, 'source': str(source),
                'first_ready_seconds': ready_at - opened, 'memory': memory,
                'qgis_tree_memory': tree_memory(os.getpid()),
                'strategy': page._source_info.get('strategy'), 'point_count': state.get('total')})
            atomic_write_json(args.output_dir / 'source_switch.json', report)
            print(json.dumps({'completed': index + 1, 'source': source.name}), flush=True)
            index += 1
            if index == args.cycles:
                finish()
                return
            page.mode.setCurrentText('Intensity')
            page.height_enabled.setChecked(True)
            page.apply_filters()
            open_next()
        except Exception:
            report['errors'].append(traceback.format_exc())
            finish()
    open_next()
    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(250)
    code = app.exec() if hasattr(app, 'exec') else app.exec_()
    app.exitQgis()
    return code


if __name__ == '__main__':
    raise SystemExit(main())
