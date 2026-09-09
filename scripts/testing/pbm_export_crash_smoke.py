"""Kill only an owned export child during writing; retain partials as evidence."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--child', action='store_true')
    args = parser.parse_args()
    dll = Path(sys.executable).parent / 'Library/bin'
    handle = os.add_dll_directory(str(dll)) if os.name == 'nt' and dll.is_dir() else None
    from pyforestscan_qgis.core.atomic_state import atomic_write_json
    from pyforestscan_qgis.core.point_cloud.session import PointCloudEditSession
    from pyforestscan_qgis.core.point_cloud.export import export_edited
    from pyforestscan_qgis.core.backend.process_env import hidden_subprocess_kwargs
    session = PointCloudEditSession.load(args.session)
    destination = args.output_dir / 'edited.laz'
    journal_before = args.session.read_bytes()
    if args.child:
        def progress(stage, count):
            if stage == 'Writing edited cloud':
                atomic_write_json(args.output_dir / 'writing.json', {'pid': os.getpid(), 'count': count})
        export_edited(session, destination, progress=progress)
        return 0
    args.output_dir.mkdir(parents=True, exist_ok=False)
    child = subprocess.Popen([sys.executable, '-I', str(Path(__file__).resolve()),
        '--session', str(args.session), '--output-dir', str(args.output_dir), '--child'],
        **hidden_subprocess_kwargs())
    killed = False
    try:
        deadline = time.monotonic() + 600
        while child.poll() is None and time.monotonic() < deadline:
            partials = list(args.output_dir.glob('.*.partial.laz'))
            if (args.output_dir / 'writing.json').is_file() and any(p.stat().st_size > 1000 for p in partials):
                child.kill()
                child.wait(timeout=30)
                killed = True
                break
            time.sleep(.01)
        if not killed:
            raise AssertionError('Did not terminate the owned child during actual output writing')
    finally:
        if child.poll() is None:
            child.kill()
        child.wait()
    assert not destination.exists(), 'Unvalidated final output published'
    assert not destination.with_name(destination.name + '.export_validation.json').exists()
    assert args.session.read_bytes() == journal_before
    session.source.verify()
    partials = [{'name': p.name, 'bytes': p.stat().st_size} for p in args.output_dir.glob('.*partial*')]
    # Retain evidence; final destination remains free for an explicit retry.
    retry = export_edited(session, destination)
    assert retry['status'] == 'VALIDATED'
    assert args.session.read_bytes() == journal_before
    session.source.verify()
    report = {'passed': True, 'killed_owned_pid': child.pid, 'exit_code': child.returncode,
              'partial_files_retained_for_qa': partials, 'retry': retry,
              'source_unchanged': True, 'journal_unchanged': True,
              'limitation': 'Abruptly killed children leave clearly named partial scratch files; automatic reclamation not qualified.'}
    atomic_write_json(args.output_dir / 'export_crash.json', report)
    print(json.dumps(report), flush=True)
    if handle:
        handle.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
