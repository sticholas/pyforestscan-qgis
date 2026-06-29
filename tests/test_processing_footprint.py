"""Tests for Mission Control processing footprint summaries."""

from __future__ import annotations

import unittest

from pyforestscan_qgis.core.processing_footprint import estimate_processing_footprint


class ProcessingFootprintTests(unittest.TestCase):
    """Processing footprint estimates stay deterministic and QGIS-free."""

    def test_footprint_accounts_for_pad_bands_and_rumple_csv(self) -> None:
        """PAD uses height-bin bands while Rumple contributes negligible storage."""
        footprint = estimate_processing_footprint(
            {
                "output_folder": "outputs",
                "estimates": {"columns": 100, "rows": 50, "cells": 5_000, "height_bins": 6},
                "products": [
                    {"product": "chm", "label": "CHM", "requested": True},
                    {"product": "pad", "label": "PAD", "requested": True},
                    {"product": "rumple", "label": "Rumple", "requested": True},
                ],
            }
        )

        self.assertEqual("100 columns x 50 rows", footprint.display_dimensions)
        self.assertEqual(7, footprint.total_bands)
        self.assertEqual(5_000 * 7 * 4, footprint.estimated_bytes)
        rumple = next(item for item in footprint.product_footprints if item.product == "rumple")
        self.assertEqual(0, rumple.estimated_bytes)
        self.assertIn("Minimal", rumple.storage_note)

    def test_footprint_can_estimate_cells_from_bounds_and_resolution(self) -> None:
        """Dataset bounds plus grid resolution can derive raster dimensions."""
        footprint = estimate_processing_footprint(
            {
                "parameters": {"grid_resolution": 2.0},
                "products": [{"product": "canopy_cover", "label": "Canopy Cover"}],
            },
            {"geometry": {"bounds": {"min_x": 0, "max_x": 10, "min_y": 0, "max_y": 6}}},
        )

        self.assertEqual(5, footprint.columns)
        self.assertEqual(3, footprint.rows)
        self.assertEqual(15, footprint.cells)
        self.assertEqual(15 * 4, footprint.estimated_bytes)
        self.assertEqual("medium", footprint.confidence)

    def test_footprint_without_dimensions_is_low_confidence(self) -> None:
        """Missing dimensions should not crash footprint creation."""
        footprint = estimate_processing_footprint(
            {"products": [{"product": "pai", "label": "PAI"}]}
        )

        self.assertEqual("low", footprint.confidence)
        self.assertEqual("Unknown", footprint.display_dimensions)
        self.assertEqual(0, footprint.estimated_bytes)
        self.assertIn("Processing time depends", footprint.caveat)


if __name__ == "__main__":
    unittest.main()
