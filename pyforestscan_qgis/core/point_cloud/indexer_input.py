"""Bounded workaround for Untwine 1.5.1 scanner-channel bit packing.

Only an owned temporary input is rewritten. The original stays authoritative.
"""
import json
from pathlib import Path


def needs_scan_flag_workaround(source, version):
    if version.strip() != 'untwine version (1.5.1)':
        return False
    with Path(source).open('rb') as stream:
        header = stream.read(105)
    if len(header) < 105 or header[:4] != b'LASF':
        raise ValueError('Cannot verify LAS point format for the managed indexer.')
    return header[104] & 0x3f >= 6


def indexer_input_pipeline(source, temporary, dimensions):
    if 'ClassFlags' in dimensions:
        raise ValueError('Source has a ClassFlags extra dimension; the indexer workaround cannot overwrite it.')
    return [
        {'type': 'readers.las', 'filename': str(source)},
        {'type': 'filters.ferry', 'dimensions': 'ScanChannel=>ClassFlags'},
        {'type': 'filters.assign', 'value': ['ClassFlags = ScanChannel * 16', 'ScanChannel = 0']},
        {'type': 'writers.las', 'filename': str(temporary), 'compression': False,
         'forward': 'all', 'extra_dims': 'all'},
    ]


def prepare_indexer_input(source, staging, version, dimensions, *, expected_count, progress):
    if not needs_scan_flag_workaround(source, version):
        return Path(source)
    temporary = Path(staging) / 'index-input.las'
    if temporary.exists() or temporary.is_symlink() or temporary.resolve().parent != Path(staging).resolve():
        raise ValueError('Unsafe or occupied indexer input staging path.')
    import pdal
    progress('Preserving source attributes for optimized view')
    pipeline = pdal.Pipeline(json.dumps(indexer_input_pipeline(source, temporary, dimensions)))
    count = pipeline.execute_streaming(65536)
    if count != expected_count:
        raise ValueError('Temporary indexing input lost source points.')
    return temporary
