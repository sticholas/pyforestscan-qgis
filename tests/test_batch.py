"""Tests for sequential batch workflow foundations."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from pyforestscan_qgis.core.batch import (
    BatchItemResult,
    BatchProductSettings,
    BatchRequest,
    BatchResult,
    batch_run_context,
    create_batch_folder,
    discover_lidar_files,
)
from pyforestscan_qgis.core.batch_results import batch_result_to_dict, write_batch_summaries
from pyforestscan_qgis.core.batch_runner import BatchRunner
from pyforestscan_qgis.core.types import ProductType


class BatchWorkflowTests(unittest.TestCase):
    """Batch helpers stay deterministic and independent from QGIS."""

    def test_discover_lidar_files_respects_recursive_flag(self) -> None:
        """Discovery finds supported files and only descends when requested."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.las").write_text("", encoding="utf-8")
            (root / "b.laz").write_text("", encoding="utf-8")
            (root / "c.copc.laz").write_text("", encoding="utf-8")
            (root / "ignore.txt").write_text("", encoding="utf-8")
            nested = root / "nested"
            nested.mkdir()
            (nested / "d.copc").write_text("", encoding="utf-8")
            ept = nested / "ept_dataset"
            ept.mkdir()
            (ept / "ept.json").write_text("{}", encoding="utf-8")

            shallow = discover_lidar_files(root, recursive=False)
            recursive = discover_lidar_files(root, recursive=True)

            self.assertEqual(["a.las", "b.laz", "c.copc.laz"], [item.path.name for item in shallow])
            self.assertEqual(["a.las", "b.laz", "c.copc.laz", "d.copc", "ept.json"], [item.path.name for item in recursive])

    def test_batch_folder_and_run_context_paths_are_stable(self) -> None:
        """Batch folders and child run contexts use the documented layout."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = create_batch_folder(root, datetime(2026, 1, 2, 3, 4, 5))
            second = create_batch_folder(root, datetime(2026, 1, 2, 3, 4, 5))
            context = batch_run_context(root / "sample.las", first).ensure_directories()

            self.assertEqual("pyforestscan_batch_20260102_030405", first.name)
            self.assertEqual("pyforestscan_batch_20260102_030405_02", second.name)
            self.assertEqual(first / "sample", context.run_folder)
            for folder in (context.reports_dir, context.tables_dir, context.outputs_dir, context.logs_dir, context.temp_dir):
                self.assertTrue(folder.is_dir())
            self.assertEqual(context.reports_dir / "dataset_report.json", context.dataset_report_json)
            self.assertEqual(context.logs_dir / "job_summary.json", context.job_summary_json)

    def test_batch_summary_writers_create_json_csv_and_html(self) -> None:
        """Batch summaries are written in all user-facing formats."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = batch_run_context(root / "sample.las", root / "batch").ensure_directories()
            result = BatchResult(
                batch_id="batch-1",
                title="Test Batch",
                started_at="2026-01-01T00:00:00+00:00",
                finished_at="2026-01-01T00:01:00+00:00",
                batch_folder=root / "batch",
                items=(
                    BatchItemResult(
                        dataset_path=root / "sample.las",
                        run_context=context,
                        status="completed",
                        message="completed",
                        outputs=(context.outputs_dir / "chm.tif",),
                        bounds_summary="X 0 to 1; Y 0 to 1",
                    ),
                ),
                summary_json=root / "batch" / "batch_summary.json",
                summary_csv=root / "batch" / "batch_summary.csv",
                summary_html=root / "batch" / "batch_summary.html",
            )

            written = write_batch_summaries(result)
            payload = json.loads(written.summary_json.read_text(encoding="utf-8"))

            self.assertTrue(written.summary_json.exists())
            self.assertTrue(written.summary_csv.exists())
            self.assertTrue(written.summary_html.exists())
            self.assertEqual(1, payload["success_count"])
            self.assertEqual(0, payload["skipped_count"])
            self.assertEqual(1, payload["total_files"])
            self.assertEqual(1, payload["total_output_count"])
            self.assertEqual("completed", payload["items"][0]["status"])
            self.assertIn("Test Batch", written.summary_html.read_text(encoding="utf-8"))

    def test_batch_runner_records_per_file_failures(self) -> None:
        """A dataset failure is recorded without aborting the whole batch by default."""

        class FailingAdapter:
            def inspect_dataset(self, _path: Path) -> object:
                raise RuntimeError("inspection failed")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            one = root / "one.las"
            two = root / "two.las"
            one.write_text("", encoding="utf-8")
            two.write_text("", encoding="utf-8")
            request = BatchRequest(
                input_folder=root,
                output_folder=root / "out",
                recursive=False,
                datasets=(one, two),
                settings=BatchProductSettings(products=(ProductType.CHM,), grid_resolution=1.0),
            )
            runner = BatchRunner(adapter=FailingAdapter())  # type: ignore[arg-type]

            result = runner.run(request)
            payload = batch_result_to_dict(result)

            self.assertEqual(0, result.success_count)
            self.assertEqual(2, result.failure_count)
            self.assertEqual(["failed", "failed"], [item["status"] for item in payload["items"]])
            self.assertTrue(result.summary_json.exists())

    def test_batch_runner_can_cancel_remaining_files(self) -> None:
        """Cancel control records unprocessed files as skipped and writes summaries."""

        class FailingAdapter:
            def inspect_dataset(self, _path: Path) -> object:
                raise RuntimeError("inspection failed")

        calls = {"count": 0}

        def control() -> str | None:
            calls["count"] += 1
            return "cancel" if calls["count"] > 1 else None

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            one = root / "one.las"
            two = root / "two.las"
            one.write_text("", encoding="utf-8")
            two.write_text("", encoding="utf-8")
            request = BatchRequest(
                input_folder=root,
                output_folder=root / "out",
                recursive=False,
                datasets=(one, two),
                settings=BatchProductSettings(products=(ProductType.CHM,), grid_resolution=1.0),
            )
            runner = BatchRunner(adapter=FailingAdapter(), control_callback=control)  # type: ignore[arg-type]

            result = runner.run(request)
            payload = batch_result_to_dict(result)

            self.assertEqual(1, result.failure_count)
            self.assertEqual(1, result.skipped_count)
            self.assertEqual(["failed", "skipped"], [item["status"] for item in payload["items"]])
            self.assertTrue(result.summary_html.exists())


if __name__ == "__main__":
    unittest.main()
