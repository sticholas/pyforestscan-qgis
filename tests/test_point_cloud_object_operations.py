"""Authoritative object split and merge contracts without QGIS."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pyforestscan_qgis.core.point_cloud.object_operations import (
    ObjectSplitSource, begin_object_split, restrict_selection_to_object,
    validate_merge_target, validate_split_count)
from pyforestscan_qgis.core.point_cloud.selection import SelectionDefinition, SelectionResult
from pyforestscan_qgis.core.point_cloud.session import PointCloudEditSession, SourceIdentity


class ObjectOperationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        source_path = Path(self.temp.name)/"source.las"
        source_path.write_bytes(b"immutable")
        self.source = SourceIdentity.capture(source_path)
        self.session = PointCloudEditSession(self.source, "EPSG:32605",
            ("X", "Y", "Z", "Classification", "Tree_ID"))
        self.definition = SelectionDefinition("current", self.session.session_id,
            self.source.sha256, "LAS", ((0,0),(10,0),(10,10),(0,10),(0,0)),
            "EPSG:32605", attribute_filters=(("Intensity",10,20),))
        self.result = SelectionResult("current", "RESOLVED", 40, (0,0,0,10,10,10),
            ((5,40),), 0,10,None,None,(self.source.path,),.1,50)
        self.catalog = {"source_sha256":self.source.sha256, "field":"Tree_ID"}
        self.active = {"field":"Tree_ID", "object_id":7, "point_count":40,
                       "selection_id":"current"}

    def test_begin_split_requires_the_current_exact_object_selection(self):
        split = begin_object_split(self.source.sha256, self.catalog, self.active, self.result)
        self.assertEqual(split.object_id, 7)
        with self.assertRaisesRegex(ValueError, "changed"):
            begin_object_split(self.source.sha256, self.catalog,
                {**self.active, "selection_id":"old"}, self.result)

    def test_split_intersects_every_boolean_step_with_original_object(self):
        add = SelectionDefinition("add", self.session.session_id, self.source.sha256,
            "LAS", ((20,20),(30,20),(30,30),(20,30),(20,20)), "EPSG:32605",
            selection_mode="ADD")
        split = ObjectSplitSource(self.source.sha256, "Tree_ID", 7, 40)
        restricted = restrict_selection_to_object((self.definition, add), split,
                                                   selection_id="split-result")
        self.assertEqual(restricted[-1].selection_id, "split-result")
        self.assertEqual(restricted[0].attribute_filters[-1], ("Tree_ID",7,7))
        self.assertEqual(restricted[1].attribute_filters[-1], ("Tree_ID",7,7))
        self.assertEqual(restricted[0].attribute_filters[0], ("Intensity",10,20))

    def test_split_rejects_empty_and_whole_parent_results(self):
        split = ObjectSplitSource(self.source.sha256, "Tree_ID", 7, 40)
        for count in (0, 40, 41):
            with self.subTest(count=count), self.assertRaises(ValueError):
                validate_split_count(split, count)
        self.assertEqual(validate_split_count(split, 39), 39)

    def test_merge_requires_existing_distinct_target(self):
        self.assertEqual(validate_merge_target(self.catalog, self.active,
                                               {"object_id":9}), 9)
        with self.assertRaisesRegex(ValueError, "different target"):
            validate_merge_target(self.catalog, self.active, {"object_id":7})
        with self.assertRaisesRegex(ValueError, "not present"):
            validate_merge_target(self.catalog, self.active, None)

    def test_worker_routes_split_and_merge_through_existing_object_journal(self):
        worker = (Path(__file__).parents[1]/"pyforestscan_qgis"/"viewer"/
                  "editor_worker.py").read_text(encoding="utf-8")
        self.assertIn('elif action == "split_object":', worker)
        self.assertIn('elif action == "merge_object":', worker)
        self.assertGreaterEqual(worker.count("session.stage_object_id("), 3)
        self.assertIn("restrict_selection_to_object(definitions, split", worker)
        self.assertIn("definitions, result = (), None", worker)
        self.assertNotIn("rendered_point", worker)
