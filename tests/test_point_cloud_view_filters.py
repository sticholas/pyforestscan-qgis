import unittest
from pyforestscan_qgis.core.point_cloud.view_filters import (
    class_visibility_rows, isolated_class, visible_classes_after_changes)


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

    def test_catalog_rows_include_effective_resident_counts_without_claiming_source_totals(self):
        rows = class_visibility_rows([2, 5], [5], {"2": 1234, "18": 7})
        self.assertEqual([row.code for row in rows], [2, 5, 18])
        self.assertEqual(rows[0].label, "Ground (2)")
        self.assertEqual(rows[0].text, "Ground (2) | ~1,234 in view")
        self.assertFalse(rows[0].visible)
        self.assertTrue(rows[1].visible)
        self.assertEqual(rows[2].label, "High noise (18)")

    def test_isolation_and_row_inputs_are_las_uint8_safe(self):
        self.assertEqual(isolated_class(5), [5])
        for call in (lambda: isolated_class(True),
                     lambda: class_visibility_rows([256]),
                     lambda: class_visibility_rows([], None, {"bad": 1}),
                     lambda: class_visibility_rows([], None, {"2": -1})):
            with self.assertRaises(ValueError):
                call()
