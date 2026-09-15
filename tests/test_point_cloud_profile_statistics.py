import unittest
import numpy as np

from pyforestscan_qgis.core.point_cloud.profile_statistics import (
    distribution_summary, finalize_numeric_statistics)


class ProfileStatisticsTests(unittest.TestCase):
    def test_numeric_statistics_include_percentiles_and_stable_histogram(self):
        result = finalize_numeric_statistics(np.arange(1, 101), count=100,
            minimum=1, maximum=100, total=5050, np=np)
        self.assertEqual(result["count"], 100)
        self.assertEqual(result["quantiles"]["50"], 50.5)
        self.assertEqual(len(result["histogram"]), 16)
        self.assertEqual(result["quantile_scope"], "AUTHORITATIVE_SOURCE_QUERY_BOUNDED_SAMPLE")

    def test_distribution_reports_percentages(self):
        result = distribution_summary({1: 3, 2: 1}, 4)
        self.assertEqual(result[0], {"value": 1, "count": 3, "percentage": 75.0})

    def test_profile_summary_surfaces_extended_analytics(self):
        from pyforestscan_qgis.core.point_cloud.profile import profile_workbench_summary
        summary = profile_workbench_summary({"a": (0, 0), "b": (10, 0), "thickness": 2,
            "crs": "EPSG:32605", "vertical_axis": "Z"}, {
            "source_points": 4, "vertical_stats": {"count": 4, "minimum": 1,
                "maximum": 4, "mean": 2.5, "quantiles": {"25": 1.75, "50": 2.5, "75": 3.25, "95": 3.85},
                "histogram": [{"count": 4}]},
            "returns": [{"value": 1, "count": 3, "percentage": 75.0}],
            "intensity_stats": {"minimum": 10, "maximum": 30, "mean": 20}})
        self.assertIn("AUTHORITATIVE PROFILE CORRIDOR", summary["details"])
        self.assertIn("Percentiles P25/P50/P75/P95", summary["details"])
        self.assertIn("Return number distribution", summary["details"])
        self.assertIn("Intensity range", summary["details"])


if __name__ == "__main__":
    unittest.main()
