"""Tests for Mission Control run-folder contexts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tempfile
import unittest

from pyforestscan_qgis.core.workspace import create_run_context


class RunContextTests(unittest.TestCase):
    """Run-folder layout tests."""

    def test_create_run_context_uses_expected_paths(self) -> None:
        """A lidar dataset and output root produce predictable internal paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            context = create_run_context(
                Path("/data/My Plot.laz"),
                Path(temp_dir),
                timestamp=datetime(2026, 6, 25, 14, 5, 6),
            )

            self.assertEqual(context.run_folder, Path(temp_dir) / "pyforestscan_runs" / "20260625_140506_My_Plot")
            self.assertEqual(context.dataset_report_json, context.run_folder / "reports" / "dataset_report.json")
            self.assertEqual(context.dataset_report_html, context.run_folder / "reports" / "dataset_report.html")
            self.assertEqual(context.dataset_summary_csv, context.run_folder / "tables" / "dataset_summary.csv")
            self.assertEqual(context.product_plan_json, context.run_folder / "reports" / "product_plan.json")
            self.assertEqual(context.product_plan_html, context.run_folder / "reports" / "product_plan.html")
            self.assertEqual(context.product_plan_csv, context.run_folder / "tables" / "product_plan.csv")
            self.assertEqual(context.job_summary_json, context.run_folder / "logs" / "job_summary.json")
            self.assertEqual(context.outputs_dir, context.run_folder / "outputs")
            self.assertEqual(context.temp_dir, context.run_folder / "temp")

    def test_ensure_directories_creates_run_layout(self) -> None:
        """The run context creates all required folders without output files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            context = create_run_context("plot.las", temp_dir, timestamp=datetime(2026, 6, 25)).ensure_directories()

            for folder in (context.reports_dir, context.tables_dir, context.outputs_dir, context.logs_dir, context.temp_dir):
                self.assertTrue(folder.is_dir())
            self.assertFalse(context.dataset_report_json.exists())
            self.assertFalse(context.product_plan_json.exists())
            self.assertFalse(context.job_summary_json.exists())

    def test_ept_json_uses_parent_folder_as_run_stem(self) -> None:
        """EPT datasets use the parent folder instead of the literal ept stem."""
        context = create_run_context("/data/tile set/ept.json", "/out", timestamp=datetime(2026, 6, 25))

        self.assertEqual(context.run_folder.name, "20260625_000000_tile_set")


if __name__ == "__main__":
    unittest.main()
