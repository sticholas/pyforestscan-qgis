"""Real Qt/renderer filter transitions without changing the selection layout."""
import argparse
import json
from pathlib import Path
import sys
import time
import traceback
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--transitions', type=int, default=500)
    args = parser.parse_args()
    if not 16 <= args.transitions <= 2000:
        parser.error('Use 16-2000 bounded transitions.')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    from qgis.core import QgsApplication, Qgis
    from qgis.PyQt.QtCore import QTimer, QEvent
    from qgis.PyQt.QtWidgets import QWidget
    from pyforestscan_qgis.ui.point_cloud_page import PointCloudPage
    from pyforestscan_qgis.compat.qt import qt_enum
    from pyforestscan_qgis.core.atomic_state import atomic_write_json
    app = QgsApplication([], True)
    app.initQgis()
    page = PointCloudPage()
    page.setWindowTitle('Automated filter-panel regression')
    page.resize(760, 850)
    page.show()
    page.source.setText(str(args.source))
    page.start_source(str(args.source))
    report = {'qgis': Qgis.QGIS_VERSION, 'transitions': 0, 'errors': [], 'samples': []}
    started = time.monotonic()
    baseline = None
    ready_at = None
    closing = False

    def finish():
        nonlocal closing
        if closing:
            return
        closing = True
        timer.stop()
        events = [w.stopped_event for w in (page.worker, page.editor.worker) if w]
        page.prepare_for_unload()
        def complete():
            if not all(e.is_set() for e in events):
                QTimer.singleShot(100, complete)
                return
            report['passed'] = not report['errors'] and report['transitions'] == args.transitions
            report['seconds'] = time.monotonic() - started
            atomic_write_json(args.output_dir / 'filter_stress.json', report)
            print(json.dumps({k: v for k, v in report.items() if k != 'samples'}), flush=True)
            page.close()
            app.exit(0 if report['passed'] else 1)
        complete()

    def tick():
        nonlocal baseline, ready_at
        try:
            if time.monotonic() - started > 240 + args.transitions:
                raise TimeoutError('Filter stress timed out')
            state = page._view_state or {}
            if not state.get('ready') or not page.editor.state.get('ready') or page.editor.busy:
                return
            if ready_at is None:
                ready_at = time.monotonic()
            if time.monotonic() - ready_at < 5:
                return
            measured = {'canvas': [page.surface.width(), page.surface.height()],
                        'camera': state['camera'], 'budget': state['budget'],
                        'selection': page.editor.state.get('selection'),
                        'revision': page.editor.state.get('revision'),
                        'widgets': len(page.findChildren(QWidget))}
            if baseline is None:
                baseline = measured
                report['baseline'] = baseline
            else:
                for key in ('canvas', 'camera', 'budget', 'selection', 'revision', 'widgets'):
                    if measured[key] != baseline[key]:
                        raise AssertionError(f'{key} changed at transition {report["transitions"]}: {measured[key]} != {baseline[key]}')
            if report['transitions'] >= args.transitions:
                finish()
                return
            action = report['transitions'] % 8
            if action == 0:
                page.filter_toggle.setChecked(True)
                app.sendEvent(page.height_min, QEvent(qt_enum(QEvent, 'Enter', 'Type')))
            elif action == 1:
                page.filters_panel.close()
            elif action == 2:
                page.mode.setCurrentIndex((page.mode.currentIndex() + 1) % page.mode.count())
            elif action == 3:
                page.height_enabled.setChecked(True)
                page.height_min.setValue(state['z_range'][0])
                page.height_max.setValue(state['z_range'][1])
                page.apply_filters()
            elif action == 4:
                page.clear_filters()
            elif action == 5:
                page.send({'action': 'classes', 'classes': [2, 5]})
            elif action == 6:
                page.show_all_classes()
            else:
                page.clear_filters()
            report['transitions'] += 1
            if report['transitions'] % 50 == 0:
                report['samples'].append(measured)
                print(json.dumps({'transitions': report['transitions']}), flush=True)
        except Exception:
            report['errors'].append(traceback.format_exc())
            finish()
    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(250)
    code = app.exec() if hasattr(app, 'exec') else app.exec_()
    app.exitQgis()
    return code


if __name__ == '__main__':
    raise SystemExit(main())
