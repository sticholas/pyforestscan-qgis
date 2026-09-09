"""Focused test boundaries; FULL remains mandatory at release milestones."""
import argparse
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EDITOR = {'test_point_cloud_editing.py', 'test_point_cloud_selection.py',
          'test_point_cloud_session.py'}


def test_files(tier):
    all_files = sorted((ROOT / 'tests').glob('test_*.py'))
    if tier == 'FULL':
        return all_files
    if tier == 'EDITOR_CORE':
        return [p for p in all_files if p.name in EDITOR]
    if tier == 'VIEWER_CORE':
        return [p for p in all_files if p.name.startswith('test_point_cloud_') and p.name not in EDITOR]
    if tier == 'RELEASE':
        return [p for p in all_files if 'release' in p.name or 'package' in p.name]
    if tier == 'PROCESS_CORE':
        return [p for p in all_files if not p.name.startswith('test_point_cloud_')]
    raise ValueError('Unknown test tier')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('tier', choices=('VIEWER_CORE', 'EDITOR_CORE', 'PROCESS_CORE', 'RELEASE', 'FULL'))
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args()
    paths = test_files(args.tier)
    if not paths:
        raise RuntimeError('Refusing an empty test tier')
    if args.list:
        print('\n'.join(str(p.relative_to(ROOT)) for p in paths))
        return 0
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(loader.discover(str(ROOT / 'tests'), pattern=p.name) for p in paths)
    return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
