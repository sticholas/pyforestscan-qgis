"""Summarize retained motion telemetry and nonblack screenshot occupancy."""
import argparse
import json
from pathlib import Path
import statistics
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    from qgis.PyQt.QtGui import QImage
    from pyforestscan_qgis.core.atomic_state import atomic_write_json
    summary = {}
    for file in sorted(args.root.glob('*/motion.json')):
        data = json.loads(file.read_text(encoding='utf-8'))
        samples = data.get('samples', [])
        groups = {}
        for phase in ('initial', 'orbit', 'settle', 'pan', 'zoom', 'refined', 'human', 'stress', 'idle'):
            rows = [s for s in samples if s['phase'] == phase]
            if not rows:
                continue
            def rendered(s):
                return s.get('render_diagnostics', {}).get('rendered_points', s['displayed'])
            groups[phase] = {'samples': len(rows), 'min_points': min(rendered(s) for s in rows),
                'max_points': max(rendered(s) for s in rows),
                'mean_frame_ms': statistics.mean(s['frame_ms'] for s in rows),
                'zero_point_samples': sum(rendered(s) == 0 for s in rows)}
        pictures = []
        for shot in data.get('screenshots', []):
            image = QImage(shot['path'])
            if image.isNull():
                continue
            hits = total = 0
            for y in range(0, image.height(), 4):
                for x in range(0, image.width(), 4):
                    color = image.pixelColor(x, y)
                    hits += max(color.red(), color.green(), color.blue()) > 5
                    total += 1
            pictures.append({'name': shot['name'], 'occupancy': hits / total, 'path': shot['path']})
        memory = [s['process_memory'] for s in samples if s.get('process_memory')]
        summary[file.parent.name] = {'errors': data['errors'], 'phases': groups, 'screenshots': pictures,
            'first_useful_view_seconds': data.get('first_useful_view_seconds'),
            'strategy': data.get('source_info', {}).get('strategy'),
            'preparation_seconds': data.get('source_info', {}).get('preparation_seconds'),
            'timings': data.get('source_info', {}).get('timings'),
            'peak_private_bytes': max((m['private_bytes'] for m in memory), default=None),
            'peak_working_set_bytes': max((m['working_set_bytes'] for m in memory), default=None),
            'final_transport': samples[-1].get('transport') if samples else None}
    atomic_write_json(args.root / 'motion_summary.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
