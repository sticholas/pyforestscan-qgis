"""QGIS-free exact, bounded, disk-backed object catalog tests."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

try:
    import numpy as np
except ImportError:
    np = None

from pyforestscan_qgis.core.point_cloud.object_catalog import (
    build_object_catalog, build_source_object_catalog, catalog_neighbor,
    catalog_object, object_catalog_report, object_catalog_summary,
    object_selection_definition)
from pyforestscan_qgis.core.point_cloud.object_fields import CHUNK_SIZE


@unittest.skipIf(np is None, "numpy unavailable")
class ObjectCatalogTests(unittest.TestCase):
    SHA = "a" * 64

    def points(self):
        values = np.zeros(7, dtype=[("X","f8"),("Y","f8"),("Z","f8"),("Tree_ID","i8")])
        values["X"] = [0,1,2,10,11,20,21]
        values["Y"] = [0,2,1,10,12,20,22]
        values["Z"] = [1,3,2,5,7,9,8]
        values["Tree_ID"] = [3,3,3,8,8,12,12]
        return values

    def test_exact_counts_bounds_and_cross_chunk_aggregation(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "objects.sqlite"
            progress = []
            report = build_object_catalog((self.points()[:4], self.points()[4:]), 7,
                "Tree_ID", path, self.SHA, progress=progress.append)
            self.assertEqual(progress, [4,7])
            self.assertEqual(report["object_count"], 3)
            self.assertEqual(report["cataloged_point_count"], 7)
            self.assertEqual(report["minimum_object_id"], 3)
            self.assertEqual(report["maximum_object_id"], 12)
            self.assertEqual(catalog_object(path, 3)["point_count"], 3)
            self.assertEqual(catalog_object(path, 3)["max_y"], 2)
            self.assertEqual(catalog_object(path, 8)["min_x"], 10)
            self.assertTrue(report["bounded_memory"])
            self.assertEqual(report["chunk_size"], CHUNK_SIZE)
            self.assertIn("3 exact objects", object_catalog_summary(report))

    def test_next_previous_and_source_field_identity_guards(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "objects.sqlite"
            build_object_catalog((self.points(),), 7, "Tree_ID", path, self.SHA)
            self.assertEqual(catalog_neighbor(path, None, 1)["object_id"], 3)
            self.assertEqual(catalog_neighbor(path, 3, 1)["object_id"], 8)
            self.assertEqual(catalog_neighbor(path, 12, -1)["object_id"], 8)
            self.assertIsNone(catalog_neighbor(path, 12, 1))
            with self.assertRaisesRegex(ValueError, "another source"):
                catalog_object(path, 3, source_sha256="b" * 64)
            with self.assertRaisesRegex(ValueError, "another source dimension"):
                catalog_object(path, 3, field="Other")

    def test_failed_or_cancelled_build_preserves_previous_catalog(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "objects.sqlite"
            build_object_catalog((self.points(),), 7, "Tree_ID", path, self.SHA)
            before = path.read_bytes()
            with self.assertRaises(InterruptedError):
                build_object_catalog((self.points(),), 7, "Tree_ID", path, self.SHA,
                                     cancelled=lambda: True)
            self.assertEqual(path.read_bytes(), before)
            self.assertFalse(list(path.parent.glob("*.building-*")))

    def test_noninteger_missing_field_and_count_mismatch_are_rejected(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "objects.sqlite"
            values = self.points().astype(self.points().dtype.descr[:-1] + [("Tree_ID","f8")])
            values["Tree_ID"] = [1,1,2.5,2,3,3,3]
            with self.assertRaisesRegex(ValueError, "non-integer"):
                build_object_catalog((values,), 7, "Tree_ID", path, self.SHA)
            with self.assertRaisesRegex(ValueError, "does not contain"):
                build_object_catalog((self.points(),), 7, "Missing", path, self.SHA)
            with self.assertRaisesRegex(ValueError, "verified header"):
                build_object_catalog((self.points(),), 8, "Tree_ID", path, self.SHA)

    def test_source_wrapper_verifies_before_publish_and_uses_bounded_iterator(self):
        class Source:
            source_type = "LAS"
            path = "source.las"
            sha256 = self.SHA
            def __init__(self): self.verifications = 0
            def verify(self, **_kwargs): self.verifications += 1
        class Pipeline:
            def __init__(self, spec): self.spec = spec
            def iterator(self, **kwargs):
                self.module.iterator_kwargs = kwargs
                return iter((self.module.points,))
        source = Source()
        module = type("PDAL", (), {})()
        module.points = self.points()
        Pipeline.module = module
        module.Pipeline = Pipeline
        with TemporaryDirectory() as folder:
            report = build_source_object_catalog(source, 7, "Tree_ID",
                Path(folder)/"objects.sqlite", pdal_module=module)
            self.assertEqual(source.verifications, 2)
            self.assertEqual(module.iterator_kwargs, {"chunk_size":CHUNK_SIZE, "prefetch":0})
            self.assertEqual(report["object_count"], 3)

    def test_source_change_after_scan_preserves_previous_verified_catalog(self):
        class Source:
            source_type = "LAS"
            path = "source.las"
            sha256 = self.SHA
            def __init__(self): self.verifications = 0
            def verify(self, **_kwargs):
                self.verifications += 1
                if self.verifications == 2:
                    raise ValueError("source changed")
        class Pipeline:
            def __init__(self, _spec): pass
            def iterator(self, **_kwargs): return iter((self.points,))
        Pipeline.points = self.points()
        module = type("PDAL", (), {"Pipeline":Pipeline})()
        with TemporaryDirectory() as folder:
            path = Path(folder)/"objects.sqlite"
            build_object_catalog((self.points(),), 7, "Tree_ID", path, self.SHA)
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "source changed"):
                build_source_object_catalog(Source(), 7, "Tree_ID", path, pdal_module=module)
            self.assertEqual(path.read_bytes(), before)
            self.assertFalse(list(path.parent.glob("*.verified-*")))

    def test_catalog_object_becomes_one_authoritative_attribute_selection(self):
        from types import SimpleNamespace
        session = SimpleNamespace(session_id="session", source=SimpleNamespace(
            sha256=self.SHA, source_type="LAZ"), source_crs="EPSG:32605")
        row = {"object_id":8, "point_count":2, "min_x":10.0, "min_y":10.0,
               "min_z":5.0, "max_x":11.0, "max_y":12.0, "max_z":7.0}
        definition = object_selection_definition(session, "Tree_ID", row)
        self.assertEqual(definition.attribute_filters, (("Tree_ID",8,8),))
        self.assertEqual(definition.z_filter, (5.0,7.0))
        self.assertEqual(definition.selection_mode, "REPLACE")
        self.assertEqual(definition.addressing, "FULL_RESOLUTION_ORIGINAL_SOURCE_QUERY")

    def test_worker_routes_object_selection_through_authoritative_resolver(self):
        worker = (Path(__file__).parents[1] / "pyforestscan_qgis" / "viewer" /
                  "editor_worker.py").read_text(encoding="utf-8")
        self.assertIn('elif action == "build_object_catalog":', worker)
        self.assertIn('elif action in ("select_object", "neighbor_object"):', worker)
        self.assertIn("resolved.resolved_point_count != row[\"point_count\"]", worker)
