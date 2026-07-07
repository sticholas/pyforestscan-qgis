"""Tests for Mission Control state models."""

from __future__ import annotations

from pathlib import Path
import unittest

from pyforestscan_qgis.core.workspace import create_run_context
from pyforestscan_qgis.ui.state import MissionControlState


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
