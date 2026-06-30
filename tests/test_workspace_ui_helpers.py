"""Tests for Workspace Welcome and resume display helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.workspace import (
    WorkspaceHistory,
    WorkspaceHistoryRun,
    WorkspaceManager,
    WorkspaceStatus,
    format_timeline_events,
    summarize_recent_workspaces,
    workspace_primary_action,
    workspace_status_label,
)


class WorkspaceUiHelperTests(unittest.TestCase):
    """Workspace UI helper behavior remains QGIS-free."""

    def test_workspace_status_and_primary_action_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = WorkspaceManager(config_root=Path(tmp) / "config")
            workspace = manager.create_workspace(Path(tmp) / "analysis", name="North Plot")

            self.assertIn("North Plot", workspace_status_label(workspace))
            self.assertIn("Select a LiDAR dataset", workspace_primary_action(workspace))

            workspace = manager.update_state(workspace, WorkspaceStatus.DATASET_SELECTED, True, "Build product plan")
            self.assertIn("Build a Product Plan", workspace_primary_action(workspace))

            workspace = manager.update_state(workspace, WorkspaceStatus.PLANNING_COMPLETE, True, "Run selected products")
            self.assertIn("Run selected products", workspace_primary_action(workspace))

    def test_recent_workspace_summaries_flag_missing_and_remove_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "analysis" / ".pyforestscan"
            existing.mkdir(parents=True)
            missing = Path(tmp) / "missing" / ".pyforestscan"

            summaries = summarize_recent_workspaces((existing, existing, missing), limit=10)

            self.assertEqual(2, len(summaries))
            self.assertEqual("analysis", summaries[0].label)
            self.assertTrue(summaries[0].exists)
            self.assertFalse(summaries[1].exists)

    def test_timeline_formatting_is_reverse_chronological_and_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = WorkspaceManager(config_root=Path(tmp) / "config")
            workspace = manager.create_workspace(Path(tmp) / "analysis")
            workspace = manager.add_timeline_event(workspace, "dataset_selected", "Dataset selected")
            workspace = manager.add_timeline_event(workspace, "notes_saved", "Workspace notes saved")

            lines = format_timeline_events(workspace.timeline, limit=2)

            self.assertEqual(2, len(lines))
            self.assertTrue(lines[0].startswith("Notes saved - Workspace notes saved"))
            self.assertTrue(lines[1].startswith("Dataset selected - Dataset selected"))

    def test_notes_persist_and_add_timeline_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = WorkspaceManager(config_root=Path(tmp) / "config")
            workspace = manager.create_workspace(Path(tmp) / "analysis")

            manager.save_notes(workspace, "# Field notes\nImportant canopy edge artifacts.")
            loaded = manager.load_workspace(Path(tmp) / "analysis")

            self.assertIn("Field notes", loaded.notes.markdown)
            self.assertEqual("notes_saved", loaded.timeline[-1].event_type)

    def test_reset_workspace_state_preserves_workspace_but_clears_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = WorkspaceManager(config_root=Path(tmp) / "config")
            workspace = manager.create_workspace(Path(tmp) / "analysis", name="Reset Me")
            workspace = manager.update_state(workspace, WorkspaceStatus.DATASET_SELECTED, True, "Build plan")
            workspace = manager.append_history(
                workspace,
                WorkspaceHistoryRun(
                    run_id="job-1",
                    products=("chm",),
                    parameters={},
                    success=True,
                    output_paths=(Path(tmp) / "analysis" / "outputs" / "chm.tif",),
                ),
            )

            reset = manager.reset_workspace_state(workspace)

            self.assertEqual("Reset Me", reset.name)
            self.assertFalse(reset.state.dataset_selected)
            self.assertEqual(WorkspaceHistory(), reset.history)
            self.assertEqual("workspace_reset", reset.timeline[-1].event_type)


if __name__ == "__main__":
    unittest.main()
