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
    AdvancedDtmParameters,
    AdvancedHagParameters,
    AdvancedPointCloudPreprocessParameters,
    AdvancedRumpleParameters,
    AdvancedVoxelParameters,
    build_canopy_cover_request,
    build_chm_request,
    build_dtm_request,
    build_hag_request,
    build_pad_request,
    build_pai_request,
    build_point_cloud_preprocess_request,
    build_rumple_request,
    parse_bounds_text,
)
from pyforestscan_qgis.core.exceptions import ProcessingError
from pyforestscan_qgis.core.types import DtmRequest, HagNormalizationRequest, PaiRequest, PointCloudPreprocessRequest


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

    def test_bounds_parser_supports_xy_and_xyz_bounds(self) -> None:
        self.assertEqual(((1.0, 2.0), (3.0, 4.0)), parse_bounds_text("1,2,3,4"))
        self.assertEqual(((1.0, 2.0), (3.0, 4.0), (5.0, 6.0)), parse_bounds_text("1,2,3,4,5,6"))
        with self.assertRaises(ProcessingError):
            parse_bounds_text("1,2,3")

    def test_dtm_and_preprocess_request_builders(self) -> None:
        dtm = build_dtm_request(
            AdvancedDtmParameters(
                input_path="plot.laz",
                output_path=Path("dtm.tif"),
                crs="EPSG:32610",
                resolution=5.0,
                classify_ground=True,
                nodata=-999.0,
            )
        )
        preprocess = build_point_cloud_preprocess_request(
            AdvancedPointCloudPreprocessParameters(
                input_path="plot.laz",
                output_path=Path("clean.laz"),
                crs="EPSG:32610",
                remove_outliers=True,
                classify_ground=True,
                ground_action="remove_ground",
                add_hag=True,
                hag_method="delaunay",
                filter_hag=True,
                hag_lower_limit=1.0,
                hag_upper_limit=40.0,
                thin_radius=0.25,
                voxelgrid_cell=0.5,
                voxelgrid_mode="first",
            )
        )

        self.assertIsInstance(dtm, DtmRequest)
        self.assertEqual(5.0, dtm.resolution)
        self.assertIsInstance(preprocess, PointCloudPreprocessRequest)
        self.assertEqual("remove_ground", preprocess.ground_action)
        self.assertEqual(0.25, preprocess.thin_radius)

    def test_hag_request_maps_read_lidar_options(self) -> None:
        request = build_hag_request(
            AdvancedHagParameters(
                input_path="plot.laz",
                crs="EPSG:32610",
                bounds_text="1,2,3,4",
                thin_radius=0.5,
                crop_polygon="POLYGON ((0 0, 1 0, 1 1, 0 0))",
            )
        )

        self.assertEqual(((1.0, 2.0), (3.0, 4.0)), request.bounds)
        self.assertEqual(0.5, request.thin_radius)
        self.assertTrue(request.crop_polygon)

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

    def test_adapter_generate_dtm_uses_public_filter_and_calculate_apis(self) -> None:
        calls: list[str] = []
        point_array = np.array([(0.0, 0.0, 1.0, 2)], dtype=[("X", "f8"), ("Y", "f8"), ("Z", "f8"), ("Classification", "u1")])
        fake_pyforestscan = types.ModuleType("pyforestscan")
        fake_handlers = types.ModuleType("pyforestscan.handlers")
        fake_filters = types.ModuleType("pyforestscan.filters")
        fake_handlers.read_lidar = lambda *args, **kwargs: [point_array]  # type: ignore[attr-defined]
        fake_filters.classify_ground_points = lambda arrays: calls.append("classify_ground_points") or arrays  # type: ignore[attr-defined]
        fake_filters.filter_select_ground = lambda arrays: calls.append("filter_select_ground") or arrays  # type: ignore[attr-defined]

        def generate_dtm(points, resolution=2.0):
            calls.append(f"generate_dtm:{resolution}")
            return np.ones((1, 1), dtype="f8"), [0.0, 1.0, 0.0, 1.0]

        def create_geotiff(layer, output_file, crs, spatial_extent, nodata=-9999):
            calls.append(f"create_geotiff:{nodata}")
            Path(output_file).write_text("fake", encoding="utf-8")

        fake_pyforestscan.generate_dtm = generate_dtm  # type: ignore[attr-defined]
        fake_handlers.create_geotiff = create_geotiff  # type: ignore[attr-defined]

        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(sys.modules, {"pyforestscan": fake_pyforestscan, "pyforestscan.handlers": fake_handlers, "pyforestscan.filters": fake_filters}):
            result = PyForestScanAdapter().generate_dtm(
                DtmRequest("plot.laz", Path(temp_dir) / "dtm.tif", "EPSG:32610", resolution=5.0, classify_ground=True, nodata=-999.0)
            )
            self.assertTrue(result.output_path.exists())

        self.assertEqual(["classify_ground_points", "filter_select_ground", "generate_dtm:5.0", "create_geotiff:-999.0"], calls)

    def test_adapter_preprocess_point_cloud_maps_filter_sequence(self) -> None:
        calls: list[str] = []
        point_array = np.array([(0.0, 0.0, 1.0, 2.0, 2)], dtype=[("X", "f8"), ("Y", "f8"), ("Z", "f8"), ("HeightAboveGround", "f8"), ("Classification", "u1")])
        fake_handlers = types.ModuleType("pyforestscan.handlers")
        fake_filters = types.ModuleType("pyforestscan.filters")
        fake_handlers.read_lidar = lambda *args, **kwargs: [point_array]  # type: ignore[attr-defined]

        def passthrough(name):
            return lambda arrays, *args, **kwargs: calls.append(name) or arrays

        fake_filters.remove_outliers_and_clean = passthrough("remove_outliers_and_clean")  # type: ignore[attr-defined]
        fake_filters.classify_ground_points = passthrough("classify_ground_points")  # type: ignore[attr-defined]
        fake_filters.filter_ground = passthrough("filter_ground")  # type: ignore[attr-defined]
        fake_filters.add_height_above_ground = passthrough("add_height_above_ground")  # type: ignore[attr-defined]
        fake_filters.filter_hag = passthrough("filter_hag")  # type: ignore[attr-defined]
        fake_filters.downsample_poisson = passthrough("downsample_poisson")  # type: ignore[attr-defined]
        fake_filters.downsample_voxel = passthrough("downsample_voxel")  # type: ignore[attr-defined]

        def write_las(arrays, output_file, srs=None, compress=True):
            calls.append(f"write_las:{compress}")
            Path(output_file).write_text("fake", encoding="utf-8")

        fake_handlers.write_las = write_las  # type: ignore[attr-defined]

        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(sys.modules, {"pyforestscan.handlers": fake_handlers, "pyforestscan.filters": fake_filters}):
            result = PyForestScanAdapter().preprocess_point_cloud(
                PointCloudPreprocessRequest(
                    input_path="plot.laz",
                    output_path=Path(temp_dir) / "clean.laz",
                    crs="EPSG:32610",
                    remove_outliers=True,
                    classify_ground=True,
                    ground_action="remove_ground",
                    add_hag=True,
                    filter_hag=True,
                    thin_radius=0.5,
                    voxelgrid_cell=1.0,
                    compress=True,
                )
            )
            self.assertTrue(result.output_path.exists())

        self.assertEqual(("remove_outliers_and_clean", "classify_ground_points", "filter_ground", "add_height_above_ground", "filter_hag", "downsample_poisson", "downsample_voxel"), result.operations)
        self.assertEqual("write_las:True", calls[-1])


if __name__ == "__main__":
    unittest.main()
