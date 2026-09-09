"""Real renderer motion measurements; deterministic cameras are not human QA."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--plugin-root', type=Path)
    args = parser.parse_args()
    if args.plugin_root:
        sys.path.insert(0, str(args.plugin_root.resolve()))
    args.output_dir.mkdir(parents=True, exist_ok=False)
    from qgis.core import QgsApplication, Qgis
    from qgis.PyQt.QtCore import QTimer
    from pyforestscan_qgis.ui.point_cloud_page import PointCloudPage
    from pyforestscan_qgis.core.atomic_state import atomic_write_json
    from windows_viewer_memory import tree_memory
    app = QgsApplication([], True)
    app.initQgis()
    print('QGIS initialized', flush=True)
    page = PointCloudPage()
    page.resize(760, 760)
    page.show()
    print('Page constructed', flush=True)
    page.source.setText(str(args.source))
    report = {'source': str(args.source), 'bytes': args.source.stat().st_size,
              'qgis': Qgis.QGIS_VERSION, 'samples': [], 'screenshots': [], 'errors': [],
              'human_acceptance': 'NOT_EXECUTED'}
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
            report['source_unchanged'] = report['sha_before'] == report['sha_after'] if report['sha_before'] else None
            atomic_write_json(args.output_dir / 'motion.json', report)
            print(json.dumps({'samples': len(report['samples']), 'errors': report['errors'], 'evidence': str(args.output_dir)}), flush=True)
            page.close()
            app.exit(0 if not report['errors'] else 1)
        wait()
    def observe(value):
        nonlocal ready_at, camera
        if value.get('screenshot'):
            report['screenshots'].append(value['screenshot'])
        if value.get('error'):
            report['errors'].append(value['error'])
            finish()
        if value.get('diagnostics_path'):
            print(value['diagnostics_path'], flush=True)
        data = value.get('telemetry', {})
        if not data.get('ready'):
            return
        if ready_at is None and data.get('displayed', 0) > 0:
            ready_at = time.monotonic()
            camera = data['camera']
        report['samples'].append({'seconds': time.monotonic() - start, 'phase': phase, **data})
        if worker.run_record:
            report['samples'][-1]['process_memory'] = tree_memory(worker.run_record.data.get('viewer_pid'))
        if data.get('errors'):
            report['errors'].extend(data['errors'])
    worker.update.connect(observe)
    def advance():
        nonlocal phase
        if time.monotonic() - start > 180:
            report['errors'].append('Deadline exceeded')
            finish()
            return
        if ready_at is None:
            return
        elapsed = time.monotonic() - ready_at
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
        if elapsed > 72:
            finish()
    tick = QTimer()
    tick.timeout.connect(advance)
    tick.start(200)
    code = app.exec() if hasattr(app, 'exec') else app.exec_()
    app.exitQgis()
    return code


if __name__ == '__main__':
    raise SystemExit(main())
