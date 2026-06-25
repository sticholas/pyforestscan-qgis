"""Tests for Mission Control state models."""

from __future__ import annotations

from pathlib import Path
import unittest

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


if __name__ == "__main__":
    unittest.main()
