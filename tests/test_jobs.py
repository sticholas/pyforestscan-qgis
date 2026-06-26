"""Tests for the dry-run job execution framework."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.job_manager import JobExecutionError, JobManager
from pyforestscan_qgis.core.job_results import job_to_dict, render_job_summary_json
from pyforestscan_qgis.core.types import ChmResult
from pyforestscan_qgis.core.jobs import JobStatus


class JobManagerTests(unittest.TestCase):
    """Plain-Python tests for dry-run job execution."""

    def test_dry_run_completes_and_writes_summary(self) -> None:
        """A valid product plan produces a completed job summary only."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan_path = _write_plan(root / "product_plan.json")
            manager = JobManager()

            job = manager.run_dry_run(plan_path, root / "jobs", title="Test Dry Run")

            self.assertEqual(JobStatus.COMPLETED, job.status)
            self.assertEqual(100.0, job.progress.percent)
            self.assertEqual(("chm", "pai"), job.requested_products)
            self.assertEqual(1, len(job.results))
            self.assertTrue(job.results[0].path.exists())
            payload = json.loads(job.results[0].path.read_text(encoding="utf-8"))
            self.assertFalse(payload["processing_executed"])
            self.assertFalse(payload["scientific_outputs_created"])
            self.assertEqual("completed", payload["status"])
            self.assertEqual(["chm", "pai"], payload["requested_products"])
            self.assertEqual(2, len(payload["pipelines"]))
            self.assertEqual("chm", payload["pipelines"][0]["product"])
            self.assertFalse((root / "jobs" / "chm.tif").exists())

    def test_invalid_plan_raises_before_job_creation(self) -> None:
        """A malformed Product Planner JSON is rejected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan_path = root / "bad_plan.json"
            plan_path.write_text('{"processing_executed": true, "products": []}', encoding="utf-8")
            manager = JobManager()

            with self.assertRaises(JobExecutionError):
                manager.create_dry_run_job(_job_request(plan_path, root / "jobs"))

    def test_blocked_product_returns_failed_summary(self) -> None:
        """Blocked products fail dry-run validation and still write a summary."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan_path = _write_plan(root / "blocked_plan.json", status="Blocked")
            manager = JobManager()

            job = manager.run_dry_run(plan_path, root / "jobs")

            self.assertEqual(JobStatus.FAILED, job.status)
            self.assertIsNotNone(job.error_message)
            self.assertTrue(job.results[0].path.exists())
            payload = json.loads(job.results[0].path.read_text(encoding="utf-8"))
            self.assertEqual("failed", payload["status"])

    def test_event_sink_can_request_cancellation(self) -> None:
        """The event sink can cancel a running dry-run job."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan_path = _write_plan(root / "product_plan.json")
            manager_holder: dict[str, JobManager] = {}

            def sink(job):  # type: ignore[no-untyped-def]
                if job.status is JobStatus.RUNNING and job.progress.percent >= 45:
                    manager_holder["manager"].request_cancel(job.job_id)

            manager = JobManager(event_sink=sink)
            manager_holder["manager"] = manager

            job = manager.run_dry_run(plan_path, root / "jobs")

            self.assertEqual(JobStatus.CANCELLED, job.status)
            self.assertTrue(job.results[0].path.exists())
            payload = json.loads(job.results[0].path.read_text(encoding="utf-8"))
            self.assertEqual("cancelled", payload["status"])


    def test_processing_job_creates_chm_result_record(self) -> None:
        """A CHM processing job records the GeoTIFF output artifact."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dataset_report = root / "dataset_report.json"
            dataset_report.write_text(json.dumps({"geometry": {"crs": "EPSG:32610"}}), encoding="utf-8")
            plan_path = _write_plan(root / "product_plan.json", include_pai=False)
            manager = JobManager(adapter=_FakeAdapter())

            job = manager.run_pipeline(plan_path, root / "logs", title="CHM Processing Test", summary_path=root / "logs" / "job_summary.json")

            self.assertEqual(JobStatus.COMPLETED, job.status)
            chm_results = [result for result in job.results if result.result_type == "chm_geotiff"]
            self.assertEqual(1, len(chm_results))
            self.assertEqual(root / "outputs" / "chm.tif", chm_results[0].path)
            self.assertTrue(chm_results[0].path.exists())
            payload = json.loads((root / "logs" / "job_summary.json").read_text(encoding="utf-8"))
            self.assertTrue(payload["processing_executed"])
            self.assertTrue(payload["scientific_outputs_created"])
            self.assertEqual(str(root / "outputs" / "chm.tif"), payload["results"][0]["path"])

    def test_job_summary_renderer_marks_no_scientific_outputs(self) -> None:
        """Serialized summaries explicitly state that processing did not run."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = JobManager()
            job = manager.run_dry_run(_write_plan(root / "product_plan.json"), root / "jobs")

            payload = job_to_dict(job)
            rendered = render_job_summary_json(job)

            self.assertFalse(payload["processing_executed"])
            self.assertFalse(payload["scientific_outputs_created"])
            self.assertIn('"scientific_outputs_created": false', rendered)


def _job_request(plan_path: Path, output_folder: Path):  # type: ignore[no-untyped-def]
    from pyforestscan_qgis.core.jobs import JobRequest

    return JobRequest(product_plan_path=plan_path, output_folder=output_folder)


def _write_plan(path: Path, status: str = "Ready", include_pai: bool = True) -> Path:
    products = [
        {
            "product": "chm",
            "label": "Canopy Height Model (CHM)",
            "requested": True,
            "feasibility_status": "Available",
            "plan_status": status,
            "reason": "Ready for future processing.",
            "warnings": [],
            "estimated_outputs": [
                {
                    "path": str(path.parent / "planned_outputs" / "chm.tif"),
                    "type": "GeoTIFF raster",
                    "description": "Future canopy height raster.",
                }
            ],
        },
    ]
    if include_pai:
        products.append(
            {
                "product": "pai",
                "label": "Plant Area Index (PAI)",
                "requested": True,
                "feasibility_status": "Available",
                "plan_status": status,
                "reason": "Ready for future processing.",
                "warnings": [],
                "estimated_outputs": [
                    {
                        "path": str(path.parent / "planned_outputs" / "pai.tif"),
                        "type": "GeoTIFF raster",
                        "description": "Future PAI raster.",
                    }
                ],
            }
        )
    payload = {
        "title": "Test Product Plan",
        "source_dataset": "plot.laz",
        "source_report": str(path.parent / "dataset_report.json"),
        "processing_executed": False,
        "output_folder": str(path.parent / "outputs"),
        "parameters": {"grid_resolution": 1.0},
        "products": products,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class _FakeAdapter:
    def create_chm(self, request):  # type: ignore[no-untyped-def]
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        request.output_path.write_text("fake chm", encoding="utf-8")
        return ChmResult(
            output_path=request.output_path,
            spatial_extent=(0.0, 1.0, 0.0, 1.0),
            grid_resolution=request.grid_resolution,
            crs=request.crs,
        )


if __name__ == "__main__":
    unittest.main()
