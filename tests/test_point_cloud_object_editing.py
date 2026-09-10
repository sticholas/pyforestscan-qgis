"""Shared-journal object ID editing contracts without QGIS."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

try:
    import numpy as np
except ImportError:
    np = None
try:
    import shapely
except ImportError:
    shapely = None

from pyforestscan_qgis.core.point_cloud.object_id_policy import ObjectIdPolicy
from pyforestscan_qgis.core.point_cloud.selection import SelectionDefinition, SelectionResult
from pyforestscan_qgis.core.point_cloud.session import (
    ObjectIdEditOperation, PointCloudEditSession, SourceIdentity)


class ObjectEditingContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        source_path = Path(self.temp.name)/"source.las"
        source_path.write_bytes(b"immutable object source")
        self.source = SourceIdentity.capture(source_path)
        self.session = PointCloudEditSession(self.source, "EPSG:32605",
                                             ("X","Y","Z","Classification","Tree_ID"))
        self.definition = SelectionDefinition("selection", self.session.session_id,
            self.source.sha256, "LAS", ((0,0),(5,0),(5,5),(0,5),(0,0)), "EPSG:32605",
            attribute_filters=(("Tree_ID",1,1),))
        self.result = SelectionResult("selection", "RESOLVED", 2, (0,0,0,5,5,5),
            ((5,2),), 0,5,None,None,(self.source.path,),.01,2)
        self.policy = ObjectIdPolicy(self.source.sha256, "Tree_ID", "int32",
                                     -(2**31), 2**31-1, 0)

    def test_object_edit_uses_same_journal_cursor_and_roundtrips_schema_three(self):
        operation = self.session.stage_object_id((self.definition,), self.result, self.policy, 8,
                                                 note="Add points to object 8")
        self.assertIsInstance(operation, ObjectIdEditOperation)
        self.assertEqual(operation.previous_value_contract,
                         "REPLAY_ORIGINAL_THEN_ORDERED_JOURNAL")
        self.assertTrue(self.session.can_undo)
        self.session.undo()
        self.assertTrue(self.session.can_redo)
        self.session.redo()
        saved = self.session.save(Path(self.temp.name)/"session.json")
        self.assertIn('"schema_version": 3', saved.read_text(encoding="utf-8"))
        loaded = PointCloudEditSession.load(saved)
        self.assertIsInstance(loaded.operations[0], ObjectIdEditOperation)
        self.assertEqual(loaded.operations[0].value, 8)

    def test_policy_source_field_value_and_selection_are_guarded(self):
        cases = (
            (replace(self.policy, source_sha256="b"*64), self.definition, self.result, 8),
            (replace(self.policy, field="Other_ID"), self.definition, self.result, 8),
            (self.policy, replace(self.definition, session_id="other"), self.result, 8),
            (self.policy, self.definition, replace(self.result, resolution_status="PREVIEW"), 8),
            (self.policy, self.definition, self.result, 2**31),
        )
        for policy, definition, result, value in cases:
            with self.subTest(policy=policy.field, value=value), self.assertRaises(ValueError):
                self.session.stage_object_id((definition,), result, policy, value)

    @unittest.skipIf(np is None or shapely is None, "Managed NumPy/Shapely tier")
    def test_replay_changes_only_authoritative_original_field_members(self):
        from pyforestscan_qgis.core.point_cloud.edit_plan import EditExecutionPlan
        points = np.array([(1,1,1,5,1),(2,2,2,5,1),(8,8,2,5,1),(3,3,3,5,2)],
            dtype=[("X","f8"),("Y","f8"),("Z","f8"),("Classification","u1"),("Tree_ID","i4")])
        self.session.stage_object_id((self.definition,), self.result, self.policy, 8)
        edited, removed = EditExecutionPlan(self.session.operations).apply(points)
        self.assertEqual(edited["Tree_ID"].tolist(), [8,8,1,2])
        self.assertEqual(points["Tree_ID"].tolist(), [1,1,1,2])
        self.assertFalse(removed.any())

    @unittest.skipIf(np is None or shapely is None, "Managed NumPy/Shapely tier")
    def test_later_object_edit_predicates_still_use_original_ids(self):
        from pyforestscan_qgis.core.point_cloud.edit_plan import EditExecutionPlan
        points = np.array([(1,1,1,5,1),(2,2,2,5,1),(3,3,3,5,2)],
            dtype=[("X","f8"),("Y","f8"),("Z","f8"),("Classification","u1"),("Tree_ID","i4")])
        self.session.stage_object_id((self.definition,), self.result, self.policy, 8)
        second = replace(self.definition, selection_id="second")
        self.session.stage_object_id((second,), replace(self.result, selection_id="second"),
                                     self.policy, 9)
        edited, _ = EditExecutionPlan(self.session.operations).apply(points)
        self.assertEqual(edited["Tree_ID"].tolist(), [9,9,2])

    def test_worker_viewer_and_export_share_the_object_edit_contract(self):
        root = Path(__file__).parents[1] / "pyforestscan_qgis"
        worker = (root/"viewer"/"editor_worker.py").read_text(encoding="utf-8")
        viewer = (root/"viewer"/"editor.js").read_text(encoding="utf-8")
        exporter = (root/"core"/"point_cloud"/"export.py").read_text(encoding="utf-8")
        self.assertIn('elif action == "stage_object_id":', worker)
        self.assertIn("session.stage_object_id(definitions, result, policy, value", worker)
        self.assertIn("objectEdited = true", viewer)
        self.assertIn('changes["object_id_changed"]', exporter)

    @unittest.skipIf(np is None or shapely is None, "Managed NumPy/Shapely tier")
    def test_replay_rejects_storage_type_drift_before_assignment(self):
        from pyforestscan_qgis.core.point_cloud.edit_plan import EditExecutionPlan
        points = np.array([(1,1,1,5,1)], dtype=[("X","f8"),("Y","f8"),("Z","f8"),
            ("Classification","u1"),("Tree_ID","i2")])
        self.session.stage_object_id((self.definition,), self.result, self.policy, 8)
        with self.assertRaisesRegex(ValueError, "storage type differs"):
            EditExecutionPlan(self.session.operations).apply(points)

    def test_recovery_rejects_object_field_missing_from_saved_dimensions(self):
        import json
        saved = self.session.save(Path(self.temp.name)/"tampered.json")
        self.session.stage_object_id((self.definition,), self.result, self.policy, 8)
        saved = self.session.save(saved)
        payload = json.loads(saved.read_text(encoding="utf-8"))
        payload["dimensions"].remove("Tree_ID")
        saved.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not present"):
            PointCloudEditSession.load(saved)
