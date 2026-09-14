"""Phase 27L EPT bounds contract regression tests."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyforestscan_qgis.core.adapter import _read_lidar_spatial_kwargs, prepare_ept_bounds
from pyforestscan_qgis.core.ept_bounds import EptBounds, EptBoundsError, validate_pdal_bounds_expression, validate_pyforestscan_bounds_value
from pyforestscan_qgis.core.types import ChmRequest


class EptBoundsContractTests(unittest.TestCase):
    def test_tuple_of_tuples_normalizes_to_list_ranges(self) -> None:
        bounds = EptBounds.from_value(
            ((204988.883967812, 205580.438378822), (2144384.290553354, 2146573.21175823)),
            crs="EPSG:6635",
        )

        value = bounds.to_pyforestscan_value()

        self.assertIsInstance(value[0], list)
        self.assertIsInstance(value[1], list)
        self.assertEqual(value, ([204988.883967812, 205580.438378822], [2144384.290553354, 2146573.21175823]))
        self.assertEqual(bounds.to_pdal_range_string(), "([204988.883967812, 205580.438378822], [2144384.290553354, 2146573.21175823])")

    def test_three_dimensional_bounds(self) -> None:
        bounds = EptBounds.from_value(([1, 2], [3, 4], [5, 6]), crs="EPSG:32610")
        self.assertEqual(bounds.to_pyforestscan_value(), ([1.0, 2.0], [3.0, 4.0], [5.0, 6.0]))

    def test_json_round_trip(self) -> None:
        original = EptBounds(1, 2, 3, 4, crs="EPSG:32610", transformed=True)
        restored = EptBounds.from_value(original.to_json())
        self.assertEqual(restored.to_pyforestscan_value(), ([1.0, 2.0], [3.0, 4.0]))

    def test_bad_values_rejected(self) -> None:
        with self.assertRaises(EptBoundsError):
            EptBounds.from_value(([1, 1], [3, 4]), crs="EPSG:32610")
        with self.assertRaises(EptBoundsError):
            EptBounds.from_value(([True, 2], [3, 4]), crs="EPSG:32610")
        with self.assertRaises(EptBoundsError):
            EptBounds.from_value("((1, 2), (3, 4))", crs="EPSG:32610")

    def test_malformed_regression_expression_is_invalid(self) -> None:
        result = validate_pdal_bounds_expression("((204988.88, 205580.44), (2144384.29, 2146573.21))")
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "Each PDAL coordinate range must use square brackets.")

    def test_final_value_assertion_rejects_tuple_ranges(self) -> None:
        with self.assertRaises(EptBoundsError):
            validate_pyforestscan_bounds_value(((1.0, 2.0), (3.0, 4.0)))

    def test_adapter_is_authoritative_conversion_point(self) -> None:
        request = ChmRequest(
            input_path=Path("ept.json"),
            output_path=Path("chm.tif"),
            grid_resolution=1.0,
            crs="EPSG:6635",
            bounds=((204988.883967812, 205580.438378822), (2144384.290553354, 2146573.21175823)),
        )
        kwargs = _read_lidar_spatial_kwargs(request, hag=True)
        self.assertEqual(kwargs["bounds"], ([204988.883967812, 205580.438378822], [2144384.290553354, 2146573.21175823]))
        self.assertEqual([type(item).__name__ for item in kwargs["bounds"]], ["list", "list"])
        self.assertEqual(prepare_ept_bounds(request.bounds, crs=request.crs).to_pdal_range_string(), "([204988.883967812, 205580.438378822], [2144384.290553354, 2146573.21175823])")


if __name__ == "__main__":
    unittest.main()
