import unittest
from pyforestscan_qgis.core.point_cloud.view_policy import next_view_budget


class ViewPolicyTests(unittest.TestCase):
    def budget(self, previous=100000, **kwargs):
        return next_view_budget(previous, viewport_pixels=600000, **kwargs)

    def test_navigation_reduces_budget(self):
        result = self.budget(moving=True)
        self.assertLess(result.points, 100000)
        self.assertFalse(result.prefetch)

    def test_settling_refines_under_ceiling(self):
        self.assertGreater(self.budget(moving=False, frame_ms=16).points, 100000)
        self.assertLessEqual(self.budget(2000000, moving=False, frame_ms=16).points, 1200000)

    def test_memory_pressure_limits_budget(self):
        self.assertEqual(self.budget(moving=False, memory_pressure=.9).points, 50000)
        self.assertEqual(self.budget(moving=False, available_bytes=0).points, 0)

    def test_source_count_bounds_budget(self):
        self.assertEqual(self.budget(moving=False, source_points=5).points, 5)

    def test_bad_measurements_rejected(self):
        for kwargs in ({"frame_ms": float("nan")}, {"memory_pressure": 2},
                       {"available_bytes": -1}, {"source_points": -1}):
            with self.assertRaises(ValueError):
                self.budget(moving=False, **kwargs)

    def test_first_frame_is_bounded(self):
        self.assertEqual(self.budget(0, moving=False).points, 100000)


if __name__ == "__main__":
    unittest.main()
