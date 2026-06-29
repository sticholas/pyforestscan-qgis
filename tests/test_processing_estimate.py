"""Tests for Mission Control processing time estimates."""

from __future__ import annotations

import unittest

from pyforestscan_qgis.core.processing_estimate import estimate_processing_time


class ProcessingEstimateTests(unittest.TestCase):
    """Processing estimates stay deterministic and QGIS-free."""

    def test_estimate_uses_point_count_grid_and_products(self) -> None:
        """Known point count and grid size produce a readable medium-confidence range."""
        estimate = estimate_processing_time(
            {
                "estimates": {"cells": 1_000_000, "height_bins": 6},
                "products": [
                    {"product": "chm", "requested": True},
                    {"product": "pad", "requested": True},
                    {"product": "rumple", "requested": True},
                ],
            },
            {"point_statistics": {"point_count": 2_000_000}},
        )

        self.assertEqual("medium", estimate.confidence)
        self.assertEqual(3, estimate.product_count)
        self.assertEqual(2_000_000, estimate.point_count)
        self.assertIn("to", estimate.display_range)
        self.assertGreater(estimate.maximum_seconds, estimate.minimum_seconds)

    def test_estimate_without_dataset_report_is_low_confidence(self) -> None:
        """Missing Dataset Explorer details should not crash estimation."""
        estimate = estimate_processing_time(
            {
                "products": [{"product": "canopy_cover", "requested": True}],
            }
        )

        self.assertEqual("low", estimate.confidence)
        self.assertIsNone(estimate.point_count)
        self.assertEqual(1, estimate.product_count)
        self.assertGreaterEqual(estimate.minimum_seconds, 10)


if __name__ == "__main__":
    unittest.main()
