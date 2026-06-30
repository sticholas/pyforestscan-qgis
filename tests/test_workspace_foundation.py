"""Tests for the local Workspace foundation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.workspace import (
    HISTORY_FILE,
    NOTES_FILE,
    RECENT_FILE,
    SESSION_FILE,
    TIMELINE_FILE,
    VERSION_FILE,
    WORKSPACE_FILE,
    WORKSPACE_FOLDER_NAME,
    WorkspaceHistoryRun,
    WorkspaceManager,
    WorkspaceSession,
    WorkspaceStatus,
    WorkspaceTimelineEvent,
    WorkspaceVersion,
)


class WorkspaceFoundationTests(unittest.TestCase):
    """Workspace persistence is local, typed, and QGIS-free."""

    def test_workspace_creation_writes_expected_hidden_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = WorkspaceManager(config_root=Path(tmp) / "config")
            workspace = manager.create_workspace(Path(tmp) / "analysis", name="Plot A")
            folder = workspace.workspace_dir

            self.assertEqual(Path(tmp) / "analysis" / WORKSPACE_FOLDER_NAME, folder)
            for name in (WORKSPACE_FILE, SESSION_FILE, TIMELINE_FILE, NOTES_FILE, HISTORY_FILE, RECENT_FILE, VERSION_FILE):
                self.assertTrue((folder / name).exists(), name)

    def test_workspace_serialization_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = WorkspaceManager(config_root=Path(tmp) / "config")
            created = manager.create_workspace(Path(tmp) / "analysis", name="Plot A")
            loaded = manager.load_workspace(Path(tmp) / "analysis")

            self.assertEqual(created.workspace_id, loaded.workspace_id)
            self.assertEqual("Plot A", loaded.name)
            self.assertEqual(created.output_root, loaded.output_root)

    def test_session_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = WorkspaceManager(config_root=Path(tmp) / "config")
            session = WorkspaceSession(
                last_opened_workspace=Path(tmp) / "analysis" / WORKSPACE_FOLDER_NAME,
                last_selected_dataset=Path("plot.laz"),
                last_output_folder=Path(tmp) / "analysis",
                last_selected_products=("chm", "pai"),
                last_page="Processing",
                window_geometry="abc",
                floating=True,
                docked=False,
                maximum_recent_items=7,
            )

            manager.save_global_session(session)
            loaded = manager.load_global_session()

            self.assertEqual(Path("plot.laz"), loaded.last_selected_dataset)
            self.assertEqual(("chm", "pai"), loaded.last_selected_products)
            self.assertEqual("Processing", loaded.last_page)
            self.assertEqual(7, loaded.maximum_recent_items)

    def test_timeline_events_auto_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = WorkspaceManager(config_root=Path(tmp) / "config")
            workspace = manager.create_workspace(Path(tmp) / "analysis")
            workspace = manager.add_timeline_event(workspace, "dataset_selected", "Dataset selected")
            payload = json.loads((workspace.workspace_dir / TIMELINE_FILE).read_text(encoding="utf-8"))

            self.assertTrue(any(item["event_type"] == "dataset_selected" for item in payload["events"]))

    def test_history_append_auto_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = WorkspaceManager(config_root=Path(tmp) / "config")
            workspace = manager.create_workspace(Path(tmp) / "analysis")
            run = WorkspaceHistoryRun(
                run_id="job-1",
                products=("chm",),
                parameters={"grid_resolution": "1.0"},
                success=True,
                output_paths=(Path(tmp) / "analysis" / "outputs" / "chm.tif",),
                duration_seconds=12.5,
            )

            workspace = manager.append_history(workspace, run)
            loaded = manager.load_workspace(Path(tmp) / "analysis")

            self.assertEqual(1, len(loaded.history.runs))
            self.assertEqual("job-1", loaded.history.runs[0].run_id)
            self.assertEqual(12.5, loaded.history.runs[0].duration_seconds)

    def test_recent_item_trimming(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = WorkspaceManager(config_root=Path(tmp) / "config", recent_limit=3)
            workspace = manager.create_workspace(Path(tmp) / "analysis")
            for index in range(8):
                workspace = manager.add_recent_item(workspace, "dataset", Path(tmp) / f"tile_{index}.laz")

            loaded = manager.load_workspace(Path(tmp) / "analysis")

            self.assertEqual(3, len(loaded.recent_items))
            self.assertEqual("tile_7.laz", loaded.recent_items[0].path.name)

    def test_status_updates_completion_percentage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = WorkspaceManager(config_root=Path(tmp) / "config")
            workspace = manager.create_workspace(Path(tmp) / "analysis")
            workspace = manager.update_state(workspace, WorkspaceStatus.DATASET_SELECTED, True, "Build plan")
            workspace = manager.update_state(workspace, WorkspaceStatus.PLANNING_COMPLETE, True, "Run products")

            self.assertTrue(workspace.state.dataset_selected)
            self.assertTrue(workspace.state.planning_complete)
            self.assertEqual("Run products", workspace.state.current_step)
            self.assertGreaterEqual(workspace.state.completion_percentage, 30)

    def test_version_model_round_trip(self) -> None:
        version = WorkspaceVersion(format_version="1.0", created_by="tests", plugin_version="0.1")
        loaded = WorkspaceVersion.from_dict(version.to_dict())

        self.assertEqual(version, loaded)

    def test_timeline_event_round_trip(self) -> None:
        event = WorkspaceTimelineEvent.create("results_reviewed", "Results reviewed", {"path": "summary.html"})
        loaded = WorkspaceTimelineEvent.from_dict(event.to_dict())

        self.assertEqual(event.event_type, loaded.event_type)
        self.assertEqual({"path": "summary.html"}, loaded.details)


if __name__ == "__main__":
    unittest.main()
