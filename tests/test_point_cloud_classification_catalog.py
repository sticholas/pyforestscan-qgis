"""QGIS-free LAS classification catalog and editor-source contracts."""
from pathlib import Path
import unittest

from pyforestscan_qgis.core.point_cloud.las_classification import (
    FORESTRY_TARGET_PRESETS, STANDARD_CLASSES, classification_entry, classification_warning,
    classification_counts_summary, classification_target_guidance,
    classify_while_selecting_decision, forestry_target_presets)


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

    def test_authoritative_count_summary_is_named_compact_and_bounded(self):
        counts = ((2, 1234567), (5, 20), (18, 3), (64, 2))
        self.assertEqual(classification_counts_summary(counts),
            "Ground: 1,234,567 | High vegetation: 20 | High noise: 3 | +1 classes")
        self.assertEqual(classification_counts_summary(()), "")
        for counts, limit in ((((256, 1),), 3), (((2, -1),), 3), (((2, 1),), 0)):
            with self.assertRaises(ValueError):
                classification_counts_summary(counts, limit=limit)

    def test_target_guidance_calls_out_scientific_and_las_risks(self):
        self.assertIn("DTM", classification_target_guidance(2))
        self.assertIn("canopy", classification_target_guidance(5))
        self.assertIn("excluded", classification_target_guidance(18))
        self.assertIn("reserved", classification_target_guidance(8))
        self.assertIn("user-defined", classification_target_guidance(64))

    def test_forestry_presets_are_explicit_valid_and_unique(self):
        self.assertEqual(FORESTRY_TARGET_PRESETS, (2, 3, 4, 5, 6, 9, 7, 18))
        presets = forestry_target_presets()
        self.assertEqual(tuple(item.code for item in presets), FORESTRY_TARGET_PRESETS)
        self.assertEqual(len(set(FORESTRY_TARGET_PRESETS)), len(FORESTRY_TARGET_PRESETS))
        self.assertTrue(all(item.common_target and item.color for item in presets))


if __name__ == "__main__":
    unittest.main()
