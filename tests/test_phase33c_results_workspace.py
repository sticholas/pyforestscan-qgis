"""Regression coverage for the Phase 33C results workspace."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.backend.models import BackendRegistry
from pyforestscan_qgis.core.backend.system_summary import format_system_summary
from pyforestscan_qgis.core.processing_history import (
    ProcessingHistoryEntry,
    append_processing_history,
    format_recent_result,
    read_processing_history,
)


ROOT = Path(__file__).resolve().parents[1]
PAGES = (ROOT / "pyforestscan_qgis" / "ui" / "pages.py").read_text(encoding="utf-8")
MISSION_CONTROL = (ROOT / "pyforestscan_qgis" / "ui" / "mission_control.py").read_text(encoding="utf-8")


def _entry(job: str, attempt: str, date: str, status: str = "SUCCEEDED") -> ProcessingHistoryEntry:
    return ProcessingHistoryEntry(
        job_id=job,
        attempt_id=attempt,
        date=date,
        source="/data/ept.json",
        source_mode="polygon",
        products=("chm", "rumple"),
        status=status,
        elapsed_seconds=12.0,
        outputs=(f"/outputs/{job}/chm.tif",),
        output_folder=f"/outputs/{job}",
        report_path=f"/outputs/{job}/processing_report.html",
        area_hectares=24.4,
    )


class Phase33CResultsWorkspaceTests(unittest.TestCase):
    def test_history_is_newest_first_bounded_and_attempt_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.json"
            for index in range(18):
                append_processing_history(path, _entry(f"job-{index}", f"attempt-{index}", str(index)), limit=15)
            history = read_processing_history(path)
        self.assertEqual(15, len(history))
        self.assertEqual("job-17", history[0].job_id)
        self.assertEqual("job-3", history[-1].job_id)

    def test_recent_summary_uses_product_names_and_terminal_wording(self):
        summary = format_recent_result(_entry("job", "attempt", "2026-09-04T07:18:00"))
        self.assertIn("Complete", summary)
        self.assertIn("CHM", summary)
        self.assertIn("Rumple", summary)
        self.assertNotIn("chm.tif", summary)

    def test_failed_result_without_outputs_remains_actionable(self):
        method = PAGES.split("def set_current_result", 1)[1].split("def set_recent_results", 1)[0]
        self.assertIn("paths or output_folder or report_path", method)
        self.assertIn("No successful outputs. Open the report for details.", method)
        self.assertIn("setEnabled(bool(paths))", method)

    def test_terminal_status_says_complete_without_report_path(self):
        method = PAGES.split("def _on_batch_complete", 1)[1].split("def _on_batch_failed", 1)[0]
        self.assertIn("Complete - {completed_count} {noun} created successfully.", method)
        self.assertNotIn("Report:", method)

    def test_processing_workspace_has_no_height_consuming_stretch(self):
        method = PAGES.split("def _install_process_workspace", 1)[1].split("def _apply_process_layout", 1)[0]
        self.assertNotIn("process_workspace_layout.addStretch", method)
        self.assertIn("QSizePolicy.Maximum", method)

    def test_result_actions_are_qt_native_and_history_isolated(self):
        self.assertIn('QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))', PAGES)
        self.assertIn('QPushButton("Open Outputs")', PAGES)
        selected = PAGES.split("def load_selected_historical_result", 1)[1].split("def open_current_outputs", 1)[0]
        self.assertIn("loadResultOutputsRequested.emit", selected)
        self.assertNotIn("session_state", selected)

    def test_details_geometry_is_refreshed_for_first_expansion(self):
        helper = PAGES.split("def _size_text_edit_to_content", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("updateGeometry", helper)
        self.assertIn("_fit_collapsible_to_visible_content", helper)
        self.assertIn("QTimer.singleShot", helper)

    def test_release_ui_uses_current_diagnostic_terms_and_help(self):
        self.assertNotIn('"Troubleshooting: reset workspace"', PAGES)
        self.assertIn('QPushButton("Open Outputs")', PAGES)
        self.assertIn("Default folder where PyForestScan saves final scientific outputs", PAGES)
        self.assertIn("Choose the default output folder using the system folder picker", PAGES)
        self.assertIn("preserving Recent Results", PAGES)

    def test_new_run_refreshes_instead_of_erasing_history(self):
        clear_method = MISSION_CONTROL.split("def _clear_current_run_state", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("_refresh_recent_results()", clear_method)
        self.assertNotIn("set_recent_results(())", clear_method)

    def test_system_summary_comes_from_registry_state(self):
        registry = BackendRegistry.from_dict({"dependencies": [
            {"name": name, "required": True, "verification_status": "pass", "detected_version": version}
            for name, version in (
                ("python", "3.12.13"), ("pyforestscan", "0.4.1"), ("pdal", "2.8.4"),
                ("gdal", "3.10.2"), ("rasterio", "1.4.3"),
            )
        ]})
        summary = format_system_summary("READY", "0.2.0-beta.1", registry, "Verified")
        self.assertIn("Processing Engine: Ready", summary)
        self.assertIn("Python: 3.12.13", summary)
        self.assertIn("Plugin: 0.2.0-beta.1", summary)
        self.assertIn("Open Technical Log", summary)


if __name__ == "__main__":
    unittest.main()
