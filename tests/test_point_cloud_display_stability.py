import unittest

from pyforestscan_qgis.core.point_cloud.display_stability import DisplayTelemetryStabilizer


class DisplayTelemetryStabilityTests(unittest.TestCase):
    def test_first_observation_is_immediate(self):
        stable = DisplayTelemetryStabilizer()
        result = stable.observe({"displayed": 4000, "budget": 10000, "quality": "Automatic", "detail": "Interactive"})
        self.assertEqual(result["displayed"], 4000)
        self.assertEqual(result["detail"], "Interactive")

    def test_transient_refinement_values_do_not_replace_summary(self):
        stable = DisplayTelemetryStabilizer(confirmations=2)
        stable.observe({"displayed": 4000, "detail": "Interactive"})
        self.assertEqual(stable.observe({"displayed": 900000, "detail": "Refining"})["displayed"], 4000)
        self.assertEqual(stable.observe({"displayed": 4000, "detail": "Interactive"})["displayed"], 4000)
        self.assertEqual(stable.observe({"displayed": 900000, "detail": "Refining"})["displayed"], 4000)

    def test_confirmed_value_is_published(self):
        stable = DisplayTelemetryStabilizer(confirmations=2)
        stable.observe({"displayed": 4000, "detail": "Interactive"})
        stable.observe({"displayed": 900000, "detail": "Refining"})
        result = stable.observe({"displayed": 900000, "detail": "Refining"})
        self.assertEqual(result["displayed"], 900000)
        self.assertEqual(result["detail"], "Refining")

    def test_reset_starts_new_view_immediately(self):
        stable = DisplayTelemetryStabilizer()
        stable.observe({"displayed": 4000})
        stable.reset()
        self.assertEqual(stable.observe({"displayed": 120000})["displayed"], 120000)


if __name__ == "__main__":
    unittest.main()
