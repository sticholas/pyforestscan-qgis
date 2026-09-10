"""QGIS-free LAS classification catalog and editor-source contracts."""
from pathlib import Path
import unittest

from pyforestscan_qgis.core.point_cloud.las_classification import (
    STANDARD_CLASSES, classification_entry, classification_warning,
    classify_while_selecting_decision)


class ClassificationCatalogTests(unittest.TestCase):
    def test_standard_catalog_is_complete_unique_and_uint8_safe(self):
        self.assertEqual([item.code for item in STANDARD_CLASSES], list(range(23)))
        self.assertEqual(len({item.label for item in STANDARD_CLASSES}), 23)
        self.assertTrue(all(item.color.startswith("#") and len(item.color) == 7
                            for item in STANDARD_CLASSES))
        for code in (2,3,4,5,6,9,17,18):
            self.assertTrue(classification_entry(code).common_target)

    def test_reserved_and_user_defined_targets_are_explicit(self):
        for code in (8,12,23,63):
            self.assertTrue(classification_entry(code).reserved)
            self.assertIn("reserved", classification_warning(code))
        self.assertEqual(classification_entry(64).name, "User-defined")
        self.assertIn("document", classification_warning(255))
        self.assertEqual(classification_warning(5), "")
        for code in (-1,256,True,1.0):
            with self.assertRaises(ValueError):
                classification_entry(code)

    def test_editor_consumes_catalog_instead_of_a_partial_tuple(self):
        source = (Path(__file__).resolve().parents[1] /
                  "pyforestscan_qgis/ui/point_cloud_editor.py").read_text()
        self.assertIn("STANDARD_CLASSES", source)
        self.assertNotIn('((0,"Created"),(1,"Unclassified")', source)

    def test_classify_while_selecting_only_accepts_new_nonempty_replace(self):
        replace = [{"selection_mode":"REPLACE"}]
        self.assertTrue(classify_while_selecting_decision(True,"select",replace,20).apply)
        for enabled,action,definitions,count in (
                (False,"select",replace,20), (True,"stage",replace,20),
                (True,"select",replace,0), (True,"select",[{"selection_mode":"ADD"}],20),
                (True,"select",[{"selection_mode":"SUBTRACT"}],20)):
            decision = classify_while_selecting_decision(enabled,action,definitions,count)
            self.assertFalse(decision.apply)
        self.assertIn("Replace", classify_while_selecting_decision(
            True,"select",[{"selection_mode":"ADD"}],20).message)
        for enabled,count in ((1,20),(True,-1)):
            with self.assertRaises(ValueError):
                classify_while_selecting_decision(enabled,"select",replace,count)


if __name__ == "__main__":
    unittest.main()
