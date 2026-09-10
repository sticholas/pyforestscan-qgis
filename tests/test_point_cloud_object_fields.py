"""QGIS-free tests for schema-independent object-field discovery."""
from pathlib import Path
import unittest

try:
    import numpy as np
except ImportError:
    np = None

from pyforestscan_qgis.core.point_cloud.object_fields import (
    CHUNK_SIZE, MAX_NONSTANDARD_FIELDS, discover_object_fields, discover_source_object_fields,
    normalized_dimension_name, object_field_discovery_summary, semantic_object_role)


@unittest.skipIf(np is None, "numpy unavailable")
class ObjectFieldDiscoveryTests(unittest.TestCase):
    def points(self):
        values = np.zeros(8, dtype=[
            ("X", "f8"), ("Y", "f8"), ("Z", "f8"), ("Classification", "u1"),
            ("Tree_ID", "i4"), ("CanopyGroup42", "u2"), ("HeightAboveGround", "f4"),
            ("UniqueSequence", "u8")])
        values["Tree_ID"] = [1,1,1,2,2,3,3,3]
        values["CanopyGroup42"] = [9,9,10,10,9,10,9,10]
        values["HeightAboveGround"] = [0.2,1.3,2.7,4.1,5.4,6.8,8.2,9.9]
        values["UniqueSequence"] = range(8)
        return values

    def test_name_normalization_and_role_are_hints_not_schema_requirements(self):
        self.assertEqual(normalized_dimension_name(" Pred-Instance "), "predinstance")
        self.assertEqual(semantic_object_role("PredInstance"), "INSTANCE")
        self.assertEqual(semantic_object_role("CanopyGroup42"), "CLUSTER")
        self.assertEqual(semantic_object_role("ArbitraryCode"), "CATEGORICAL")

    def test_discovers_named_and_arbitrary_repeated_integer_fields(self):
        points = self.points()
        # Deliberately use a statistically categorical name with no semantic token.
        points.dtype.names = tuple("ArbitraryCode" if n == "CanopyGroup42" else n
                                   for n in points.dtype.names)
        report = discover_object_fields((points[:3], points[3:]), 8)
        candidates = {item["name"]: item for item in report["candidate_fields"]}
        self.assertEqual(candidates["Tree_ID"]["role"], "TREE")
        self.assertEqual(candidates["Tree_ID"]["confidence"], "HIGH")
        self.assertEqual(candidates["ArbitraryCode"]["role"], "CATEGORICAL")
        self.assertEqual(candidates["ArbitraryCode"]["confidence"], "MEDIUM")
        self.assertNotIn("Classification", candidates)
        self.assertFalse(next(item for item in report["nonstandard_numeric_fields"]
                              if item["name"] == "HeightAboveGround")["candidate"])
        self.assertFalse(next(item for item in report["nonstandard_numeric_fields"]
                              if item["name"] == "UniqueSequence")["candidate"])
        self.assertTrue(report["bounded_memory"])
        self.assertEqual(report["chunk_size"], CHUNK_SIZE)
        self.assertEqual(report["sampling_strategy"], "EVENLY_SPACED_SOURCE_ORDER")

    def test_progress_cancellation_count_and_schema_guards(self):
        progress = []
        report = discover_object_fields((self.points()[:4], self.points()[4:]), 8,
                                        progress=progress.append)
        self.assertEqual(progress, [4,8])
        self.assertEqual(report["source_point_count"], 8)
        with self.assertRaises(InterruptedError):
            discover_object_fields((self.points(),), 8, cancelled=lambda: True)
        with self.assertRaisesRegex(ValueError, "verified header"):
            discover_object_fields((self.points()[:2],), 8)
        changed = self.points()[["X", "Y", "Z"]]
        with self.assertRaisesRegex(ValueError, "changed"):
            discover_object_fields((self.points()[:2], changed[2:]), 8)

    def test_source_wrapper_verifies_both_sides_and_uses_bounded_iterator(self):
        class Source:
            source_type = "LAS"
            path = "source.las"
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
        report = discover_source_object_fields(source, 8, pdal_module=module)
        self.assertEqual(source.verifications, 2)
        self.assertEqual(module.iterator_kwargs, {"chunk_size":CHUNK_SIZE, "prefetch":0})
        self.assertFalse(report["modifies_source_or_journal"])

    def test_summary_is_compact_and_validated(self):
        report = discover_object_fields((self.points(),), 8)
        self.assertIn("candidate", object_field_discovery_summary(report))
        with self.assertRaises(ValueError):
            object_field_discovery_summary({})

    def test_excessive_extra_dimensions_fail_instead_of_exceeding_memory_bound(self):
        dtype = [("X", "f8"), ("Y", "f8"), ("Z", "f8")]
        dtype.extend((f"Extra{index}", "u1") for index in range(MAX_NONSTANDARD_FIELDS + 1))
        with self.assertRaisesRegex(ValueError, "bounded object-field discovery"):
            discover_object_fields((np.zeros(1, dtype=dtype),), 1)

    def test_worker_action_is_explicit_and_session_backed(self):
        source = (Path(__file__).parents[1] / "pyforestscan_qgis" / "viewer" /
                  "editor_worker.py").read_text(encoding="utf-8")
        self.assertIn('elif action == "discover_object_fields":', source)
        self.assertIn('session.visibility["object_field_discovery"] = report', source)
