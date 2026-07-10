"""QGIS-free tests for Phase 27D PAD, Rumple, and polygon-folder planning."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from pyforestscan_qgis.core.lidar_inventory import LidarFolderRequest, discover_lidar_sources, inventory_cache_needs_update, write_inventory_cache
from pyforestscan_qgis.core.localized_rumple import LocalizedRumpleSpec, calculate_localized_rumple, calculate_rumple_from_chm_window
from pyforestscan_qgis.core.pad_products import (
    PadDerivativeSpec,
    calculate_pad_derivative,
    pad_band_indices_for_range,
    pad_band_mapping,
    pad_derivative_filename,
    pad_metadata_tags,
    select_pad_slice_band,
)
from pyforestscan_qgis.core.polygon_processing import build_polygon_processing_plan, polygon_preflight_summary
from pyforestscan_qgis.core.spatial_selection import Bounds2D, polygon_selection_from_wkt

ROOT = Path(__file__).resolve().parents[1]


class PadProductsTests(unittest.TestCase):
    """PAD remains a volume with explicit derived visualizations."""

    def test_pad_band_height_mapping_and_metadata(self) -> None:
        mapping = pad_band_mapping(3, 2.0, drop_ground=True)

        self.assertEqual((mapping[0].min_height, mapping[0].max_height), (2.0, 4.0))
        self.assertEqual(mapping[1].description, "PAD 4-6 m")
        tags = pad_metadata_tags(2.0, 0.8, True, 3)
        self.assertEqual(tags["pyforestscan_representation"], "3D height-binned volume stored as multiband GeoTIFF")
        self.assertIn("1:2-4m", tags["band_height_mapping"])

    def test_pad_derivative_slice_projection_and_integrated(self) -> None:
        volume = np.array(
            [
                [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
                [[7.0, 8.0, 9.0], [10.0, 11.0, 12.0]],
            ]
        )

        slice_result = calculate_pad_derivative(volume, PadDerivativeSpec("slice", Path("slice.tif"), 1.0, band_index=2), drop_ground=False)
        max_result = calculate_pad_derivative(volume, PadDerivativeSpec("maximum", Path("max.tif"), 1.0, min_height=1.0, max_height=3.0), drop_ground=False)
        mean_result = calculate_pad_derivative(volume, PadDerivativeSpec("mean", Path("mean.tif"), 1.0), drop_ground=False)
        integrated = calculate_pad_derivative(volume, PadDerivativeSpec("integrated", Path("int.tif"), 2.0), drop_ground=False)

        np.testing.assert_array_equal(slice_result, np.array([[2.0, 5.0], [8.0, 11.0]]))
        np.testing.assert_array_equal(max_result, np.array([[3.0, 6.0], [9.0, 12.0]]))
        np.testing.assert_array_equal(mean_result, np.array([[2.0, 5.0], [8.0, 11.0]]))
        np.testing.assert_array_equal(integrated, np.array([[12.0, 30.0], [48.0, 66.0]]))

    def test_pad_range_and_filename_helpers(self) -> None:
        self.assertEqual(select_pad_slice_band(10.0, None, 12, 1.0), 10)
        self.assertEqual(pad_band_indices_for_range(5, 2.0, 2.0, 6.0, drop_ground=False), (2, 3))
        self.assertEqual(pad_derivative_filename("maximum", min_height=2.0, max_height=30.0), "pad_max_2m_30m.tif")


class RumpleExtensionTests(unittest.TestCase):
    """Native Rumple is scalar; localized Rumple is a documented extension."""

    def test_flat_chm_rumple_is_one(self) -> None:
        value = calculate_rumple_from_chm_window(np.ones((4, 4)) * 10.0, (1.0, 1.0))

        self.assertAlmostEqual(value, 1.0, places=6)

    def test_corrugated_chm_rumple_is_greater_than_one(self) -> None:
        chm = np.array([[0.0, 2.0, 0.0], [2.0, 0.0, 2.0], [0.0, 2.0, 0.0]])
        value = calculate_rumple_from_chm_window(chm, (1.0, 1.0))

        self.assertGreater(value, 1.0)

    def test_insufficient_data_returns_nodata(self) -> None:
        chm = np.array([[np.nan, np.nan], [np.nan, 1.0]])
        value = calculate_rumple_from_chm_window(chm, (1.0, 1.0), min_valid_fraction=0.75, nodata=-9999.0)

        self.assertEqual(value, -9999.0)

    def test_localized_rumple_grid_shape(self) -> None:
        chm = np.ones((5, 5))
        result = calculate_localized_rumple(chm, LocalizedRumpleSpec(Path("rumple.tif"), (1.0, 1.0), window_width=3, window_height=3, stride=2))

        self.assertEqual(result.shape, (2, 2))
        self.assertTrue(np.allclose(result, 1.0))

    def test_adapter_has_chm_cache_for_rumple_reuse(self) -> None:
        source = (ROOT / "pyforestscan_qgis/core/adapter.py").read_text(encoding="utf-8")

        self.assertIn("self._chm_cache", source)
        self.assertIn("reused compatible CHM", source)
        self.assertIn("internally generated for Rumple", source)
        self.assertIn("native_pyforestscan_output", source)


class PolygonFolderPlanningTests(unittest.TestCase):
    """Folder inventory and polygon planning avoid unbounded reads."""

    def test_recursive_discovery_and_ept_json_recognition(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.laz").write_text("", encoding="utf-8")
            (root / "metadata.json").write_text("{}", encoding="utf-8")
            nested = root / "tiles"
            nested.mkdir()
            (nested / "ept.json").write_text(json.dumps({"bounds": [0, 0, 0, 10, 10, 5], "points": 100}), encoding="utf-8")
            inventory = discover_lidar_sources(LidarFolderRequest(root, recursive=True))

        self.assertEqual([item.source_type for item in inventory.sources], ["laz", "ept"])
        self.assertEqual(inventory.sources[1].bounds, Bounds2D(0.0, 0.0, 10.0, 10.0))

    def test_inventory_cache_detects_changed_and_deleted_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lidar = root / "a.las"
            lidar.write_text("1", encoding="utf-8")
            inventory = discover_lidar_sources(LidarFolderRequest(root))
            cache = root / ".pyforestscan" / "inventory.json"
            self.assertTrue(inventory_cache_needs_update(cache, inventory))
            write_inventory_cache(cache, inventory)
            self.assertFalse(inventory_cache_needs_update(cache, inventory))
            lidar.write_text("changed", encoding="utf-8")
            changed = discover_lidar_sources(LidarFolderRequest(root))
            self.assertTrue(inventory_cache_needs_update(cache, changed))

    def test_polygon_bounds_and_intersection_plan(self) -> None:
        polygon = polygon_selection_from_wkt("POLYGON ((1 1, 4 1, 4 4, 1 4, 1 1))", "EPSG:32610")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ept = root / "ept.json"
            ept.write_text(json.dumps({"bounds": [0, 0, 0, 10, 10, 5], "srs": {"authority": "EPSG:32610"}, "points": 50}), encoding="utf-8")
            inventory = discover_lidar_sources(LidarFolderRequest(root))
            plan = build_polygon_processing_plan(inventory, polygon, root / "out", ("chm",))

        self.assertEqual(len(plan.selected_sources), 1)
        self.assertEqual(plan.intersections[0].ept_bounds, ((1.0, 4.0), (1.0, 4.0)))
        self.assertIn("Intersecting sources: 1 of 1", polygon_preflight_summary(plan))

    def test_crs_mismatch_and_large_workload_warnings(self) -> None:
        polygon = polygon_selection_from_wkt("POLYGON ((0 0, 5 0, 5 5, 0 5, 0 0))", "EPSG:32610")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ept = root / "ept.json"
            ept.write_text(json.dumps({"bounds": [0, 0, 0, 10, 10, 5], "srs": {"authority": "EPSG:4326"}, "points": 999}), encoding="utf-8")
            inventory = discover_lidar_sources(LidarFolderRequest(root))
            plan = build_polygon_processing_plan(inventory, polygon, root / "out", ("chm",), large_point_threshold=10)

        self.assertTrue(any("CRS differs" in warning for warning in plan.warnings))
        self.assertTrue(any("Large point estimate" in warning for warning in plan.warnings))

    def test_polygon_folder_entry_point_moved_to_batch(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        dataset_source = source[source.index("class DatasetPage"):source.index("class BatchPage")]
        batch_source = source[source.index("class BatchPage"):]

        self.assertNotIn("Process Folder by Polygon", dataset_source)
        self.assertIn("Polygon Area Processing", batch_source)
        self.assertIn("Run Polygon Batch", batch_source)
        self.assertIn("run_polygon_batch_preflight", batch_source)


if __name__ == "__main__":
    unittest.main()
