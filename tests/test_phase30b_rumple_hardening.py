import json
import math
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.crs_alignment import compare_crs
from pyforestscan_qgis.core.durable_errors import DurableErrorRecord, read_recent_error, write_recent_error
from pyforestscan_qgis.core.output_registry import generated_output_for_path
from pyforestscan_qgis.core.processing_ui_state import ProcessingUiState, control_policy, reconcile_ui_state, terminal_state_from_result
from pyforestscan_qgis.core.product_finalization import OutputRole, ProductCompletion, RUMPLE_OUTPUT_CONTRACT, rumple_completion
from pyforestscan_qgis.core.rumple_adaptive import RumpleHaloRequirement, RumpleTotals, derive_rumple_grid, rumple_core_extent
from pyforestscan_qgis.core.source_aware_processing import AlignedRasterGrid, SpatialExtent
from pyforestscan_qgis.core.resource_estimation import estimate_work_unit_resources
from pyforestscan_qgis.core.adaptive_processing import AdaptivePlannerInputs, derive_adaptive_plan


EPSG_6635_WKT = 'PROJCS["NAD83(PA11) / UTM zone 5N",GEOGCS["NAD83(PA11)",DATUM["NAD83_National_Spatial_Reference_System_PA11",SPHEROID["GRS 1980",6378137,298.257222101]],PROJECTION["Transverse_Mercator"],PARAMETER["central_meridian",-153],UNIT["metre",1],AUTHORITY["EPSG","6635"]]'


class CrsEquivalenceTests(unittest.TestCase):
    def test_epsg_and_wkt_are_horizontally_equivalent(self):
        result = compare_crs("EPSG:6635", EPSG_6635_WKT)
        self.assertTrue(result.horizontally_equivalent)
        self.assertFalse(result.transformation_required_xy)
        self.assertEqual("EPSG:6635", result.source_horizontal_authority)
        self.assertEqual("EPSG:6635", result.target_horizontal_authority)

    def test_different_horizontal_crs_requires_transform(self):
        result = compare_crs("EPSG:4326", "EPSG:6635")
        self.assertFalse(result.horizontally_equivalent)
        self.assertTrue(result.transformation_required_xy)


class ProcessingStateTests(unittest.TestCase):
    def test_every_terminal_state_unlocks_inputs(self):
        for state in (ProcessingUiState.COMPLETE, ProcessingUiState.FAILED, ProcessingUiState.CANCELLED, ProcessingUiState.INTERRUPTED, ProcessingUiState.RECOVERABLE):
            with self.subTest(state=state):
                policy = control_policy(state)
                self.assertTrue(policy.run_inputs_enabled)
                self.assertFalse(policy.cancel_enabled)

    def test_terminal_matrix(self):
        self.assertEqual(ProcessingUiState.COMPLETE, terminal_state_from_result())
        self.assertEqual(ProcessingUiState.RECOVERABLE, terminal_state_from_result(warning=True))
        self.assertEqual(ProcessingUiState.FAILED, terminal_state_from_result(failed=1))
        self.assertEqual(ProcessingUiState.CANCELLED, terminal_state_from_result(cancelled=True))
        self.assertEqual(ProcessingUiState.INTERRUPTED, terminal_state_from_result(interrupted=True))

    def test_watchdog_repairs_stale_running_projection(self):
        self.assertEqual(ProcessingUiState.COMPLETE, reconcile_ui_state(ProcessingUiState.RUNNING, "complete", coordinator_active=False))
        self.assertEqual(ProcessingUiState.INTERRUPTED, reconcile_ui_state(ProcessingUiState.RUNNING, None, coordinator_active=False))
        self.assertEqual(ProcessingUiState.RUNNING, reconcile_ui_state(ProcessingUiState.RUNNING, "complete", coordinator_active=True))


