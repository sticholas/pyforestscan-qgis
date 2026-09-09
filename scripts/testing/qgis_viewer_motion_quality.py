"""Real renderer motion measurements; deterministic cameras are not human QA."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--plugin-root', type=Path)
    parser.add_argument('--duration', type=float, default=72)
    parser.add_argument('--preparation-timeout', type=float, default=180)
    parser.add_argument('--human', action='store_true')
    parser.add_argument('--stability', action='store_true')
    args = parser.parse_args()
    if not 30 <= args.duration <= 7200 or not 60 <= args.preparation_timeout <= 7200:
        parser.error('Use a bounded 30-7200 second test and 60-7200 second preparation deadline.')
    if args.plugin_root:
        sys.path.insert(0, str(args.plugin_root.resolve()))
    args.output_dir.mkdir(parents=True, exist_ok=False)
    from qgis.core import QgsApplication, Qgis
    from qgis.PyQt.QtCore import QTimer, Qt
    from pyforestscan_qgis.compat.qt import qt_enum
    from pyforestscan_qgis.ui.point_cloud_page import PointCloudPage
    from pyforestscan_qgis.core.atomic_state import atomic_write_json
    from windows_viewer_memory import tree_memory
    app = QgsApplication([], True)
    app.initQgis()
    print('QGIS initialized', flush=True)
    page = PointCloudPage()
    page.setWindowTitle(("Human editing check: " if args.human else "Automated viewer QA: ") + args.source.name)
    if args.human:
        page.setWindowFlag(qt_enum(Qt, 'WindowStaysOnTopHint', 'WindowType'), True)
    page.resize(760, 760)
    page.show()
    print('Page constructed', flush=True)
    page.source.setText(str(args.source))
    report = {'source': str(args.source), 'bytes': args.source.stat().st_size,
              'qgis': Qgis.QGIS_VERSION, 'samples': [], 'screenshots': [], 'errors': [],
              'human_acceptance': 'PENDING_USER_REPORT' if args.human else 'NOT_EXECUTED',
              'duration_requested': args.duration}
    def sha():
        if args.source.stat().st_size > 300_000_000:
            return None
        with args.source.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    report['sha_before'] = sha()
    start = time.monotonic()
    ready_at = None
    camera = None
    phase = ''
    closing = False
    captures = set()
    last_action = -1
    last_checkpoint = -1
    last_telemetry = start
    report['filter_transitions'] = 0
    report['geometry_failures'] = []
    report['minute_checkpoints'] = []
    page.start_source(str(args.source))
    print('Source requested', flush=True)
    worker = page.worker
    def finish():
        nonlocal closing
        if closing:
            return
        closing = True
        tick.stop()
        events = [w.stopped_event for w in (page.worker, page.editor.worker) if w]
        page.prepare_for_unload()
        def wait():
            if not all(e.is_set() for e in events):
                QTimer.singleShot(100, wait)
                return
            report['sha_after'] = sha()
            if report['geometry_failures']:
                report['errors'].append('Filter transitions changed viewer canvas geometry')
            report['source_unchanged'] = report['sha_before'] == report['sha_after'] if report['sha_before'] else None
            atomic_write_json(args.output_dir / 'motion.json', report)
            atomic_write_json(args.output_dir / 'checkpoint.json', {
                'complete': True, 'errors': report['errors'],
                'checkpoints': report['minute_checkpoints'],
                'filter_transitions': report['filter_transitions']})
            print(json.dumps({'samples': len(report['samples']), 'errors': report['errors'], 'evidence': str(args.output_dir)}), flush=True)
            page.close()
            app.exit(0 if not report['errors'] else 1)
        wait()
    def observe(value):
        nonlocal ready_at, camera, last_telemetry
        if value.get('screenshot'):
            report['screenshots'].append(value['screenshot'])
        if value.get('error'):
            report['errors'].append(value['error'])
            finish()
        if value.get('diagnostics_path'):
            print(value['diagnostics_path'], flush=True)
            report['diagnostics_path'] = value['diagnostics_path']
        if value.get('source_info'):
            report['source_info'] = value['source_info']
        data = value.get('telemetry', {})
        if not data.get('ready'):
            return
        last_telemetry = time.monotonic()
        if ready_at is None and data.get('render_diagnostics', {}).get('rendered_points', 0) > 0:
            ready_at = time.monotonic()
            report['first_useful_view_seconds'] = ready_at - start
            camera = data['camera']
        report['samples'].append({'seconds': time.monotonic() - start, 'phase': phase, **data})
        if worker.run_record:
            report['samples'][-1]['process_memory'] = tree_memory(worker.run_record.data.get('viewer_pid'))
        if data.get('errors'):
            report['errors'].extend(data['errors'])
    worker.update.connect(observe)
    def advance():
        nonlocal phase, last_action, last_checkpoint
        if time.monotonic() - start > args.preparation_timeout + args.duration:
            report['errors'].append('Deadline exceeded')
            finish()
            return
        if ready_at is None:
            return
        elapsed = time.monotonic() - ready_at
        if args.stability:
            if time.monotonic() - last_telemetry > 30:
                report['errors'].append('Renderer telemetry stalled for more than 30 seconds')
                finish()
                return
            action_number = int(elapsed / 6)
            if action_number != last_action:
                last_action = action_number
                before = (page.surface.width(), page.surface.height())
                action = action_number % 8
                if action == 0:
                    page.filter_toggle.setChecked(True)
                elif action == 1:
                    page.filter_toggle.setChecked(False)
                elif action == 2:
                    page.mode.setCurrentIndex((page.mode.currentIndex() + 1) % page.mode.count())
                elif action == 3:
                    page.height_enabled.setChecked(True)
                    page.apply_filters()
                elif action == 4:
                    page.clear_filters()
                elif action == 5:
                    page.show_all_classes()
                elif action == 6:
                    if page.editor.state.get('ready') and not page.editor.busy:
                        page.editor.send('clear')
                else:
                    page.clear_filters()
                    if page.editor.state.get('ready') and not page.editor.busy:
                        direction = [-math.sin(camera['yaw']) * math.cos(camera['pitch']),
                                     math.cos(camera['yaw']) * math.cos(camera['pitch']), math.sin(camera['pitch'])]
                        x, y, _z = [p + d * camera['radius'] for p, d in zip(camera['position'], direction)]
                        page.send({'action': 'selection_test',
                                   'geometry': [[x,y], [x+1,y], [x,y+1], [x,y]]})
                report['filter_transitions'] += 1
                def check_geometry(expected=before):
                    actual = (page.surface.width(), page.surface.height())
                    if actual != expected:
                        report['geometry_failures'].append({'seconds': elapsed, 'before': expected, 'after': actual})
                QTimer.singleShot(150, check_geometry)
            minute = int(elapsed / 60)
            if minute != last_checkpoint:
                last_checkpoint = minute
                checkpoint = {'minute': minute, 'elapsed': elapsed,
                              'sample': report['samples'][-1] if report['samples'] else None,
                              'filter_transitions': report['filter_transitions'],
                              'geometry_failures': len(report['geometry_failures'])}
                report['minute_checkpoints'].append(checkpoint)
                atomic_write_json(args.output_dir / 'checkpoint.json', {
                    'complete': False, 'source': str(args.source),
                    'checkpoints': report['minute_checkpoints'], 'errors': report['errors']})
                print(json.dumps({'minute': minute, 'filter_transitions': report['filter_transitions'],
                                  'geometry_failures': len(report['geometry_failures'])}), flush=True)
        if args.human:
            phase = 'human'
            if not captures:
                captures.add('human_start')
                page.send({'action': 'capture', 'name': 'human_start'})
            if elapsed >= args.duration:
                finish()
            return
        if args.duration > 72:
            phase = 'idle' if elapsed >= 1800 and int(elapsed) % 120 >= 90 else 'stress'
            if phase == 'stress':
                c = dict(camera)
                angle = math.sin(elapsed * .2)
                c['yaw'] += angle * .7
                c['pitch'] += math.sin(elapsed * .15) * .2
                factor = .2 + .8 * (1 + math.sin(elapsed * .09)) / 2
                direction = [-math.sin(c['yaw']) * math.cos(c['pitch']),
                             math.cos(c['yaw']) * math.cos(c['pitch']), math.sin(c['pitch'])]
                original_direction = [-math.sin(camera['yaw']) * math.cos(camera['pitch']),
                                      math.cos(camera['yaw']) * math.cos(camera['pitch']), math.sin(camera['pitch'])]
                pivot = [p + d * camera['radius'] for p, d in zip(camera['position'], original_direction)]
                c['position'] = [p - d * camera['radius'] * factor for p, d in zip(pivot, direction)]
                c['radius'] *= factor
                page.send({'action': 'camera', 'camera': c})
            if int(elapsed) % 300 == 0 and str(int(elapsed)) not in captures:
                captures.add(str(int(elapsed)))
                page.send({'action': 'capture', 'name': 'stress_' + str(int(elapsed))})
            if elapsed >= args.duration:
                finish()
            return
        new_phase = ('initial' if elapsed < 6 else 'orbit' if elapsed < 36 else
                     'settle' if elapsed < 44 else 'pan' if elapsed < 54 else
                     'zoom' if elapsed < 64 else 'refined')
        if new_phase != phase:
            phase = new_phase
            if phase in ('pan', 'zoom'):
                page.send({'action': 'camera', 'camera': camera})
        if phase == 'orbit':
            page.send({'action': 'orbit'})
        elif phase in ('pan', 'zoom'):
            c = dict(camera)
            c['position'] = list(camera['position'])
            if phase == 'pan':
                c['position'][0] += math.sin(elapsed) * camera['radius'] * .08
            else:
                # Dolly along the existing view direction, keeping the same pivot.
                factor = 1 + .15 * math.sin(elapsed)
                direction = [-math.sin(c['yaw']) * math.cos(c['pitch']),
                             math.cos(c['yaw']) * math.cos(c['pitch']), math.sin(c['pitch'])]
                c['position'] = [p + d * camera['radius'] * (1 - factor) for p, d in zip(c['position'], direction)]
                c['radius'] *= factor
            page.send({'action': 'camera', 'camera': c})
        marker = (phase if phase not in ('orbit', 'initial') else
                  'initial' if phase == 'initial' else 'orbit_start' if elapsed < 9 else 'orbit_middle' if elapsed < 22 else 'orbit_end')
        if marker not in captures and elapsed > 3:
            captures.add(marker)
            page.send({'action': 'capture', 'name': marker})
        if elapsed > args.duration:
            finish()
    tick = QTimer()
    tick.timeout.connect(advance)
    tick.start(200)
    code = app.exec() if hasattr(app, 'exec') else app.exec_()
    app.exitQgis()
    return code


if __name__ == '__main__':
    raise SystemExit(main())
