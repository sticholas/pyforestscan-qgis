from pathlib import Path
import tempfile
import unittest
from pyforestscan_qgis.core.point_cloud.indexer_input import (
    indexer_input_pipeline, needs_scan_flag_workaround,
)


class IndexerInputTests(unittest.TestCase):
    def test_workaround_is_version_and_point_format_specific(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source.laz'
            for fmt in (3, 6, 7, 8):
                header = bytearray(105)
                header[:4] = b'LASF'
                header[104] = fmt | 0x80
                source.write_bytes(header)
                self.assertEqual(needs_scan_flag_workaround(source, 'untwine version (1.5.1)'), fmt >= 6)
                self.assertFalse(needs_scan_flag_workaround(source, 'untwine version (1.6.0)'))

    def test_bit_packing_preserves_all_channels_and_scan_directions(self):
        for channel in range(4):
            for direction in range(2):
                bits = (channel * 16) | (0 << 5) | (direction << 6)
                self.assertEqual((bits >> 4) & 3, channel)
                self.assertEqual((bits >> 6) & 1, direction)

    def test_pipeline_uses_temporary_output_and_all_dimensions(self):
        stages = indexer_input_pipeline('original.laz', 'owned-temp/index-input.las', ('ScanChannel',))
        self.assertEqual(stages[0]['filename'], 'original.laz')
        self.assertEqual(stages[-1]['filename'], 'owned-temp/index-input.las')
        self.assertEqual(stages[-1]['extra_dims'], 'all')
        self.assertEqual(stages[2]['value'], ['ClassFlags = ScanChannel * 16', 'ScanChannel = 0'])
        with self.assertRaises(ValueError):
            indexer_input_pipeline('original', 'temp', ('ClassFlags',))