class ProductFinalizationTests(unittest.TestCase):
    def test_rumple_roles_are_explicit(self):
        self.assertEqual((OutputRole.PRIMARY, OutputRole.SECONDARY, OutputRole.SUPPORTING), tuple(role for _, role in RUMPLE_OUTPUT_CONTRACT.outputs))

    def test_secondary_and_autoload_failures_preserve_primary_success(self):
        self.assertEqual(ProductCompletion.SUCCESS_WITH_WARNING, rumple_completion(raster_valid=True, mask_valid=True, registry_valid=True, summary_valid=False))
        self.assertEqual(ProductCompletion.SUCCESS_WITH_WARNING, rumple_completion(raster_valid=True, mask_valid=True, registry_valid=True, summary_valid=True, autoload_valid=False))
        self.assertEqual(ProductCompletion.FAILED, rumple_completion(raster_valid=True, mask_valid=False, registry_valid=True, summary_valid=True))
        self.assertEqual(ProductCompletion.RECOVERABLE, rumple_completion(raster_valid=True, mask_valid=True, registry_valid=False, summary_valid=True))

    def test_registry_marks_rumple_summary_secondary(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rumple_summary.csv"
            path.write_text("metric,value\n", encoding="utf-8")
            output = generated_output_for_path(path, job_id="job")
            self.assertEqual("secondary", output.output_role)
            self.assertFalse(output.required_for_success)


class AdaptiveRumpleTests(unittest.TestCase):
    def setUp(self):
        self.chm = AlignedRasterGrid.from_extent(SpatialExtent(0, 0, 16, 12), 1.0, "EPSG:6635")
        self.rumple = derive_rumple_grid(self.chm)

    def test_global_grid_has_half_cell_inset_and_reduced_shape(self):
        self.assertEqual((11, 15), (self.rumple.rows, self.rumple.columns))
        self.assertEqual(SpatialExtent(0.5, 0.5, 15.5, 11.5), self.rumple.extent)
        self.assertEqual((0.5, 1.0, 0.0, 11.5, 0.0, -1.0), self.rumple.transform)

    def test_adjacent_core_extents_have_no_gap_or_overlap(self):
        left = rumple_core_extent(SpatialExtent(0, 0, 8, 12), self.rumple)
        right = rumple_core_extent(SpatialExtent(8, 0, 16, 12), self.rumple)
        self.assertEqual(left.xmax, right.xmin)
        self.assertEqual(self.rumple.extent.xmin, left.xmin)
        self.assertEqual(self.rumple.extent.xmax, right.xmax)

    def test_four_boundaries_and_corner_cover_global_grid_once(self):
        cores = [SpatialExtent(0, 0, 8, 6), SpatialExtent(8, 0, 16, 6), SpatialExtent(0, 6, 8, 12), SpatialExtent(8, 6, 16, 12)]
        extents = [rumple_core_extent(core, self.rumple) for core in cores]
        area = sum(item.width * item.height for item in extents if item)
        self.assertAlmostEqual(self.rumple.extent.width * self.rumple.extent.height, area)
        self.assertEqual(extents[0].xmax, extents[1].xmin)
        self.assertEqual(extents[0].ymax, extents[2].ymin)

    def test_streaming_totals_combine_without_halo_double_count(self):
        a = RumpleTotals(12.0, 10.0, 10)
        b = RumpleTotals(18.0, 10.0, 10)
        total = a.combine(b)
        self.assertEqual(20, total.valid_patch_count)
        self.assertAlmostEqual(1.5, total.rumple_index)

    def test_halo_derivation_is_explicit(self):
        halo = RumpleHaloRequirement()
        self.assertEqual(1, halo.chm_cells)
        self.assertIn("2x2", halo.reason)

    def test_resource_plan_counts_shared_rumple_arrays(self):
        chm = estimate_work_unit_resources(1_000_000, raster_cells=2_000_000, product="chm")
        rumple = estimate_work_unit_resources(1_000_000, raster_cells=2_000_000, product="rumple")
        self.assertGreater(rumple.estimated_memory, chm.estimated_memory)
        plan = derive_adaptive_plan(AdaptivePlannerInputs(5000, 5000, 20_000_000, 1.0, product="rumple"))
        self.assertEqual(50.0, plan.buffer_distance)
        self.assertTrue(any("simultaneous buffered CHM" in item for item in plan.rationale))


class ErrorRetentionTests(unittest.TestCase):
    def test_recent_error_survives_dialog_lifetime(self):
        with tempfile.TemporaryDirectory() as folder:
            write_recent_error(folder, DurableErrorRecord("TEST", "PROCESS", "User", "Technical", "finalizing", job_id="job-a"))
            loaded = read_recent_error(folder)
            self.assertEqual("TEST", loaded.code)
            self.assertEqual("job-a", loaded.job_id)


class StaticIntegrationTests(unittest.TestCase):
    def test_completion_cleanup_is_finally_guarded(self):
        source = (Path(__file__).parents[1] / "pyforestscan_qgis" / "ui" / "pages.py").read_text(encoding="utf-8")
        self.assertIn("finally:\n            self._finish_batch_run(terminal)", source)
        self.assertIn("self._processing_watchdog", source)

    def test_adaptive_route_accepts_rumple_without_publishing_supporting_chm(self):
        source = (Path(__file__).parents[1] / "pyforestscan_qgis" / "core" / "polygon_batch.py").read_text(encoding="utf-8")
        self.assertIn("scalable_products <= {ProductType.CHM, ProductType.RUMPLE}", source)
        self.assertIn("if ProductType.CHM in requested:", source)


if __name__ == "__main__":
    unittest.main()
