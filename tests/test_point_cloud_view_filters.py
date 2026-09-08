import unittest
from pyforestscan_qgis.core.point_cloud.view_filters import visible_classes_after_changes


class ClassVisibilityTests(unittest.TestCase):
    def test_hidden_all_is_not_confused_with_unfiltered(self):
        self.assertEqual(visible_classes_after_changes([], {231: True}), [231])

    def test_unobserved_classes_keep_visibility(self):
        result = visible_classes_after_changes(None, {2: False})
        self.assertEqual(len(result), 255)
        self.assertIn(255, result)
        self.assertNotIn(2, result)

    def test_solo_and_arbitrary_values_survive_updates(self):
        self.assertEqual(visible_classes_after_changes([231], {5: True}), [5, 231])
        self.assertEqual(visible_classes_after_changes([231], {231: False}), [])

    def test_invalid_class_is_rejected(self):
        for value in (-1, 256, "5", True):
            with self.assertRaises(ValueError):
                visible_classes_after_changes(None, {value: True})
