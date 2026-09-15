import unittest

from pyforestscan_qgis.core.point_cloud.profile_editing import (
    insert_midpoint, insert_vertex, move_vertex, normalize_path, remove_vertex,
    replace_path,
)


class ProfileEditingTests(unittest.TestCase):
    def setUp(self):
        self.path = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0))

    def test_endpoints_and_intermediate_vertices_can_move(self):
        self.assertEqual(move_vertex(self.path, 0, (-1, -2))[0], (-1.0, -2.0))
        self.assertEqual(move_vertex(self.path, 1, (4, 5))[1], (4.0, 5.0))
        self.assertEqual(move_vertex(self.path, 2, (11, 12))[-1], (11.0, 12.0))

    def test_insert_midpoint_and_explicit_vertex(self):
        self.assertEqual(insert_midpoint(self.path, 0)[1], (5.0, 0.0))
        self.assertEqual(insert_vertex(self.path, 1, (5, 2))[1], (5.0, 2.0))

    def test_remove_only_allows_intermediate_vertices(self):
        self.assertEqual(remove_vertex(self.path, 1), ((0.0, 0.0), (10.0, 10.0)))
        with self.assertRaises(ValueError):
            remove_vertex(self.path, 0)
        with self.assertRaises(ValueError):
            remove_vertex(((0, 0), (1, 1)), 1)

    def test_replace_path_keeps_slice_metadata_and_updates_endpoints(self):
        geometry = {"a": (0, 0), "b": (10, 10), "thickness": 2, "crs": "EPSG:32604"}
        updated = replace_path(geometry, ((1, 2), (3, 4)))
        self.assertEqual(updated["a"], (1.0, 2.0))
        self.assertEqual(updated["b"], (3.0, 4.0))
        self.assertEqual(updated["thickness"], 2)
        self.assertEqual(updated["crs"], "EPSG:32604")

    def test_invalid_and_degenerate_paths_are_rejected(self):
        with self.assertRaises(ValueError):
            normalize_path(((0, 0),))
        with self.assertRaises(ValueError):
            normalize_path(((0, 0), (0, 0)))
        with self.assertRaises(ValueError):
            move_vertex(self.path, 1, (float("nan"), 1))


if __name__ == "__main__":
    unittest.main()
