"""Tests for Mission Control state models."""

from __future__ import annotations

from pathlib import Path
import unittest

from pyforestscan_qgis.core.jobs import JobMode, JobProgress, JobRecord, JobResultRecord, JobStatus
from pyforestscan_qgis.core.workspace import create_run_context
from pyforestscan_qgis.ui.state import MissionControlState, build_project_summary, dataset_type_label, product_key_from_result_type


class MissionControlStateTests(unittest.TestCase):
    """Mission Control state tests without QGIS."""

    def test_activity_is_prepended_and_limited(self) -> None:
        state = MissionControlState()

        for index in range(10):
            state = state.with_activity(f"Activity {index}", limit=3)

        self.assertEqual(len(state.activities), 3)
        self.assertEqual(state.activities[0].label, "Activity 9")
        self.assertEqual(state.activities[-1].label, "Activity 7")

    def test_status_updates_are_immutable(self) -> None:
        state = MissionControlState()

        next_state = state.with_environment("READY").with_dataset("plot.laz").with_planning("Ready")

        self.assertEqual(state.environment_status, "Unknown")
        self.assertEqual(next_state.environment_status, "READY")
        self.assertEqual(next_state.latest_dataset, "plot.laz")
        self.assertEqual(next_state.planning_status, "Ready")

    def test_report_paths_are_deduplicated(self) -> None:
        state = MissionControlState()
        path = Path("report.json")

        state = state.with_report_path(path).with_report_path(path)

        self.assertEqual(state.latest_report_paths, (path,))

    def test_dataset_pending_clears_downstream_run_state(self) -> None:
        state = MissionControlState()
        context = create_run_context("old.laz", "outputs")

        populated = (
            state.with_active_run(context)
            .with_planning("Ready")
            .with_report_path(Path("old_report.html"))
            .with_activity("Old run", "complete")
        )
        pending = populated.with_dataset_pending("new.laz")

        self.assertEqual(pending.latest_dataset, "new.laz")
        self.assertIsNone(pending.latest_project)
        self.assertIsNone(pending.active_run)
        self.assertEqual(pending.latest_report_paths, ())
        self.assertEqual(pending.planning_status, "Not started")
        self.assertEqual(pending.activities, populated.activities)

    def test_without_active_run_clears_results_but_keeps_dataset(self) -> None:
        context = create_run_context("plot.laz", "outputs")
        state = MissionControlState().with_active_run(context).with_planning("Ready").with_report_path(Path("report.html"))

        cleared = state.without_active_run()

        self.assertEqual(cleared.latest_dataset, "plot.laz")
        self.assertIsNone(cleared.latest_project)
        self.assertIsNone(cleared.active_run)
        self.assertEqual(cleared.latest_report_paths, ())
        self.assertEqual(cleared.planning_status, "Not started")


    def test_project_summary_tracks_generated_loaded_missing_and_unavailable_products(self) -> None:
        context = create_run_context("plot.copc.laz", "outputs")
        chm_path = context.outputs_dir / "chm.tif"
        pad_path = context.outputs_dir / "pad.tif"
        job = JobRecord(
            job_id="job-1",
            title="Products",
            status=JobStatus.COMPLETED,
            mode=JobMode.PROCESSING,
            product_plan_path=context.product_plan_json,
            output_folder=context.logs_dir,
            summary_path=context.job_summary_json,
            created_at="2026-07-07T00:00:00+00:00",
            updated_at="2026-07-07T00:03:00+00:00",
            progress=JobProgress(100, "Done"),
            requested_products=("chm", "pad", "pai"),
            results=(
                JobResultRecord(chm_path, "chm_geotiff", "CHM"),
                JobResultRecord(pad_path, "pad_geotiff", "PAD"),
                JobResultRecord(context.job_summary_json, "job_summary_json", "Summary"),
            ),
        )
        state = MissionControlState().with_active_run(context).with_environment("READY").with_backend("READY")

        summary = build_project_summary(state, jobs=(job,), loaded_paths=(chm_path,), workspace="outputs", project_crs="EPSG:32604")
        statuses = {item.product: item for item in summary.product_statuses}

        self.assertEqual(summary.dataset_name, "plot.copc.laz")
        self.assertEqual(summary.dataset_type, "COPC")
        self.assertEqual(summary.output_folder, context.outputs_dir)
        self.assertEqual(summary.project_crs, "EPSG:32604")
        self.assertEqual(summary.processing_state, "completed")
        self.assertEqual(summary.last_processing_time, "2026-07-07T00:03:00+00:00")
        self.assertEqual(statuses["chm"].load_state, "Loaded")
        self.assertEqual(statuses["pad"].load_state, "Generated")
        self.assertEqual(statuses["pai"].load_state, "Missing")
        self.assertEqual(statuses["dtm"].load_state, "Unavailable")
        self.assertIn("Products generated: CHM, PAD", summary.generated_summary())
        self.assertEqual(summary.loaded_summary(), "Products loaded: CHM")

    def test_product_and_dataset_type_mapping_helpers_are_stable(self) -> None:
        self.assertEqual(product_key_from_result_type("point_density_geotiff"), "point_density")
        self.assertEqual(product_key_from_result_type("job_summary_json"), None)
        self.assertEqual(dataset_type_label("/tmp/plot.las"), "LAS")
        self.assertEqual(dataset_type_label("/tmp/ept.json"), "EPT")
        self.assertEqual(dataset_type_label("/tmp/plot.copc.laz"), "COPC")

    def test_active_run_and_default_output_folder_are_immutable(self) -> None:
        state = MissionControlState()
        context = create_run_context("plot.laz", "outputs")

        next_state = state.with_default_output_folder(Path("outputs")).with_active_run(context)

        self.assertIsNone(state.default_output_folder)
        self.assertIsNone(state.active_run)
        self.assertEqual(next_state.default_output_folder, Path("outputs"))
        self.assertEqual(next_state.active_run, context)
        self.assertEqual(next_state.latest_dataset, "plot.laz")
        self.assertEqual(next_state.latest_project, str(context.run_folder))


if __name__ == "__main__":
    unittest.main()
