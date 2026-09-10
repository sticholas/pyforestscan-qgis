"""QGIS-free bounded classification audit and journal-replay tests."""
from dataclasses import replace
from pathlib import Path
import unittest

try:
    import numpy as np
except ImportError:
    np = None
try:
    import shapely
except ImportError:
    shapely = None

from pyforestscan_qgis.core.point_cloud.classification_audit import (
    CHUNK_SIZE, audit_classification_chunks, audit_source_classifications,
    classification_audit_summary,
    classification_findings)


@unittest.skipIf(np is None, "numpy unavailable")
class ClassificationAuditTests(unittest.TestCase):
    def points(self):
        values = np.zeros(6, dtype=[("X", "f8"), ("Y", "f8"), ("Z", "f8"),
                                    ("Classification", "u1"), ("Withheld", "u1")])
        values["X"] = [0, 1, 2, 3, 4, 5]
        values["Classification"] = [1, 1, 2, 5, 7, 18]
        return values

    def operation(self, *, attribute="Classification", value=5):
        from pyforestscan_qgis.core.point_cloud.selection import SelectionDefinition
        from pyforestscan_qgis.core.point_cloud.session import AttributeEditOperation
        definition = SelectionDefinition("selection", "session", "a" * 64, "LAS",
            ((0,-1),(2,-1),(2,1),(0,1),(0,-1)), "EPSG:32605")
        return AttributeEditOperation("operation", "now", (definition,), attribute, value, 3)

    @unittest.skipIf(shapely is None, "shapely unavailable")
    def test_full_source_counts_replay_active_journal_in_bounded_chunks(self):
        progress = []
        report = audit_classification_chunks((self.points()[:3], self.points()[3:]),
            (self.operation(),), 6, progress=progress.append)
        self.assertEqual(report["source_classification_counts"], {1:2, 2:1, 5:1, 7:1, 18:1})
        self.assertEqual(report["effective_classification_counts"], {5:4, 7:1, 18:1})
        self.assertEqual(report["classification_changed"], 3)
        self.assertEqual(progress, [3, 6])
        self.assertTrue(report["bounded_memory"])
        self.assertEqual(report["chunk_size"], CHUNK_SIZE)
        self.assertIn("6 source points", classification_audit_summary(report))

    @unittest.skipIf(shapely is None, "shapely unavailable")
    def test_removal_withheld_and_review_findings_are_explicit(self):
        remove = self.operation(attribute="DELETE_ON_EXPORT", value=1)
        withheld = replace(self.operation(attribute="Withheld", value=1), operation_id="withheld")
        report = audit_classification_chunks((self.points(),), (withheld, remove), 6)
        self.assertEqual(report["removed_on_export"], 3)
        self.assertEqual(report["withheld"], 0)
        self.assertTrue(any("omission" in item for item in report["findings"]))

    def test_cancellation_and_incomplete_reads_never_publish_a_report(self):
        with self.assertRaises(InterruptedError):
            audit_classification_chunks((self.points(),), (), 6, cancelled=lambda: True)
        with self.assertRaises(ValueError):
            audit_classification_chunks((self.points()[:2],), (), 6)

    def test_health_flags_are_factual_and_zero_safe(self):
        self.assertEqual(classification_findings({}, 0), ())
        findings = classification_findings({1:8, 18:2}, 10, withheld_points=1)
        self.assertTrue(any("Ground" in item for item in findings))
        self.assertTrue(any("80.0%" in item for item in findings))
        self.assertTrue(any("Noise" in item for item in findings))
        self.assertTrue(any("Withheld" in item for item in findings))

    def test_source_wrapper_verifies_both_sides_and_uses_bounded_iterator(self):
        class Source:
            source_type = "LAS"
            path = "source.las"
            def __init__(self):
                self.verifications = 0
            def verify(self, **_kwargs):
                self.verifications += 1
        class Pipeline:
            def __init__(self, spec):
                self.spec = spec
            def iterator(self, **kwargs):
                self.module.iterator_kwargs = kwargs
                return iter((self.module.points,))
        source = Source()
        module = type("PDAL", (), {})()
        module.points = self.points()
        Pipeline.module = module
        module.Pipeline = Pipeline
        report = audit_source_classifications(source, (), 6, pdal_module=module)
        self.assertEqual(source.verifications, 2)
        self.assertEqual(module.iterator_kwargs, {"chunk_size": CHUNK_SIZE, "prefetch": 0})
        self.assertEqual(report["source_point_count"], 6)

    def test_managed_worker_persists_and_invalidates_audit_with_journal_changes(self):
        source = (Path(__file__).parents[1] / "pyforestscan_qgis" / "viewer" /
                  "editor_worker.py").read_text(encoding="utf-8")
        self.assertIn('elif action == "classification_audit":', source)
        self.assertIn('session.visibility["classification_audit"] = report', source)
        self.assertGreaterEqual(source.count('session.visibility.pop("classification_audit", None)'), 2)
