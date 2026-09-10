"""QGIS-free selection integrity tests; geometry tier uses managed dependencies."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from pyforestscan_qgis.core.point_cloud.selection import (
    SelectionDefinition, SelectionResolver, reader_spec, reader_specs, validate_sequence,
)
from pyforestscan_qgis.core.point_cloud.session import SourceIdentity


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name) / "original.copc.laz"
        path.write_bytes(b"immutable source for contract tests")
        self.source = SourceIdentity.capture(path)
        self.definition = SelectionDefinition("a", "session", self.source.sha256, "COPC",
            ((0, 0), (2, 0), (0, 2), (0, 0)), "SOURCE_LOCAL:" + self.source.sha256)

    def test_nested_inputs_are_immutable(self):
        points = [[0, 0], [2, 0], [0, 2], [0, 0]]
        definition = replace(self.definition, geometry=points, classification_filter=[2])
        points[1][0] = 999
        self.assertEqual(definition.geometry[1], (2, 0))
        self.assertEqual(definition.classification_filter, (2,))

    def test_inversion_is_explicit_and_forces_complete_copc_reader(self):
        inverted = replace(self.definition, invert_result=True)
        self.assertNotIn("bounds", reader_spec(self.source, [inverted]))
        subtract_inverted = replace(self.definition, selection_id="subtract", selection_mode="SUBTRACT",
                                      invert_result=True)
        self.assertEqual(len(reader_specs(self.source, [self.definition, subtract_inverted])), 1)
        self.assertNotIn("bounds", reader_specs(self.source, [self.definition, subtract_inverted])[0])
        with self.assertRaisesRegex(ValueError, "boolean"):
            replace(self.definition, invert_result=1)

    def test_lod_and_ept_identity_rejected(self):
        for field, value in (("addressing", "LOD_SAMPLE"), ("source_type", "EPT")):
            with self.assertRaises(ValueError):
                replace(self.definition, **{field: value})

    def test_invalid_geometry_and_filters_rejected(self):
        for values in ({"geometry": ((0, 0), (1, 0), (0, 1))},
                       {"geometry": ((0, 0), (float("nan"), 0), (0, 2), (0, 0))},
                       {"classification_filter": [True]}, {"z_filter": (3, 1)},
                       {"hag_filter": (0, float("inf"))},
                       {"attribute_filters": (("X", 0, 1),)},
                       {"attribute_filters": (("Intensity || 1", 0, 1),)}):
            with self.assertRaises(ValueError):
                replace(self.definition, **values)

    def test_copc_reader_is_bounded_without_lod(self):
        reader = reader_spec(self.source, [self.definition])
        self.assertEqual(reader["type"], "readers.copc")
        self.assertEqual(reader["bounds"], "([0,2],[0,2])")
        for key in ("resolution", "depth", "count", "point_budget"):
            self.assertNotIn(key, reader)

    def test_sources_sessions_crs_and_duplicate_ids_rejected(self):
        for change in ({"session_id": "other"}, {"source_fingerprint": "f" * 64},
                       {"geometry_crs": "EPSG:4326"}, {"selection_id": "a"}):
            with self.assertRaises(ValueError):
                validate_sequence([self.definition, replace(self.definition,
                    **({"selection_id": "b", "selection_mode": "ADD"} | change))])

    def test_distant_add_regions_do_not_make_one_large_envelope(self):
        far = replace(self.definition, selection_id="far", selection_mode="ADD",
                      geometry=((100, 100), (102, 100), (100, 102), (100, 100)))
        specs = reader_specs(self.source, [self.definition, far])
        self.assertEqual(len(specs), 2)
        self.assertEqual(specs[0]["bounds"], "([0,2],[0,2])")
        self.assertEqual(specs[1]["bounds"], "([100,102],[100,102])")

    def test_last_replace_resets_sequence(self):
        later = replace(self.definition, selection_id="b")
        self.assertEqual(validate_sequence([self.definition, later]), (later,))
        with self.assertRaises(ValueError):
            validate_sequence([replace(later, selection_mode="SUBTRACT")])

    def test_foreign_source_rejected(self):
        with self.assertRaises(ValueError):
            reader_spec(replace(self.source, sha256="e" * 64), [self.definition])

    def test_attachment_and_later_source_change_rejected(self):
        resolver = SelectionResolver(self.source)
        Path(self.source.path).write_bytes(b"changed source")
        with self.assertRaisesRegex(ValueError, "Source changed"):
            resolver._check_source()
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            SelectionResolver(self.source)

    @unittest.skipUnless(importlib.util.find_spec("shapely") and importlib.util.find_spec("pyproj"),
                         "Managed geometry tier requires Shapely and pyproj")
    def test_streamed_geometry_modes_stats_and_missing_hag(self):
        import numpy as np
        points = np.array([(0, 0, 1, 2), (1, 1, 2, 5), (2, 2, 3, 5), (.5, .5, 4, 2)],
            dtype=[("X", "f8"), ("Y", "f8"), ("Z", "f8"), ("Classification", "u1")])

        class Pipeline:
            quickinfo = {"readers.copc": {"num_points": 4, "dimensions": "X, Y, Z, Classification"}}
            def __init__(self, spec): pass
            def iterator(self, *, chunk_size, prefetch):
                self_outer.assertEqual(chunk_size, 65536)
                self_outer.assertEqual(prefetch, 0)
                yield points[:2]
                yield points[2:]
        self_outer = self
        resolver = SelectionResolver(self.source)
        with patch.dict("sys.modules", {"pdal": types.SimpleNamespace(Pipeline=Pipeline)}):
            progress = []
            result = resolver.resolve([self.definition], progress=progress.append)
            # Triangle includes boundary (1,1), excludes its envelope corner (2,2).
            self.assertEqual(result.resolved_point_count, 3)
            self.assertEqual(result.classification_counts, ((2, 2), (5, 1)))
            self.assertEqual(result.z_max, 4)
            self.assertEqual(progress, [2, 4])
            inverted = replace(self.definition, invert_result=True)
            self.assertEqual(resolver.resolve([inverted]).resolved_point_count, 1)
            added_after_invert = replace(self.definition, selection_id="after", selection_mode="ADD",
                                         classification_filter=(2,))
            self.assertEqual(resolver.resolve([inverted, added_after_invert]).resolved_point_count, 3)
            added = replace(self.definition, selection_id="b", selection_mode="ADD")
            self.assertEqual(resolver.resolve([self.definition, added]).resolved_point_count, 3)
            with patch.object(Pipeline, "iterator", lambda self, **kwargs: iter((np.concatenate((points, points)),))):
                self.assertEqual(resolver.resolve([self.definition, added]).resolved_point_count, 6)
            removed = replace(added, selection_id="c", selection_mode="SUBTRACT",
                              classification_filter=(2,))
            self.assertEqual(resolver.resolve([self.definition, added, removed]).resolved_point_count, 1)
            none = replace(self.definition, classification_filter=())
            self.assertEqual(resolver.resolve([none]).resolved_point_count, 0)
            with self.assertRaisesRegex(ValueError, "HeightAboveGround"):
                resolver.resolve([replace(self.definition, hag_filter=(0, 5))])
            with patch.object(Pipeline, "iterator", return_value=iter(())) as iterator:
                with self.assertRaisesRegex(ValueError, "HeightAboveGround"):
                    resolver.resolve([replace(self.definition, hag_filter=(0, 5))])
                iterator.assert_not_called()
            with self.assertRaises(InterruptedError):
                resolver.resolve([self.definition], cancelled=lambda: True)
            with self.assertRaisesRegex(ValueError, "invalid"):
                resolver.resolve([replace(self.definition,
                    geometry=((0, 0), (2, 2), (2, 0), (0, 2), (0, 0)))])
        self.source.verify()

    @unittest.skipUnless(importlib.util.find_spec('shapely') and importlib.util.find_spec('pyproj'),
                         'Managed geometry tier requires Shapely and pyproj')
    def test_large_raw_metadata_uses_bounded_original_stream(self):
        import json
        import numpy as np
        raw = replace(self.source, source_type='LAS')
        definition = replace(self.definition, source_type='LAS')
        points = np.array([(0, 0, 1, 2)],
            dtype=[('X', 'f8'), ('Y', 'f8'), ('Z', 'f8'), ('Classification', 'u1')])
        owner = self
        class Pipeline:
            quickinfo = {'readers.las': {'num_points': 104819538,
                         'dimensions': 'X, Y, Z, Classification'}}
            def __init__(self, spec):
                reader = json.loads(spec)[0]
                owner.assertEqual(reader['filename'], raw.path)
                owner.assertEqual(reader['type'], 'readers.las')
                owner.assertNotIn('count', reader)
            def iterator(self, *, chunk_size, prefetch):
                owner.assertEqual((chunk_size, prefetch), (65536, 0))
                yield points
        # Test query policy without claiming the one-row stub is a large-file benchmark.
        with patch.object(SourceIdentity, 'verify'), patch.dict('sys.modules', {
                'pdal': types.SimpleNamespace(Pipeline=Pipeline)}):
            self.assertEqual(SelectionResolver(raw).resolve([definition]).resolved_point_count, 1)


if __name__ == "__main__":
    unittest.main()
