"""Bounded real-PDAL all-attribute equivalence check, ignoring cache point order."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    dll = Path(sys.executable).parent / 'Library/bin'
    handle = os.add_dll_directory(str(dll)) if os.name == 'nt' and dll.is_dir() else None
    import numpy as np
    import pdal
    from pyproj import CRS
    from pyforestscan_qgis.core.point_cloud.session import SourceIdentity
    from pyforestscan_qgis.core.atomic_state import atomic_write_json
    started = time.monotonic()
    source = SourceIdentity.capture(args.source)
    original = pdal.Pipeline(json.dumps([{'type': 'readers.las', 'filename': str(args.source)}]))
    indexed = pdal.Pipeline(json.dumps([{'type': 'readers.copc', 'filename': str(args.cache)}]))
    first, second = (next(iter(p.quickinfo.values())) for p in (original, indexed))
    assert 0 < first['num_points'] <= 3_000_000, 'Full-array QA is limited to a 3M-point fixture'
    assert first['num_points'] == second['num_points']
    original.execute()
    indexed.execute()
    left, raw_right = original.arrays[0], indexed.arrays[0]
    assert set(left.dtype.names) <= set(raw_right.dtype.names)
    right = np.empty(len(raw_right), dtype=left.dtype)
    for name in left.dtype.names:
        right[name] = raw_right[name]
    left = left.copy()
    left.sort(order=list(left.dtype.names))
    right.sort(order=list(right.dtype.names))
    matched = {name: bool(np.array_equal(left[name], right[name], equal_nan=True)) for name in left.dtype.names}
    def crs(meta):
        return meta.get('srs', {}).get('compoundwkt') or meta.get('srs', {}).get('wkt') or ''
    a, b = crs(first), crs(second)
    crs_equal = bool(a) == bool(b) and (not a or CRS(a).equals(CRS(b)))
    source.verify()
    report = {'passed': all(matched.values()) and crs_equal, 'dimensions': matched,
              'crs_preserved': crs_equal, 'points': len(left), 'source_sha256': source.sha256,
              'original_unchanged': True, 'seconds': time.monotonic() - started,
              'comparison': 'All original attribute values, canonical record ordering; cache order is not edit authority.'}
    atomic_write_json(args.report, report)
    print(json.dumps(report), flush=True)
    if handle:
        handle.close()
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
