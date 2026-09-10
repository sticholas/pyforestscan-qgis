"""Bounded effective object accounting without QGIS."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

try:
    import numpy as np
    import shapely
except ImportError:
    np = shapely = None

from pyforestscan_qgis.core.point_cloud.object_audit import (
    audit_object_chunks, effective_object_audit_report,
    effective_object_audit_summary)
from pyforestscan_qgis.core.point_cloud.object_id_policy import ObjectIdPolicy
from pyforestscan_qgis.core.point_cloud.selection import SelectionDefinition, SelectionResult
from pyforestscan_qgis.core.point_cloud.session import PointCloudEditSession, SourceIdentity


@unittest.skipIf(np is None or shapely is None, "Managed NumPy/Shapely tier")
class EffectiveObjectAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        source_path = Path(self.temp.name)/"source.las"
        source_path.write_bytes(b"immutable")
        self.source = SourceIdentity.capture(source_path)
        self.session = PointCloudEditSession(self.source, "EPSG:32605",
            ("X","Y","Z","Classification","Tree_ID"))
        self.points = np.array([
            (1.,1.,1.,5,1),(2.,2.,2.,5,1),(3.,3.,3.,5,2),
            (4.,4.,4.,5,2),(5.,5.,5.,5,0)],
            dtype=[("X","f8"),("Y","f8"),("Z","f8"),
                   ("Classification","u1"),("Tree_ID","i4")])
        definition = SelectionDefinition("move", self.session.session_id, self.source.sha256,
            "LAS", ((0,0),(2.5,0),(2.5,2.5),(0,2.5),(0,0)), "EPSG:32605")
        result = SelectionResult("move", "RESOLVED", 2, (1,1,1,2,2,2),
            ((5,2),),1,2,None,None,(self.source.path,),.01,2)
        policy = ObjectIdPolicy(self.source.sha256, "Tree_ID", "int32",
                                -(2**31), 2**31-1, 0)
        self.session.stage_object_id((definition,), result, policy, 3)

    def test_audit_replays_journal_into_atomic_disk_backed_counts(self):
        destination = Path(self.temp.name)/"effective.sqlite"
        progress = []
        report = audit_object_chunks((self.points[:2], self.points[2:]),
            self.session.operations, 5, "Tree_ID", destination,
            self.source.sha256, 0, progress=progress.append)
        self.assertEqual(progress, [2,5])
        self.assertEqual(report["source_object_count"], 3)
        self.assertEqual(report["effective_object_count"], 3)
        self.assertEqual(report["object_id_changed"], 2)
        self.assertEqual(report["effective_unassigned_count"], 1)
        self.assertEqual(report["largest_effective_objects"], [[2,2],[3,2],[0,1]])
        self.assertTrue(report["bounded_memory"])
        self.assertEqual(effective_object_audit_report(destination)["audit_id"],
                         report["audit_id"])
        self.assertIn("2 staged membership changes",
                      effective_object_audit_summary(report))

    def test_failed_or_cancelled_audit_preserves_prior_atomic_report(self):
        destination = Path(self.temp.name)/"effective.sqlite"
        original = audit_object_chunks((self.points,), self.session.operations, 5,
            "Tree_ID", destination, self.source.sha256, 0)
        with self.assertRaises(InterruptedError):
            audit_object_chunks((self.points,), self.session.operations, 5,
                "Tree_ID", destination, self.source.sha256, 0,
                cancelled=lambda: True)
        self.assertEqual(effective_object_audit_report(destination)["audit_id"],
                         original["audit_id"])
        self.assertFalse(list(Path(self.temp.name).glob("*.building-*")))

    def test_count_or_field_mismatch_fails_without_publication(self):
        for expected, field in ((6,"Tree_ID"),(5,"TreeScore")):
            destination = Path(self.temp.name)/f"bad-{expected}-{field}.sqlite"
            with self.subTest(expected=expected, field=field), self.assertRaises(ValueError):
                audit_object_chunks((self.points,), self.session.operations, expected,
                    field, destination, self.source.sha256, 0)
            self.assertFalse(destination.exists())
