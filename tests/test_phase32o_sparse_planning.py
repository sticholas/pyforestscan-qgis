from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

from pyforestscan_qgis.core.source_aware_processing import NativeSource, SourceAwareWorkPlanner, SpatialExtent
from pyforestscan_qgis.core.work_unit_geometry import NormalizedPolygonGeometry
from pyforestscan_qgis.core.ept_occupancy import load_ept_occupancy


def scattered_fixture(count: int = 27) -> str:
    parts = []
    for index in range(count):
        x = (index % 9) * 6000.0
        y = (index // 9) * 40000.0
        parts.append(f"(({x} {y}, {x + 500} {y}, {x + 500} {y + 300}, {x} {y + 300}, {x} {y}))")
    return "MULTIPOLYGON (" + ", ".join(parts) + ")"


class Phase32OSparsePlanningTests(unittest.TestCase):
    def plan(self, wkt: str):
        polygon = NormalizedPolygonGeometry.from_wkt(wkt, processing_crs="EPSG:6635")
        bounds = SpatialExtent(*polygon.bounds)
        source = NativeSource(Path("ept.json"), bounds, point_count=110_008_858_527, source_type="ept")
        return SourceAwareWorkPlanner().plan(
            repository_kind="ept", sources=(source,), polygon_envelope=bounds,
            processing_crs="EPSG:6635", product="chm", resolution=1,
            normalized_polygon=polygon,
        )

    def test_scattered_multipolygon_never_materializes_global_envelope_skips(self):
        plan = self.plan(scattered_fixture())
        self.assertEqual(plan.component_count, 27)
        self.assertEqual(plan.skipped_count, 0)
        self.assertEqual(plan.candidate_count, plan.required_count)
        self.assertEqual(plan.required_count, 27)
        self.assertGreater(plan.outside_polygon_count_estimate, 1000)
        self.assertGreater(plan.estimated_point_range[1], plan.estimated_point_range[0])
        self.assertTrue(all(unit.component_ids for unit in plan.work_units))
        self.assertTrue(all(unit.read_block_id and unit.science_block_id and unit.checkpoint_tile_id for unit in plan.work_units))
        self.assertTrue(all(unit.core_extent.width >= 300 for unit in plan.work_units))
        self.assertTrue(all(unit.core_extent.height >= 300 for unit in plan.work_units))

    def test_balanced_ranges_never_leave_rounding_slivers(self):
        ranges = SourceAwareWorkPlanner._balanced_ranges(0, 701, 700)
        self.assertEqual(ranges, ((0, 350), (350, 701)))
        self.assertEqual(sum(end - start for start, end in ranges), 701)
        self.assertGreaterEqual(min(end - start for start, end in ranges), 350)

    def test_small_component_uses_direct_science_block(self):
        plan = self.plan("POLYGON ((0 0, 500 0, 500 300, 0 300, 0 0))")
        self.assertEqual(plan.required_count, 1)
        self.assertEqual(plan.science_block_count, 1)

    def test_execution_order_is_stable_morton_order(self):
        first = self.plan(scattered_fixture())
        second = self.plan(scattered_fixture())
        self.assertEqual([unit.work_unit_id for unit in first.work_units], [unit.work_unit_id for unit in second.work_units])
        self.assertEqual([unit.morton_code for unit in first.work_units], sorted(unit.morton_code for unit in first.work_units))
        self.assertEqual([unit.execution_order for unit in first.work_units], list(range(1, first.required_count + 1)))

    def test_nearby_components_receive_one_transport_cluster(self):
        plan = self.plan("MULTIPOLYGON (((0 0, 50 0, 50 50, 0 50, 0 0)), ((100 0, 150 0, 150 50, 100 50, 100 0)))")
        self.assertEqual(plan.component_count, 2)
        self.assertEqual(plan.cluster_count, 1)
        self.assertEqual({unit.transport_cluster_id for unit in plan.work_units}, {"tc-0001"})

    def test_global_grid_alignment_is_preserved(self):
        text = "MULTIPOLYGON (((0 0, 500 0, 500 300, 0 300, 0 0)), ((6000 40000, 6500 40000, 6500 40300, 6000 40300, 6000 40000)))"
        plan = self.plan(text)
        for unit in plan.work_units:
            self.assertEqual(unit.core_extent.xmin, plan.grid.origin_x + unit.column_start * plan.grid.resolution)
            self.assertEqual(unit.core_extent.ymin, plan.grid.origin_y + unit.row_start * plan.grid.resolution)
        polygon = NormalizedPolygonGeometry.from_wkt(text, processing_crs="EPSG:6635")
        self.assertAlmostEqual(sum(unit.polygon_intersection_area for unit in plan.work_units), sum(polygon.component_areas))

    def test_normal_preflight_source_omits_scheduler_jargon(self):
        source = (Path(__file__).parents[1] / "pyforestscan_qgis" / "core" / "polygon_batch.py").read_text(encoding="utf-8")
        formatter = source[source.index("def polygon_preflight_text"):source.index("def execute_polygon_batch")]
        self.assertIn("Processing regions:", formatter)
        self.assertNotIn("Processing grid:", formatter)
        self.assertNotIn("Outside polygon:", formatter)

    def test_ept_hierarchy_prunes_before_work_unit_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "ept-hierarchy").mkdir()
            (root / "ept.json").write_text(json.dumps({"bounds": [0, 0, 0, 1000, 1000, 100]}), encoding="utf-8")
            (root / "ept-hierarchy" / "0-0-0-0.json").write_text(json.dumps({"0-0-0-0": 1, "1-0-0-0": 10}), encoding="utf-8")
            occupancy = load_ept_occupancy(root / "ept.json")
            self.assertIsNotNone(occupancy)
            polygon = NormalizedPolygonGeometry.from_wkt("MULTIPOLYGON (((0 0, 400 0, 400 400, 0 400, 0 0)), ((600 600, 900 600, 900 900, 600 900, 600 600)))", processing_crs="EPSG:6635")
            extent = SpatialExtent(*polygon.bounds)
            plan = SourceAwareWorkPlanner().plan(repository_kind="ept", sources=(NativeSource(root / "ept.json", extent, source_type="ept"),), polygon_envelope=extent, processing_crs="EPSG:6635", product="chm", resolution=1, normalized_polygon=polygon)
            self.assertEqual(plan.required_count, 1)
            self.assertEqual(plan.pruned_by_hierarchy, 1)


if __name__ == "__main__":
    unittest.main()
