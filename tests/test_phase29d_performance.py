"""Phase 29D adaptive performance and scalability contracts."""
from pathlib import Path
import unittest

from pyforestscan_qgis.core.adaptive_processing import AdaptivePlannerInputs, PilotMeasurement, calibrate_from_pilot, derive_adaptive_plan
from pyforestscan_qgis.core.processing_performance import summarize_plan
from pyforestscan_qgis.core.resource_estimation import estimate_work_unit_resources, estimated_point_memory_bytes
from pyforestscan_qgis.core.scientific_equivalence import compare_raster_values
from pyforestscan_qgis.core.source_aware_processing import NativeSource, SourceAwareWorkPlanner, SpatialExtent

class AdaptivePerformanceTests(unittest.TestCase):
    def plan(self, width, height, *, kind="ept", path="https://example/ept.json", memory=8*1024**3, cpu=8, polygon_wkt=None):
        extent = SpatialExtent(0, 0, width, height)
        source = NativeSource(Path(path), extent, source_type=kind)
        return SourceAwareWorkPlanner().plan(repository_kind=kind, sources=(source,), polygon_envelope=extent,
            processing_crs="EPSG:26904", product="chm", resolution=1, available_memory_bytes=memory,
            cpu_count=cpu, polygon_wkt=polygon_wkt)

    def test_planner_and_executor_share_point_memory_model(self):
        self.assertGreater(estimated_point_memory_bytes(), 200)
        estimate = estimate_work_unit_resources(1_000_000)
        expected = int(1_000_000 * estimated_point_memory_bytes()) + estimate.raster_bytes + 128*1024**2
        self.assertEqual(estimate.estimated_memory, expected)

    def test_small_job_uses_one_direct_request(self):
        summary = summarize_plan(self.plan(200, 200))
        self.assertEqual(summary.execution_path, "direct_single_request")
        self.assertEqual(summary.required_units, 1)
        self.assertEqual(summary.startup_count, 1)

    def test_scale_matrix_has_no_historical_fixed_count(self):
        counts = [self.plan(w, h).required_count for w, h in ((200,200),(2000,1500),(10000,7000),(30000,20000))]
        self.assertEqual(counts[0], 1)
        self.assertEqual(counts, sorted(counts))
        self.assertNotIn(counts[-1], (88, 89, 120))

    def test_memory_pressure_reduces_unit_size_and_concurrency(self):
        low = self.plan(8000, 8000, kind="folder", path="/local/tile.laz", memory=2*1024**3)
        high = self.plan(8000, 8000, kind="folder", path="/local/tile.laz", memory=32*1024**3)
        self.assertLessEqual(low.target_work_unit_width, high.target_work_unit_width)
        self.assertLessEqual(low.concurrency_limit, high.concurrency_limit)

    def test_network_ept_is_serial_and_local_native_is_bounded(self):
        ept = self.plan(8000, 8000, path="https://example/ept.json")
        native = self.plan(8000, 8000, kind="folder", path="/local/tile.laz", memory=32*1024**3)
        self.assertEqual(ept.concurrency_limit, 1)
        self.assertGreaterEqual(native.concurrency_limit, 1)
        self.assertLessEqual(native.concurrency_limit, 4)

    def test_large_native_source_subdivides_from_estimated_workload(self):
        plan = self.plan(10000, 7000, kind="folder", path="/local/unknown-size.laz")
        self.assertGreater(plan.required_count, 1)
        self.assertTrue(all(unit.unit_type.value == "subdivided_large_source" for unit in plan.work_units))

    def test_effective_concurrency_never_exceeds_runnable_units(self):
        plan = self.plan(200, 200, kind="folder", path="/local/small.laz", memory=32*1024**3)
        self.assertEqual(plan.required_count, 1)
        self.assertEqual(plan.concurrency_limit, 1)

    def test_read_amplification_is_measured(self):
        plan = self.plan(10000, 7000)
        self.assertGreater(plan.read_amplification, 1.0)
        self.assertLess(plan.read_amplification, 2.0)
        self.assertEqual(summarize_plan(plan).read_amplification, plan.read_amplification)

    def test_one_pbm_coordinator_startup_owns_all_work_units(self):
        summary = summarize_plan(self.plan(10000, 7000))
        self.assertGreater(summary.required_units, 1)
        self.assertEqual(summary.startup_count, 1)

    def test_exact_polygon_filters_units_without_changing_grid(self):
        base = self.plan(3000, 2000)
        filtered = self.plan(3000, 2000, polygon_wkt="POLYGON ((0 0, 3000 0, 500 2000, 0 2000, 0 0))")
        self.assertEqual(base.grid.grid_signature, filtered.grid.grid_signature)
        self.assertEqual(filtered.skipped_count, 0)
        self.assertGreater(filtered.outside_polygon_count_estimate, 0)

    def test_pilot_is_advisory_and_skipped_for_small_plan(self):
        small = derive_adaptive_plan(AdaptivePlannerInputs(200, 200, 40000, 1))
        self.assertFalse(small.pilot_required)
        large = derive_adaptive_plan(AdaptivePlannerInputs(10000, 7000, 70000000, 1))
        calibrated = calibrate_from_pilot(large, PilotMeasurement(1_000_000, 8_000_000, 20, 15, 5, 800*1024**2, 2), 8*1024**3, 8)
        self.assertFalse(calibrated.pilot_required)
        self.assertNotEqual(calibrated.target_width, large.target_width)

    def test_synthetic_partition_assembly_is_numerically_identical(self):
        reference = (1.0, 2.0, -9999.0, 4.0, 5.0, 6.0)
        adaptive = (1.0, 2.0) + (-9999.0, 4.0) + (5.0, 6.0)
        result = compare_raster_values(reference, adaptive, tolerance=0.0)
        self.assertTrue(result.equivalent)
        self.assertEqual(result.maximum_absolute_difference, 0.0)
        self.assertEqual(result.rmse, 0.0)

    def test_equivalence_rejects_nodata_or_pixel_changes(self):
        nodata = compare_raster_values((1.0, -9999.0), (1.0, 0.0))
        changed = compare_raster_values((1.0, 2.0), (1.0, 2.1), tolerance=0.01)
        self.assertFalse(nodata.equivalent)
        self.assertFalse(changed.equivalent)

if __name__ == "__main__": unittest.main()
