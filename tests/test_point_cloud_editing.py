"""Editing-loop contracts and managed-runtime integration, without QGIS."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import tempfile
import unittest

from pyforestscan_qgis.core.point_cloud.session import PointCloudEditSession, SourceIdentity
from pyforestscan_qgis.core.point_cloud.selection import SelectionDefinition, SelectionResult


class EditingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        path = self.root / "original.las"
        path.write_bytes(b"original identity")
        self.source = SourceIdentity.capture(path)
        self.session = PointCloudEditSession(self.source, "SOURCE_LOCAL:" + self.source.sha256)
        self.definition = SelectionDefinition("selection", self.session.session_id, self.source.sha256, "LAS",
            ((0, 0), (4, 0), (0, 4), (0, 0)), self.session.source_crs)
        self.result = SelectionResult("selection", "RESOLVED", 3, (0, 0, 0, 4, 4, 4),
                                      ((2, 3),), 0, 4, None, None, (self.source.path,), .01, 3)

    def test_resolved_edits_roundtrip_and_cursor(self):
        for attribute, value in (("Classification", 5), ("Classification", 18),
                                 ("Withheld", 1), ("DELETE_ON_EXPORT", 1)):
            self.session.stage_resolved([self.definition], self.result, attribute, value)
        self.session.undo()
        path = self.session.save(self.root / "session.json")
        loaded = PointCloudEditSession.load(path)
        self.assertEqual(len(loaded.operations), 3)
        self.assertTrue(loaded.can_redo)
        loaded.redo()
        self.assertEqual(loaded.operations[-1].attribute, "DELETE_ON_EXPORT")
        self.source.verify()

    def test_only_resolved_current_source_can_stage(self):
        for definition, result in (
            (replace(self.definition, session_id="another"), self.result),
            (self.definition, replace(self.result, resolution_status="PREVIEW")),
            (self.definition, replace(self.result, selection_id="stale")),
            (self.definition, replace(self.result, resolved_point_count=0))):
            with self.assertRaises(ValueError):
                self.session.stage_resolved([definition], result, "Classification", 2)

    def test_attributes_and_values_are_restricted(self):
        for attribute, value in (("X", 1), ("Classification", 256), ("Withheld", 2),
                                 ("DELETE_ON_EXPORT", -1), ("Classification", True)):
            with self.assertRaises(ValueError):
                self.session.stage_resolved([self.definition], self.result, attribute, value)

    def test_new_edit_discards_redo_and_legacy_is_retained(self):
        self.session.stage_resolved([self.definition], self.result, "Classification", 5)
        self.session.undo()
        self.session.stage_resolved([self.definition], self.result, "Withheld", 1)
        self.assertFalse(self.session.can_redo)

    def test_changed_source_cannot_replay_saved_edits(self):
        self.session.stage_resolved([self.definition], self.result, "Classification", 2)
        path = self.session.save(self.root / "saved.json")
        Path(self.source.path).write_bytes(b"changed original")
        with self.assertRaisesRegex(ValueError, "fingerprint changed"):
            PointCloudEditSession.load(path)
        self.assertTrue(path.is_file())

    def test_session_never_overwrites_source_or_hardlink(self):
        with self.assertRaises(ValueError):
            self.session.save(self.source.path)
        import os
        linked = self.root / "alias.json"
        os.link(self.source.path, linked)
        with self.assertRaises(ValueError):
            self.session.save(linked)
        self.source.verify()

    def test_new_journal_retains_original_value_contract(self):
        operation = self.session.stage_resolved([self.definition], self.result, "Withheld", 1)
        self.assertEqual(operation.previous_value_contract, "REPLAY_ORIGINAL_THEN_ORDERED_JOURNAL")
        self.assertEqual(operation.definitions[0].source_fingerprint, self.source.sha256)
        self.assertEqual(operation.definitions[0].session_id, self.session.session_id)

    def test_empty_las_header_strings_do_not_break_pdal_writer(self):
        from pyforestscan_qgis.core.point_cloud.export import writer_header_options
        self.assertEqual(writer_header_options({"system_id": "", "project_id": None,
            "global_encoding": 0, "offset_x": 0, "minor_version": 4}),
            {"global_encoding": 0, "offset_x": 0, "minor_version": 4})

    @unittest.skipUnless(importlib.util.find_spec("shapely"), "Managed geometry tier")
    def test_disjoint_operations_do_not_affect_unselected_points(self):
        import numpy as np
        from pyforestscan_qgis.core.point_cloud.edit_plan import EditExecutionPlan
        points = np.array([(100, 100, 1, 5, 0)], dtype=[("X", "f8"), ("Y", "f8"),
            ("Z", "f8"), ("Classification", "u1"), ("Withheld", "u1")])
        self.session.stage_resolved([self.definition], self.result, "DELETE_ON_EXPORT", 1)
        edited, removed = EditExecutionPlan(self.session.operations).apply(points)
        self.assertTrue(np.array_equal(points, edited))
        self.assertFalse(removed.any())

    @unittest.skipUnless(importlib.util.find_spec("shapely"), "Managed geometry tier")
    def test_overlap_undo_and_original_filter_membership(self):
        import numpy as np
        from pyforestscan_qgis.core.point_cloud.edit_plan import EditExecutionPlan
        points = np.array([(0, 0, 1, 2, 0), (1, 1, 2, 2, 0), (3, 3, 1, 5, 0)],
                          dtype=[("X", "f8"), ("Y", "f8"), ("Z", "f8"), ("Classification", "u1"), ("Withheld", "u1")])
        self.session.stage_resolved([self.definition], self.result, "Classification", 5)
        second = replace(self.definition, selection_id="second", classification_filter=(2,), z_filter=(2, 2))
        self.session.stage_resolved([second], replace(self.result, selection_id="second"), "Classification", 7)
        edited, removed = EditExecutionPlan(self.session.operations).apply(points)
        self.assertEqual(edited["Classification"].tolist(), [5, 7, 5])
        self.assertFalse(removed.any())
        self.session.undo()
        edited, _ = EditExecutionPlan(self.session.operations).apply(points)
        self.assertEqual(edited["Classification"].tolist(), [5, 5, 5])
        self.session.redo()
        self.assertEqual(EditExecutionPlan(self.session.operations).apply(points)[0]["Classification"].tolist(), [5, 7, 5])
        self.assertEqual(points["Classification"].tolist(), [2, 2, 5])


if __name__ == "__main__":
    unittest.main()
