import unittest
from pyforestscan_qgis.core.point_cloud.view_policy import next_view_budget


class ViewPolicyTests(unittest.TestCase):
    def budget(self, previous=100000, **kwargs):
        return next_view_budget(previous, viewport_pixels=600000, **kwargs)

    def test_navigation_preserves_structural_floor(self):
        result = self.budget(moving=True, root_points=177426, velocity=1)
        self.assertGreaterEqual(result.points, result.floor)
        self.assertGreaterEqual(result.floor, 177426)
        self.assertFalse(result.prefetch)

    def test_settling_refines_under_ceiling(self):
        self.assertGreater(self.budget(moving=False, frame_ms=16).points, 100000)
        self.assertLessEqual(self.budget(2000000, moving=False, frame_ms=16).points, 1200000)

    def test_memory_pressure_limits_budget(self):
        self.assertGreaterEqual(self.budget(moving=False, memory_pressure=.9).points, 100000)
        self.assertEqual(self.budget(moving=False, available_bytes=0).points, 0)

    def test_source_count_bounds_budget(self):
        self.assertEqual(self.budget(moving=False, source_points=5).points, 5)

    def test_bad_measurements_rejected(self):
        for kwargs in ({"frame_ms": float("nan")}, {"memory_pressure": 2},
                       {"available_bytes": -1}, {"source_points": -1}):
            with self.assertRaises(ValueError):
                self.budget(moving=False, **kwargs)

    def test_first_frame_is_bounded(self):
        self.assertLessEqual(self.budget(0, moving=False).points, 500000)

    def test_tiny_source_does_not_thin_during_motion(self):
        for ms in (16, 50, 100):
            self.assertEqual(self.budget(20000, moving=True, velocity=3,
                                        frame_ms=ms, source_points=20000).points, 20000)

    def test_continuous_motion_cannot_decay_to_zero(self):
        points = 1000000
        for _ in range(200):
            result = self.budget(points, moving=True, velocity=1, root_points=177426)
            points = result.points
        self.assertGreaterEqual(points, result.floor)
        self.assertGreaterEqual(points, 177426)

    def test_changes_are_smooth_above_floor(self):
        result = self.budget(900000, moving=True, frame_ms=60, velocity=1)
        self.assertGreaterEqual(result.points, 900000 * .92)
        self.assertLessEqual(result.points, 900000 * 1.08)

    def test_viewport_changes_budget(self):
        small = next_view_budget(1000000, viewport_pixels=100000, moving=True)
        large = next_view_budget(1000000, viewport_pixels=2000000, moving=True)
        self.assertLess(small.ceiling, large.ceiling)

    def test_velocity_continuum(self):
        slow = self.budget(900000, moving=True, velocity=.01)
        fast = self.budget(900000, moving=True, velocity=1)
        self.assertLess(slow.screen_error, fast.screen_error)
        self.assertGreaterEqual(slow.points, fast.points)

    def test_memory_cap_is_not_claimed_as_free_memory(self):
        result = self.budget(moving=True, root_points=177426, available_bytes=1024)
        self.assertLess(result.ceiling, 177426)

    def test_source_classes(self):
        for count, label in ((20000, 'TINY'), (2287408, 'SMALL'), (10000000, 'MEDIUM'),
                             (104819538, 'LARGE'), (110008858527, 'MASSIVE_INDEXED')):
            self.assertEqual(self.budget(moving=False, source_points=count).source_class, label)

    def test_quality_presets_are_display_only_limits(self):
        low = self.budget(moving=False, quality='Performance')
        high = self.budget(moving=False, quality='High Detail')
        self.assertLess(low.ceiling, high.ceiling)
        with self.assertRaises(ValueError):
            self.budget(moving=False, quality='invalid')


if __name__ == "__main__":
    unittest.main()
