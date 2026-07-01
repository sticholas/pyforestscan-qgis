"""Tests for Advanced Processing Toolbox request mapping without QGIS."""

from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from pyforestscan_qgis.core.adapter import PyForestScanAdapter
from pyforestscan_qgis.core.advanced_processing import (
    AdvancedCanopyCoverParameters,
    AdvancedChmParameters,
    AdvancedHagParameters,
    AdvancedRumpleParameters,
    AdvancedVoxelParameters,
    build_canopy_cover_request,
    build_chm_request,
    build_hag_request,
    build_pad_request,
    build_pai_request,
    build_rumple_request,
)
from pyforestscan_qgis.core.exceptions import ProcessingError
from pyforestscan_qgis.core.types import HagNormalizationRequest, PaiRequest


class AdvancedProcessingTests(unittest.TestCase):
    """Advanced request builders and adapter mappings are QGIS-free."""

    def test_advanced_chm_none_interpolation_maps_to_adapter_none(self) -> None:
        request = build_chm_request(
            AdvancedChmParameters(
                input_path="plot.laz",
                output_path=Path("chm.tif"),
                crs="EPSG:32610",
                x_resolution=1.0,
                y_resolution=2.0,
                interpolation="none",
                interpolate_valid_region=True,
                clean_edges=True,
            )
        )

        self.assertIsNone(request.interpolation)
        self.assertEqual(1.0, request.grid_resolution)
        self.assertEqual(2.0, request.y_resolution)
        self.assertTrue(request.interp_valid_region)
        self.assertTrue(request.interp_clean_edges)

    def test_voxel_request_validation_and_mapping(self) -> None:
        params = AdvancedVoxelParameters(
            input_path="plot.laz",
            output_path=Path("pai.tif"),
            crs="EPSG:32610",
            x_resolution=2.0,
            y_resolution=3.0,
            voxel_height=1.5,
            min_height=2.0,
            max_height=20.0,
            beer_lambert_constant=0.8,
            drop_ground=False,
        )

        pad_request = build_pad_request(params)
        pai_request = build_pai_request(params)

        self.assertEqual(3.0, pad_request.y_resolution)
        self.assertEqual(0.8, pad_request.beer_lambert_constant)
        self.assertFalse(pai_request.drop_ground)
        self.assertEqual(20.0, pai_request.max_height)

    def test_canopy_cover_request_exposes_height_range_and_k(self) -> None:
        request = build_canopy_cover_request(
            AdvancedCanopyCoverParameters(
                input_path="plot.laz",
                output_path=Path("cover.tif"),
                crs="EPSG:32610",
                x_resolution=1.0,
                y_resolution=1.0,
                voxel_height=1.0,
                min_height=2.0,
                max_height=30.0,
                beer_lambert_constant=0.9,
                drop_ground=True,
                extinction_coefficient=0.45,
            )
        )

        self.assertEqual(2.0, request.canopy_height_threshold)
        self.assertEqual(30.0, request.max_height)
        self.assertEqual(0.45, request.extinction_coefficient)
        self.assertEqual(0.9, request.beer_lambert_constant)

    def test_rumple_requires_csv_output(self) -> None:
        with self.assertRaises(ProcessingError):
            build_rumple_request(
                AdvancedRumpleParameters(
                    input_path="plot.laz",
                    output_path=Path("rumple.tif"),
                    crs="EPSG:32610",
                    x_resolution=1.0,
                    y_resolution=1.0,
                )
            )

    def test_hag_request_documents_optional_output_behavior(self) -> None:
        request = build_hag_request(AdvancedHagParameters(input_path="plot.laz", crs="EPSG:32610"))

        self.assertIsInstance(request, HagNormalizationRequest)
        self.assertIsNone(request.output_path)

    def test_adapter_pai_mapping_uses_explicit_y_resolution_and_beer_lambert(self) -> None:
        calls: dict[str, object] = {}
        point_array = np.array(
            [(0.0, 0.0, 1.0), (1.0, 1.0, 3.0)],
            dtype=[("X", "f8"), ("Y", "f8"), ("HeightAboveGround", "f8")],
        )
        fake_pyforestscan = types.ModuleType("pyforestscan")
        fake_handlers = types.ModuleType("pyforestscan.handlers")
        fake_handlers.read_lidar = lambda input_path, crs, hag=True: [point_array]  # type: ignore[attr-defined]

        def assign_voxels(arr, voxel_resolution):
            calls["voxel_resolution"] = voxel_resolution
            return np.ones((2, 2, 2), dtype="f8"), [0.0, 2.0, 0.0, 2.0]

        def calculate_pad(voxels, voxel_height=1.0, beer_lambert_constant=1.0, drop_ground=True):
            calls["pad_args"] = (voxel_height, beer_lambert_constant, drop_ground)
            return np.ones((2, 2, 2), dtype="f8")

        def calculate_pai(pad, voxel_height, min_height=1.0, max_height=None):
            calls["pai_args"] = (voxel_height, min_height, max_height)
            return np.ones((2, 2), dtype="f8")

        def create_geotiff(layer, output_file, crs, spatial_extent):
            Path(output_file).write_text("fake", encoding="utf-8")

        fake_pyforestscan.assign_voxels = assign_voxels  # type: ignore[attr-defined]
        fake_pyforestscan.calculate_pad = calculate_pad  # type: ignore[attr-defined]
        fake_pyforestscan.calculate_pai = calculate_pai  # type: ignore[attr-defined]
        fake_handlers.create_geotiff = create_geotiff  # type: ignore[attr-defined]

        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            sys.modules,
            {"pyforestscan": fake_pyforestscan, "pyforestscan.handlers": fake_handlers},
        ):
            output = Path(temp_dir) / "pai.tif"
            PyForestScanAdapter().create_pai(
                PaiRequest(
                    input_path="plot.laz",
                    output_path=output,
                    grid_resolution=2.0,
                    y_resolution=3.0,
                    voxel_height=1.5,
                    crs="EPSG:32610",
                    min_height=2.0,
                    max_height=10.0,
                    beer_lambert_constant=0.7,
                    drop_ground=False,
                )
            )

        self.assertEqual((2.0, 3.0, 1.5), calls["voxel_resolution"])
        self.assertEqual((1.5, 0.7, False), calls["pad_args"])
        self.assertEqual((1.5, 2.0, 10.0), calls["pai_args"])

    def test_adapter_hag_without_output_reports_limitation(self) -> None:
        point_array = np.array([(0.0, 0.0, 1.0)], dtype=[("X", "f8"), ("Y", "f8"), ("HeightAboveGround", "f8")])
        fake_handlers = types.ModuleType("pyforestscan.handlers")
        fake_handlers.read_lidar = lambda *args, **kwargs: [point_array]  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"pyforestscan.handlers": fake_handlers}):
            result = PyForestScanAdapter().normalize_heights(
                HagNormalizationRequest(input_path="plot.laz", crs="EPSG:32610")
            )

        self.assertFalse(result.written)
        self.assertEqual(1, result.point_count)
        self.assertIn("in-memory", result.limitation or "")


if __name__ == "__main__":
    unittest.main()
